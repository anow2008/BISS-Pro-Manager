# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve
import os, re, shutil
import subprocess

PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.0"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"
PLUGIN_ICON = ICON_PATH + "plugin.png"
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

lock = Lock()

# ======== Auto Scale ========
class AutoScale:
    BASE_W = 1920.0
    BASE_H = 1080.0
    def __init__(self):
        d = getDesktop(0).size()
        self.w = d.width()
        self.h = d.height()
        self.scale = min(self.w / self.BASE_W, self.h / self.BASE_H)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(18, v * self.scale))

# ======== Utils ========
def get_key_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def extract_biss_key_from_block(block):
    if len(block) < 4:
        return None
    raw_key_line = block[3]
    clean = re.sub(r'[^0-9A-Fa-f ]', '', raw_key_line)
    parts = clean.split()
    if len(parts) == 8:
        return ''.join(parts).upper()
    return None

def restart_softcam():
    softcams = ["oscam", "cccam", "mgcamd", "ncamd"]  # كل SoftCam محتمل
    for sc in softcams:
        try:
            subprocess.call(["killall", "-HUP", sc])
        except Exception as e:
            print(f"Restart {sc} failed:", e)

# ======== Main Screen ========
class BISSPro(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(600)}" itemHeight="{self.ui.px(120)}"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}" size="{self.ui.px(1060)},{self.ui.px(50)}" font="Regular;{self.ui.font(28)}" halign="center"/>
        </screen>"""
        Screen.__init__(self, session)

        self.update_menu()
        self["status"] = Label("")
        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {"ok": self.ok,"cancel":self.close,"up":self["menu"].up,"down":self["menu"].down}, -1
        )
        self.timer = eTimer()
        self.timer.callback.append(self.show_result)

    def update_status(self, text):
        self["status"].setText(text)

    def update_menu(self):
        items = [
            ("Add BISS Manually", "add", ICON_PATH + "add.png"),
            ("Update SoftCam.Key", "upd", ICON_PATH + "update.png"),
            ("Auto Add BISS", "autoadd", ICON_PATH + "autoadd.png")
        ]

        self.menu_list = []
        for t, a, p in items:
            self.menu_list.append((a, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10), self.ui.px(10)), size=(self.ui.px(100), self.ui.px(100)), png=LoadPixmap(p)),
                MultiContentEntryText(pos=(self.ui.px(130), self.ui.px(30)), size=(self.ui.px(800), self.ui.px(60)), font=0, text=t)
            ]))
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    def ok(self):
        action = self["menu"].getCurrent()[0]
        service = self.session.nav.getCurrentService()
        if action == "add": 
            self.session.openWithCallback(self.manual_add_callback, InputBox, title="Enter BISS Key", text="")
        elif action == "upd": 
            Thread(target=self.do_upd).start()
        elif action == "autoadd" and service: 
            Thread(target=self.do_auto_add, args=(service,)).start()

    def manual_add_callback(self, result):
        if result:
            service = self.session.nav.getCurrentService()
            if service:
                self.update_status("Adding BISS key manually...")
                sid = "%08X" % service.info().getInfo(iServiceInformation.sSID)
                name = service.info().getName()
                key = re.sub(r'[^0-9A-Fa-f]', '', result.strip()).upper()
                if len(key) == 16:
                    try:
                        with lock:
                            with open(BISS_FILE, "a+") as f:
                                f.write(f"\nF {sid} 00000000 {key} ;{name}\n")
                        self.update_status("Restarting SoftCam...")
                        restart_softcam()
                        self.res = (True, f"Added BISS key for {name}")
                    except:
                        self.res = (False, "Failed to write key")
                else:
                    self.res = (False, "Invalid key format")
                self.timer.start(100, True)

    def do_upd(self):
        try:
            self.update_status("Updating SoftCam.Key...")
            urlretrieve(UPDATE_URL, "/tmp/S.Key")
            shutil.copy("/tmp/S.Key", BISS_FILE)
            self.update_status("Restarting SoftCam...")
            restart_softcam()
            self.res = (True, "SoftCam.Key updated successfully")
        except:
            self.res = (False, "Failed to update SoftCam.Key")
        self.timer.start(100, True)

    def do_auto_add(self, service):
        try:
            self.update_status("Auto adding BISS key...")
            info = service.info()
            sid = "%08X" % info.getInfo(iServiceInformation.sSID)
            name = info.getName()
            freq = str(info.getInfo(iServiceInformation.sTransponderData))

            raw = urlopen(BISS_TXT_URL, timeout=10).read().decode("utf-8","replace")
            lines = raw.splitlines()
            found = False

            for i in range(0, len(lines), 4):
                block = lines[i:i+4]
                if len(block) < 4: continue
                file_freq = re.sub(r'[^0-9]', '', block[1])
                file_name = re.sub(r'[^A-Za-z0-9 ]', '', block[2])
                if freq == file_freq and name.replace(" ","") == file_name.replace(" ",""):
                    key = extract_biss_key_from_block(block)
                    if key:
                        with lock:
                            with open(BISS_FILE, "a+") as f:
                                f.write(f"\nF {sid} 00000000 {key} ;{name}\n")
                        found = True
                        break
            if found:
                self.update_status("Restarting SoftCam...")
                restart_softcam()
                self.res = (True, "BISS key added automatically")
            else:
                self.res = (False, "No key found")
        except Exception as e:
            print("BISS ERROR:", e)
            self.res = (False, "Auto add failed")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, 5)
        self.update_status("")  # رجع شريط الحالة فاضي بعد الرسالة

# ======== Entry Points ========
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description=f"BissPro Manager {PLUGIN_VERSION}",
            icon=PLUGIN_ICON,
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        )
    ]
