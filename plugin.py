# -*- coding: utf-8 -*-
# BissPro Manager v1.5 for OpenATV 7.6 (Python 3.12)
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_HALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve
import os, re, shutil

# تحديد المسارات
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
PLUGIN_ICON = os.path.join(PLUGIN_PATH, "plugin.png")
ICON_PATH = os.path.join(PLUGIN_PATH, "icons/")
BISS_FILE = "/etc/tuxbox/config/oscam/SoftCam.Key" if os.path.exists("/etc/tuxbox/config/oscam/") else "/etc/tuxbox/config/SoftCam.Key"

lock = Lock()

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
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v1.5">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(600)}" itemHeight="{self.ui.px(120)}" scrollbarMode="showOnDemand" transparent="1"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}" size="{self.ui.px(1060)},{self.ui.px(50)}" font="Regular;{self.ui.font(28)}" halign="center" transparent="1" foregroundColor="#f0a30a"/>
        </screen>"""
        
        self["status"] = Label("")
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)
        
        self.timer = eTimer()
        try: self.timer.callback.append(self.show_result)
        except: self.timer.timeout.connect(self.show_result)
        
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [("Add BISS Manually", "add", "add.png"), 
                 ("Update SoftCam.Key", "upd", "update.png"), 
                 ("Auto Add BISS", "auto", "autoadd.png")]
        lst = []
        for text, action, icon in items:
            p = os.path.join(ICON_PATH, icon)
            pix = LoadPixmap(p)
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10), self.ui.px(10)), size=(self.ui.px(100), self.ui.px(100)), png=pix),
                MultiContentEntryText(pos=(self.ui.px(130), self.ui.px(30)), size=(self.ui.px(800), self.ui.px(60)), font=0, text=text, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)
        if hasattr(self["menu"].l, 'setFont'):
            self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    def ok(self):
        curr = self["menu"].getCurrent()
        if not curr: return
        action = curr[0]
        service = self.session.nav.getCurrentService()
        if action == "add" and service:
            self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif action == "upd":
            self["status"].setText("Downloading SoftCam.Key...")
            Thread(target=self.do_update).start()
        elif action == "auto" and service:
            self["status"].setText("Searching Online Database...")
            Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key):
        if not key: return
        info = self.session.nav.getCurrentService().info()
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        if self.save_key(sid, key, info.getName()):
            self.res = (True, "BISS Key Saved & CAM Reloaded")
        else: self.res = (False, "Error: Could not write to file")
        self.timer.start(100, True)

    def save_key(self, sid, key, name):
        try:
            with lock:
                lines = open(BISS_FILE, "r").readlines() if os.path.exists(BISS_FILE) else []
                with open(BISS_FILE, "w") as f:
                    found = False
                    for l in lines:
                        if sid.upper() in l.upper() and l.strip().startswith("F"):
                            f.write(f"F {sid.upper()} 00000000 {key.upper()} ;{name}\n")
                            found = True
                        else: f.write(l)
                    if not found: f.write(f"F {sid.upper()} 00000000 {key.upper()} ;{name}\n")
            os.system("killall -HUP oscam ncam >/dev/null 2>&1")
            return True
        except: return False

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            os.system("killall -HUP oscam ncam >/dev/null 2>&1")
            self.res = (True, "SoftCam.Key Updated Successfully")
        except: self.res = (False, "Update Failed! Check Internet")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            sid = "%08X" % info.getInfo(iServiceInformation.sSID)
            raw = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt", timeout=10).read().decode("utf-8")
            m = re.search(sid + r'.*?([0-9A-Fa-f]{16})', raw, re.I)
            if m and self.save_key(sid, m.group(1), info.getName()):
                self.res = (True, f"Found Key: {m.group(1)}")
            else: self.res = (False, "No Key Found for this Channel")
        except: self.res = (False, "Server Connection Error")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("")

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(800)},{self.ui.px(600)}" title="BISS Key Input">
            <eLabel position="0,0" size="800,70" backgroundColor="#1a1a1a" zPosition="-1" />
            <widget name="keylabel" position="20,10" size="760,50" font="Regular;{self.ui.font(38)}" halign="center" valign="center" foregroundColor="#f0a30a" transparent="1"/>
            <widget name="hexlist" position="250,90" size="300,320" itemHeight="{self.ui.px(55)}" font="Regular;{self.ui.font(32)}" scrollbarMode="showOnDemand" transparent="1"/>
            <eLabel position="20,430" size="760,2" backgroundColor="#555555" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="40,460" size="30,30" alphatest="on" />
            <widget name="key_red" position="80,460" size="150,30" font="Regular;22" halign="left" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="280,460" size="30,30" alphatest="on" />
            <widget name="key_green" position="320,460" size="150,30" font="Regular;22" halign="left" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="520,460" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="560,460" size="150,30" font="Regular;22" halign="left" transparent="1" />
            <widget name="help" position="20,520" size="760,40" font="Regular;20" halign="center" foregroundColor="#cccccc" transparent="1"/>
        </screen>"""

        self.key = ""
        self["keylabel"] = Label("0000 0000 0000 0000")
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Save")
        self["key_yellow"] = Label("Delete")
        self["help"] = Label("Use OK to select | 0-9 for Direct Input")
        
        self["hexlist"] = MenuList(["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions"], {
            "ok": self.add, "cancel": self.close, "red": self.close, "green": self.save, "yellow": self.backspace,
            "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), "2": lambda: self.keyNum("2"),
            "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"),
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"),
            "9": lambda: self.keyNum("9")
        }, -1)

    def update_label(self):
        display = self.key + "_" * (16 - len(self.key))
        formatted = " ".join([display[i:i+4] for i in range(0, len(display), 4)])
        self["keylabel"].setText(formatted)

    def add(self):
        if len(self.key) < 16:
            self.key += self["hexlist"].getCurrent()
            self.update_label()

    def keyNum(self, num):
        if len(self.key) < 16:
            self.key += num
            self.update_label()

    def backspace(self):
        self.key = self.key[:-1]
        self.update_label()

    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "Key must be 16 digits!", MessageBox.TYPE_ERROR)

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name="BissPro", description="BISS Key Manager", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
