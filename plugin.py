# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
import os, re, shutil
try:
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib2 import urlopen

# المسارات
PLUGIN_PATH = os.path.dirname(__file__)
ICON_PATH = os.path.join(PLUGIN_PATH, "icons")

def get_softcam_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/ncam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/oscam/SoftCam.Key"

class AutoScale:
    def __init__(self):
        d = getDesktop(0).size()
        self.scale = min(d.width() / 1920.0, d.height() / 1080.0)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(18, v * self.scale))

class BISSPro(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        # تم تغيير اللون البرتقالي إلى الأزرق الاحترافي #3498db
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v3.8">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(550)}" itemHeight="{self.ui.px(110)}" transparent="1"/>
            <eLabel position="{self.ui.px(50)},{self.ui.px(600)}" size="{self.ui.px(1000)},{self.ui.px(2)}" backgroundColor="#444444" />
            <widget name="progress" position="{self.ui.px(50)},{self.ui.px(620)}" size="{self.ui.px(1000)},{self.ui.px(15)}" transparent="1" />
            <widget name="status" position="{self.ui.px(50)},{self.ui.px(650)}" size="{self.ui.px(1000)},{self.ui.px(60)}" font="Regular;{self.ui.font(30)}" halign="center" valign="center" transparent="1" foregroundColor="#3498db"/>
        </screen>"""
        self["status"] = Label("Ready")
        self["progress"] = ProgressBar()
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {"ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)
        self.timer = eTimer()
        try: self.timer.callback.append(self.show_result)
        except: self.timer.timeout.connect(self.show_result)
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [("Add BISS Manually", "add", "add.png"), ("Update SoftCam.Key", "upd", "update.png"), ("Auto Add BISS", "auto", "autoadd.png")]
        lst = []
        for text, action, icon_name in items:
            p = os.path.join(ICON_PATH, icon_name)
            pix = LoadPixmap(path=p) if os.path.exists(p) else None
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(25), self.ui.px(15)), size=(self.ui.px(80), self.ui.px(80)), png=pix),
                MultiContentEntryText(pos=(self.ui.px(130), self.ui.px(25)), size=(self.ui.px(800), self.ui.px(60)), font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_sid = full_id.zfill(8).upper()
        try:
            os.system(f"sed -i '/F {full_sid}/d' {target}")
            new_entry = f"F {full_sid} 00000000 {key.upper()} ;{name}"
            os.system(f'echo "{new_entry}" >> {target}')
            os.system("killall -9 oscam ncam >/dev/null 2>&1")
            if os.path.exists("/etc/init.d/softcam"): os.system("/etc/init.d/softcam restart >/dev/null 2>&1")
            return True
        except: return False

    def ok(self):
        curr = self["menu"].getCurrent()
        if curr and curr[0] == "add": self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif curr:
            service = self.session.nav.getCurrentService()
            if curr[0] == "upd": Thread(target=self.do_update).start()
            else:
                self["status"].setText("Searching Biss Online...")
                Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key=None):
        if not key: return
        service = self.session.nav.getCurrentService()
        if service:
            info = service.info()
            raw_sid = info.getInfo(iServiceInformation.sSID)
            raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
            combined_id = "%04X%04X" % (raw_sid & 0xFFFF, raw_vpid & 0xFFFF if raw_vpid != -1 else 0)
            if self.save_biss_key(combined_id, key, info.getName()):
                self.res = (True, f"Saved: {combined_id}")
            else: self.res = (False, "Error Saving")
            self.timer.start(100, True)

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/SoftCam.Key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            self.res = (True, "SoftCam Updated")
        except: self.res = (False, "Download Error")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
            vpid = info.getInfo(iServiceInformation.sVideoPID)
            combined_id = sid + ("%04X" % (vpid & 0xFFFF) if vpid != -1 else "0000")
            # تحديث الرابط وبحث أفضل
            response = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt", timeout=10)
            raw_data = response.read().decode("utf-8")
            m = re.search(sid + r'.*?([0-9A-Fa-f]{16})', raw_data, re.I)
            if m and self.save_biss_key(combined_id, m.group(1).upper(), info.getName()):
                self.res = (True, f"Found & Added: {m.group(1)}")
            else:
                self.res = (False, f"SID {sid} Not Found Online")
        except: self.res = (False, "Connection Error")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready")

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(900)},{self.ui.px(550)}" title="BISS Editor" backgroundColor="#121212">
            <eLabel position="0,0" size="900,80" backgroundColor="#3498db" zPosition="-1" />
            <widget name="keylabel" position="60,110" size="780,90" font="Regular;{self.ui.font(60)}" halign="center" valign="center" foregroundColor="#3498db" backgroundColor="#1f1f1f" transparent="0" />
            <widget name="hexlist" position="350,230" size="200,220" itemHeight="{self.ui.px(70)}" font="Regular;{self.ui.font(50)}" selectionColor="#3498db" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="300,480" size="30,30" alphatest="on" />
            <widget name="key_green" position="340,480" size="150,30" font="Regular;22" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="550,480" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="590,480" size="150,30" font="Regular;22" />
        </screen>"""
        self.key = ""
        self["keylabel"] = Label("")
        self["key_green"] = Label("Save")
        self["key_yellow"] = Label("Delete")
        self["hexlist"] = MenuList(["A", "B", "C", "D", "E", "F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "DirectionActions"], {
            "ok": self.add_from_list, "cancel": self.close, "green": self.save, "yellow": self.backspace,
            "up": self["hexlist"].up, "down": self["hexlist"].down,
            "0": lambda: self.add("0"), "1": lambda: self.add("1"), "2": lambda: self.add("2"), "3": lambda: self.add("3"),
            "4": lambda: self.add("4"), "5": lambda: self.add("5"), "6": lambda: self.add("6"), "7": lambda: self.add("7"),
            "8": lambda: self.add("8"), "9": lambda: self.add("9")}, -1)
        self.update_label()

    def update_label(self):
        d = self.key + "_" * (16 - len(self.key))
        self["keylabel"].setText(" ".join([d[i:i+4] for i in range(0, 16, 4)]))

    def add(self, n):
        if len(self.key) < 16: self.key += n; self.update_label()

    def add_from_list(self):
        self.add(self["hexlist"].getCurrent())

    def backspace(self):
        if self.key: self.key = self.key[:-1]; self.update_label()

    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "16 digits required!", MessageBox.TYPE_ERROR)

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="v3.8 Blue Edition", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
