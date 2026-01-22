# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont
from Tools.LoadPixmap import LoadPixmap
import os, time, shutil

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.0"
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"

def get_key_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key",
             "/usr/keys/SoftCam.Key", "/var/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def restartSoftcam():
    cams = ["oscam","ncam","gcam","revcam","vicard"]
    active = None
    for cam in cams:
        if os.system("pgrep -x %s >/dev/null 2>&1" % cam) == 0:
            active = cam
            break
    os.system("killall -q " + " ".join(cams) + " 2>/dev/null")
    time.sleep(1)
    os.system("%s -b &" % (active if active else "oscam"))

class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="900,520" title="BISS Key Editor" backgroundColor="#0e1117">
        <eLabel position="0,0" size="900,80" backgroundColor="#161b22"/>
        <widget name="info" position="50,100" size="800,40" font="Regular;28" halign="center" foregroundColor="#58a6ff" transparent="1"/>
        <widget name="keyline" position="120,185" size="660,80" font="Console;70" halign="center" foregroundColor="#3fb950" transparent="1"/>
        <eLabel text="RED: EXIT  |  GREEN: SAVE  |  OK: HEX (A-F)" position="50,450" size="800,40" font="Regular;24" halign="center" transparent="1"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.key = list("0000000000000000")
        self.pos, self.hex_index = 0, 0
        self.hex_chars = ["A","B","C","D","E","F"]
        s = session.nav.getCurrentService()
        self.sid = "%04X"%s.info().getInfo(iServiceInformation.sSID) if s else "0000"
        self["keyline"] = Label("")
        self["info"] = Label("Target Channel SID: %s" % self.sid)
        self["actions"] = ActionMap(["OkCancelActions","ColorActions","DirectionActions","NumberActions"],{
            "ok": self.toggle_hex, "left": self.prev, "right": self.next, "green": self.save_key, "red": self.close, "cancel": self.close,
            **{str(i):(lambda x=str(i): self.set_char(x)) for i in range(10)}
        },-1)
        self.refresh()

    def refresh(self):
        self["keyline"].setText("".join("[%s]"%c if i==self.pos else " %s "%c for i,c in enumerate(self.key)))

    def set_char(self, c):
        self.key[self.pos] = c
        self.next()

    def toggle_hex(self):
        self.key[self.pos] = self.hex_chars[self.hex_index]
        self.hex_index = (self.hex_index + 1) % 6
        self.refresh()

    def next(self):
        self.pos = (self.pos + 1) % 16
        self.refresh()

    def save_key(self):
        new_line = "F %s0000 00 %s ;BissPro\n" % (self.sid, "".join(self.key))
        try:
            # اقرأ محتويات الملف أولاً
            existing_lines = []
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE, "r") as f:
                    existing_lines = [l.strip() for l in f]

            # تحقق إذا المفتاح موجود مسبقاً
            if new_line.strip() in existing_lines:
                self["info"].setText("Key Already Exists!")
                return  # لا تضيف المفتاح

            # أضف المفتاح الجديد
            with open(BISS_FILE, "a") as f:
                f.write(new_line)

            restartSoftcam()
            self.close()
        except Exception as e:
            self["info"].setText("Error Saving Key")
            self.close()

class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="900,540" title="BissPro Manager" backgroundColor="#0e1117">
        <eLabel position="0,0" size="900,70" backgroundColor="#161b22"/>
        <eLabel text="BissPro Controller" position="30,15" size="840,40" font="Regular;32" foregroundColor="#58a6ff" transparent="1"/>
        <widget name="menu" position="30,100" size="840,320" itemHeight="140" scrollbarMode="showOnDemand" transparent="1"/>
        <widget name="status" position="50,470" size="800,40" font="Regular;24" foregroundColor="#3fb950" halign="center" transparent="1"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["status"] = Label("Ready")
        menu_items = [
            ("add.png", "➕ Add Key (Current Channel)", "add"),
            ("update.png", "🌐 Online Update SoftCam", "update"),
            ("restart.png", "♻️ Restart Softcam", "restart"),
            ("count.png", "📊 Count Total Keys", "count")
        ]
        self.menu_list = []
        for icon_file, text, action in menu_items:
            pix = LoadPixmap(ICON_PATH + icon_file)
            self.menu_list.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(10, 5), size=(128, 128), png=pix),
                MultiContentEntryText(pos=(150, 45), size=(650, 50), font=0, text=text)
            ]))
        
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setItemHeight(140)
        self["menu"].l.setFont(0, gFont("Regular", 28))
        
        self["actions"] = ActionMap(["OkCancelActions","DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down
        }, -1)

    def ok(self):
        sel = self["menu"].getCurrent()
        if sel:
            action = sel[0]
            if action == "add": self.session.open(EasyBissInput)
            elif action == "update": self.start_update()
            elif action == "restart":
                restartSoftcam()
                self["status"].setText("Softcam Restarted!")
            elif action == "count":
                if os.path.exists(BISS_FILE):
                    with open(BISS_FILE) as f:
                        c = sum(1 for l in f if l.upper().startswith("F "))
                    self["status"].setText("Total Keys Found: %d" % c)

    def start_update(self):
        self["status"].setText("Updating Online...")
        try:
            urlretrieve(UPDATE_URL, "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            restartSoftcam()
            self["status"].setText("Update Successful!")
        except:
            self["status"].setText("Update Failed!")

def main(session, **kwargs): 
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="BISS Key Manager",
                             where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="plugin.png")]
