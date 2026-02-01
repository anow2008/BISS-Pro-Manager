# -*- coding: utf-8 -*-
# BissPro Manager v2.0 - Final Optimized Version
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_HALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve
import os, re, shutil

# المسارات الأساسية
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
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
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v2.0">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(550)}" itemHeight="{self.ui.px(110)}" scrollbarMode="showOnDemand" transparent="1"/>
            <eLabel position="{self.ui.px(50)},{self.ui.px(600)}" size="{self.ui.px(1000)},{self.ui.px(2)}" backgroundColor="#333333" />
            <widget name="progress" position="{self.ui.px(50)},{self.ui.px(620)}" size="{self.ui.px(1000)},{self.ui.px(15)}" borderWidth="1" borderColor="#555555" transparent="1" />
            <widget name="status" position="{self.ui.px(50)},{self.ui.px(650)}" size="{self.ui.px(1000)},{self.ui.px(60)}" font="Regular;{self.ui.font(30)}" halign="center" valign="center" transparent="1" foregroundColor="#f0a30a"/>
        </screen>"""

        self["status"] = Label("Ready")
        self["progress"] = ProgressBar()
        self["progress"].setRange(0, 100)
        self["progress"].setValue(0)
        
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.safe_exit, "up": self["menu"].up, "down": self["menu"].down
        }, -1)
        
        self.timer = eTimer()
        try: self.timer.callback.append(self.show_result)
        except: self.timer.timeout.connect(self.show_result)
        
        self.prog_timer = eTimer()
        try: self.prog_timer.callback.append(self.anim_progress)
        except: self.prog_timer.timeout.connect(self.anim_progress)
        
        self.onLayoutFinish.append(self.build_menu)

    def anim_progress(self):
        curr = self["progress"].getValue()
        if curr < 90: self["progress"].setValue(curr + 5)

    def safe_exit(self):
        self.prog_timer.stop()
        self.timer.stop()
        self.close()

    def build_menu(self):
        items = [("Add BISS Manually", "add", "add.png"), 
                 ("Update SoftCam.Key", "upd", "update.png"), 
                 ("Auto Add BISS", "auto", "autoadd.png")]
        lst = []
        for text, action, icon in items:
            p = os.path.join(ICON_PATH, icon)
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10), self.ui.px(10)), size=(self.ui.px(90), self.ui.px(90)), png=LoadPixmap(p)),
                MultiContentEntryText(pos=(self.ui.px(120), self.ui.px(25)), size=(self.ui.px(800), self.ui.px(55)), font=0, text=text, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER)
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
        elif action in ["upd", "auto"]:
            self["progress"].setValue(0)
            self.prog_timer.start(100, False)
            if action == "upd":
                self["status"].setText("Downloading SoftCam...")
                Thread(target=self.do_update).start()
            else:
                self["status"].setText("Searching Online Database...")
                Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key=None):
        if key is None or key == "": return
        info = self.session.nav.getCurrentService().info()
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        if self.save_key(sid, key, info.getName()):
            self.res = (True, "BISS Key Saved & CAM Reloaded")
        else: self.res = (False, "Error: File write failed")
        self.timer.start(100, True)

    def save_key(self, sid, key, name):
        try:
            with lock:
                lines = open(BISS_FILE, "r").readlines() if os.path.exists(BISS_FILE) else []
                with open(BISS_FILE, "w") as f:
                    found = False
                    for l in lines:
                        if sid.upper() in l.upper() and l.strip().startswith("F"):
                            f.write(f"F {sid.upper()} 00000000 {key.upper()} ;{name}\n"); found = True
                        else: f.write(l)
                    if not found: f.write(f"F {sid.upper()} 00000000 {key.upper()} ;{name}\n")
            os.system("killall -HUP oscam ncam >/dev/null 2>&1")
            return True
        except: return False

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            self.res = (True, "Updated Successfully")
        except: self.res = (False, "Update Failed")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            sid = "%08X" % info.getInfo(iServiceInformation.sSID)
            raw = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt", timeout=10).read().decode("utf-8")
            m = re.search(sid + r'.*?([0-9A-Fa-f]{16})', raw, re.I)
            if m and self.save_key(sid, m.group(1), info.getName()):
                self.res = (True, f"Found: {m.group(1)}")
            else: self.res = (False, "Key Not Found")
        except: self.res = (False, "Connection Error")
        self.timer.start(100, True)

    def show_result(self):
        self.prog_timer.stop()
        self["progress"].setValue(100)
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready")
        self["progress"].setValue(0)

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(850)},{self.ui.px(600)}" title="Enter BISS Key">
            <eLabel position="0,0" size="850,85" backgroundColor="#1a1a1a" zPosition="-1" />
            <widget name="keylabel" position="20,15" size="810,55" font="Regular;{self.ui.font(46)}" halign="center" valign="center" foregroundColor="#f0a30a" transparent="1"/>
            <widget name="hexlist" position="275,100" size="300,320" itemHeight="{self.ui.px(65)}" font="Regular;{self.ui.font(38)}" transparent="1" selectionPixmap="skin_default/menu_sel.png"/>
            <eLabel position="40,440" size="770,2" backgroundColor="#444444" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="60,470" size="30,30" alphatest="on" />
            <widget name="key_red" position="100,470" size="160,30" font="Regular;24" halign="left" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="310,470" size="30,30" alphatest="on" />
            <widget name="key_green" position="350,470" size="160,30" font="Regular;24" halign="left" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="560,470" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="600,470" size="160,30" font="Regular;24" halign="left" transparent="1" />
            <widget name="help" position="20,535" size="810,40" font="Regular;22" halign="center" foregroundColor="#999999" transparent="1"/>
        </screen>"""
        self.key = ""
        self["keylabel"] = Label("____ ____ ____ ____")
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Save")
        self["key_yellow"] = Label("Delete")
        self["help"] = Label("OK: Select | 0-9: Type Directly")
        self["hexlist"] = MenuList(["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions"], {
            "ok": self.add, "cancel": lambda: self.close(None), "red": lambda: self.close(None),
            "green": self.save, "yellow": self.backspace,
            "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), "2": lambda: self.keyNum("2"),
            "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"),
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"),
            "9": lambda: self.keyNum("9")
        }, -1)

    def update_label(self):
        d = self.key + "_" * (16 - len(self.key))
        self["keylabel"].setText(" ".join([d[i:i+4] for i in range(0, 16, 4)]))

    def add(self):
        if len(self.key) < 16: self.key += self["hexlist"].getCurrent(); self.update_label()
    def keyNum(self, n):
        if len(self.key) < 16: self.key += n; self.update_label()
    def backspace(self):
        if self.key: self.key = self.key[:-1]; self.update_label()
    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "Incomplete Key!", MessageBox.TYPE_ERROR)

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name="BissPro", description="BISS Key Manager v2.0", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
