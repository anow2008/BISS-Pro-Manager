# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
from urllib.request import urlopen, urlretrieve
import os, re, shutil

# --------------------------------------------------
# Utils
# --------------------------------------------------

def get_softcam_path():
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/ncam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0]

PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = os.path.join(PLUGIN_PATH, "icons")

class AutoScale:
    def __init__(self):
        d = getDesktop(0).size()
        self.scale = min(d.width() / 1920.0, d.height() / 1080.0)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(18, v * self.scale))

# --------------------------------------------------
# Main Screen
# --------------------------------------------------

class BISSPro(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v3.0">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}"
                size="{self.ui.px(1060)},{self.ui.px(550)}"
                itemHeight="{self.ui.px(110)}"
                scrollbarMode="showOnDemand"
                transparent="1"/>
            <widget name="progress" position="{self.ui.px(50)},{self.ui.px(620)}"
                size="{self.ui.px(1000)},{self.ui.px(15)}" />
            <widget name="status" position="{self.ui.px(50)},{self.ui.px(650)}"
                size="{self.ui.px(1000)},{self.ui.px(60)}"
                font="Regular;{self.ui.font(30)}"
                halign="center"
                valign="center"
                foregroundColor="#f0a30a"/>
        </screen>"""

        self["menu"] = MenuList([])
        self["progress"] = ProgressBar()
        self["status"] = Label("Ready")

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            }, -1)

        self.timer = eTimer()
        try:
            self.timer.callback.append(self.show_result)
        except:
            self.timer.timeout.connect(self.show_result)

        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [
            ("Add BISS Manually", "add", "add.png"),
            ("Update SoftCam.Key", "upd", "update.png"),
            ("Auto Add BISS", "auto", "autoadd.png")
        ]
        lst = []
        for text, action, icon in items:
            pix = LoadPixmap(os.path.join(ICON_PATH, icon))
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(25, 15), size=(80, 80), png=pix),
                MultiContentEntryText(
                    pos=(130, 25), size=(800, 60),
                    font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)
        self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    # --------------------------------------------------
    # Save BISS (same as manual)
    # --------------------------------------------------

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_id = full_id.zfill(8).upper()
        try:
            os.system(f"sed -i '/F {full_id}/d' {target}")
            entry = f"F {full_id} 00000000 {key.upper()} ;{name}"
            os.system(f'echo \"{entry}\" >> {target}')
            os.system("killall -9 oscam ncam >/dev/null 2>&1")
            if os.path.exists("/etc/init.d/softcam"):
                os.system("/etc/init.d/softcam restart >/dev/null 2>&1")
            return True
        except:
            return False

    # --------------------------------------------------
    # OK Action
    # --------------------------------------------------

    def ok(self):
        curr = self["menu"].getCurrent()
        if not curr:
            return
        action = curr[0]
        service = self.session.nav.getCurrentService()

        if action == "add":
            self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif action == "upd":
            self["status"].setText("Updating...")
            Thread(target=self.do_update).start()
        elif action == "auto":
            self["status"].setText("Searching Online...")
            Thread(target=self.do_auto, args=(service,)).start()

    # --------------------------------------------------
    # Manual callback
    # --------------------------------------------------

    def manual_done(self, key=None):
        if not key:
            return
        service = self.session.nav.getCurrentService()
        info = service.info()

        sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
        vpid = "%04X" % (info.getInfo(iServiceInformation.sVideoPID) & 0xFFFF)
        cid = sid + vpid

        if self.save_biss_key(cid, key, info.getName()):
            self.res = (True, "Saved Successfully")
        else:
            self.res = (False, "Save Error")
        self.timer.start(100, True)

    # --------------------------------------------------
    # Update SoftCam
    # --------------------------------------------------

    def do_update(self):
        try:
            urlretrieve(
                "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key",
                "/tmp/SoftCam.Key"
            )
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            self.res = (True, "SoftCam Updated")
        except:
            self.res = (False, "Update Failed")
        self.timer.start(100, True)

    # --------------------------------------------------
    # AUTO SEARCH (freq + pol + name)
    # --------------------------------------------------

    def do_auto(self, service):
        try:
            info = service.info()
            name = info.getName().lower()

            fe = service.frontendInfo().getAll(True)
            freq = str(fe.get("frequency", ""))[:5]
            pol = "H" if fe.get("polarization", 0) == 0 else "V"

            data = urlopen(
                "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt",
                timeout=10
            ).read().decode("utf-8", "ignore")

            lines = [l.strip().lower() for l in data.splitlines() if l.strip()]
            biss = None

            for i in range(len(lines) - 3):
                if freq in lines[i] and pol in lines[i]:
                    if name in lines[i + 1]:
                        key = lines[i + 2].replace(" ", "")
                        if re.match(r"^[0-9a-f]{16}$", key):
                            biss = key.upper()
                            break

            if not biss:
                self.res = (False, "No Match Found")
                self.timer.start(100, True)
                return

            sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
            vpid = "%04X" % (info.getInfo(iServiceInformation.sVideoPID) & 0xFFFF)
            cid = sid + vpid

            if self.save_biss_key(cid, biss, info.getName()):
                self.res = (True, "Auto Added Successfully")
            else:
                self.res = (False, "Save Error")

        except:
            self.res = (False, "Server Error")

        self.timer.start(100, True)

    def show_result(self):
        self.session.open(
            MessageBox,
            self.res[1],
            MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR,
            timeout=5
        )
        self["status"].setText("Ready")
        self["progress"].setValue(0)

# --------------------------------------------------
# Hex Input
# --------------------------------------------------

class HexInputScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.key = ""
        self["label"] = Label("____ ____ ____ ____")
        self["actions"] = ActionMap(
            ["OkCancelActions", "NumberActions"],
            {
                "ok": self.add,
                "cancel": lambda: self.close(None)
            }, -1)

    def add(self):
        if len(self.key) == 16:
            self.close(self.key)

# --------------------------------------------------
# Plugin entry
# --------------------------------------------------

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="BissPro",
            description="Auto Match by Freq + Name",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        )
    ]
