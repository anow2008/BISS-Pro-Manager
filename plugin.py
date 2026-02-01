# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve, Request
import os, re, shutil

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
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(600)}" itemHeight="{self.ui.px(120)}" scrollbarMode="showOnDemand" transparent="1"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}" size="{self.ui.px(1060)},{self.ui.px(50)}" font="Regular;{self.ui.font(28)}" halign="center" transparent="1"/>
        </screen>"""
        
        self["status"] = Label()
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)
        
        # حل مشكلة التايمر - الطريقة الأكثر أماناً لـ OpenATV 7.6
        self.timer = eTimer()
        try:
            self.timer.callback.append(self.show_result)
        except:
            self.timer_conn = self.timer.timeout.connect(self.show_result)
        
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [("Add BISS Manually", "add", "add.png"), 
                 ("Update SoftCam.Key", "upd", "update.png"), 
                 ("Auto Add BISS", "auto", "autoadd.png")]
        lst = []
        for text, action, icon in items:
            p = os.path.join(ICON_PATH, icon)
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10), self.ui.px(10)), size=(self.ui.px(100), self.ui.px(100)), png=LoadPixmap(p)),
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
            self["status"].setText("Updating...")
            Thread(target=self.do_update).start()
        elif action == "auto" and service:
            self["status"].setText("Searching...")
            Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key):
        if not key: return
        info = self.session.nav.getCurrentService().info()
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        if self.save_key(sid, key, info.getName()):
            self.res = (True, "Key Saved!")
        else: self.res = (False, "Error Saving")
        self.timer.start(100, True)

    def save_key(self, sid, key, name):
        try:
            with lock:
                lines = open(BISS_FILE, "r").readlines() if os.path.exists(BISS_FILE) else []
                with open(BISS_FILE, "w") as f:
                    found = False
                    for l in lines:
                        if sid in l.upper():
                            f.write(f"F {sid} 00000000 {key} ;{name}\n")
                            found = True
                        else: f.write(l)
                    if not found: f.write(f"F {sid} 00000000 {key} ;{name}\n")
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
                self.res = (True, "Auto-Added!")
            else: self.res = (False, "No Key Found")
        except: self.res = (False, "Connection Error")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("")

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(700)},{self.ui.px(500)}" title="Enter BISS">
            <widget name="keylabel" position="0,30" size="700,50" font="Regular;32" halign="center"/>
            <widget name="hexlist" position="150,100" size="400,260" itemHeight="50"/>
        </screen>"""
        self.key = ""
        self["keylabel"] = Label("Key: " + "_"*16)
        self["hexlist"] = MenuList(["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"ok": self.add, "cancel": self.close, "green": self.save}, -1)
    def add(self):
        if len(self.key) < 16:
            self.key += self["hexlist"].getCurrent()
            self["keylabel"].setText("Key: " + self.key + "_"*(16-len(self.key)))
    def save(self):
        if len(self.key) == 16: self.close(self.key)

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name="BissPro", description="Manager", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
