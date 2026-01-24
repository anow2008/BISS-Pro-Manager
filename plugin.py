# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont
from Tools.LoadPixmap import LoadPixmap
import os, time, shutil
from datetime import datetime

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
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def create_backup():
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        return b
    return None

def restartSoftcam():
    cams = ["oscam","ncam","gcam","revcam","vicard"]
    active = None
    for cam in cams:
        if os.system("pgrep -x %s >/dev/null 2>&1" % cam) == 0:
            active = cam
            break

    for cam in cams:
        os.system("killall -9 %s 2>/dev/null" % cam)

    time.sleep(1)
    cam_to_run = active if active else "oscam"
    path = "/usr/bin/" + cam_to_run
    if os.path.exists(path):
        os.system("%s -b &" % path)
    else:
        os.system("%s -b &" % cam_to_run)

# ===== Key Selection Screen =====
class SelectKeyScreen(Screen):
    skin = """
    <screen position="center,center" size="720,420" title="Select BISS Key">
        <widget name="list" position="20,20" size="680,320"/>
        <widget name="info" position="20,360" size="680,40" font="Regular;22" halign="center"/>
    </screen>
    """
    def __init__(self, session, sid, callback):
        Screen.__init__(self, session)
        self.sid = sid
        self.callback = callback
        self["list"] = MenuList([])
        self["info"] = Label("OK: Select | RED: Cancel")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"ok": self.ok, "red": self.close, "cancel": self.close}, -1)
        self.load()

    def load(self):
        items = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                for l in f:
                    l = l.strip()
                    if l.upper().startswith("F %s " % self.sid.upper()):
                        parts = l.split()
                        key = parts[3] if len(parts) > 3 else "???"
                        service_name = parts[2] if len(parts) > 2 else "Unknown"
                        items.append((l, "SID:%s | %s | KEY:%s" % (self.sid, service_name, key)))
        self["list"].setList(items)

    def ok(self):
        sel = self["list"].getCurrent()
        if sel:
            self.close()
            self.callback(sel[0])

# ===== BISS Key Editor =====
class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="820,300" title="BISS Editor">
        <widget name="key" position="110,100" size="600,80" font="Console;50" halign="center" valign="center" foregroundColor="#ffffff"/>
        <widget name="hexlist" position="720,100" size="80,200" itemHeight="40"/>
        <widget name="info" position="110,200" size="600,60" font="Regular;22" halign="center"/>
    </screen>
    """
    def __init__(self, session, sid, mode="add", key_line=None):
        Screen.__init__(self, session)
        self.sid = sid
        self.mode = mode
        self.key_line = key_line
        self.chars = ["A","B","C","D","E","F"]
        self.key = list("0000000000000000")
        self.pos = 0
        if key_line: self.load_from_line()

        self["key"] = Label("")
        self["hexlist"] = MenuList([(c,c) for c in self.chars])
        self["info"] = Label("Arrows: Move/Change | Numbers: Direct Input | GREEN: Save")
        self["actions"] = ActionMap(["DirectionActions","NumberActions","ColorActions","OkCancelActions"],{
            "left": self.left, "right": self.right, "up": self.up, "down": self.down,
            "ok": self.select_hex, "green": self.save, "cancel": self.close,
            **{str(i):(lambda x=str(i): self.set_num(x)) for i in range(10)}
        }, -1)
        self.refresh()

    def load_from_line(self):
        try:
            self.key = list(self.key_line.split()[3])[:16]
        except:
            pass

    def refresh(self):
        res = "".join(["[%s]" % c if i==self.pos else " %s " % c for i,c in enumerate(self.key)])
        self["key"].setText(res)

    def left(self): self.pos = (self.pos - 1) % 16; self.refresh()
    def right(self): self.pos = (self.pos + 1) % 16; self.refresh()
    def up(self): self.set_char(self.chars[(self.chars.index(self.key[self.pos])+1)%6])
    def down(self): self.set_char(self.chars[(self.chars.index(self.key[self.pos])-1)%6])
    def set_char(self, c): self.key[self.pos]=c; self.right()
    def set_num(self, c): self.key[self.pos]=c; self.right()
    def select_hex(self):
        sel = self["hexlist"].getCurrent()
        if sel: self.set_char(sel[0])

    def save(self):
        new_line = "F %s 00 %s ;BissPro" % (self.sid, "".join(self.key))
        create_backup()
        lines = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE,"r") as f: lines = [l.strip() for l in f]
        with open(BISS_FILE,"w") as f:
            for l in lines:
                if self.mode=="edit" and self.key_line and l.strip()==self.key_line.strip(): continue
                f.write(l+"\n")
            f.write(new_line+"\n")
        restartSoftcam()
        self.session.openWithCallback(self.close, MessageBox, "Key Saved & Softcam Restarted!", MessageBox.TYPE_INFO, timeout=3)

# ===== Main Plugin Screen (متوافق مع icons 128x128 + شاشة أكبر) =====
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1024,768" title="BissPro v1.0">
        <widget name="menu" position="40,100" size="940,540" itemHeight="150" scrollbarMode="showOnDemand"/>
        <widget name="status" position="40,660" size="940,50" font="Regular;32" halign="center"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["status"] = Label("Ready")

        self.menu_items = [
            ("Add Key (Current Channel)","add","add.png"),
            ("Edit Key (Current SID)","edit","edit.png"),
            ("Delete Key (Current SID)","delete","delete.png"),
            ("Online Update SoftCam.Key","update","update.png"),
        ]

        self.menu_list = []
        for text, action, icon in self.menu_items:
            pix = LoadPixmap(ICON_PATH + icon)
            self.menu_list.append((
                action,
                [
                    MultiContentEntryPixmapAlphaTest(pos=(10,10), size=(128,128), png=pix),
                    MultiContentEntryText(pos=(160,50), size=(760,60), font=0, text=text)
                ]
            ))

        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular",32))

        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            },
            -1
        )

    def ok(self):
        sel = self["menu"].getCurrent()
        if sel:
            action = sel[0]
            service = self.session.nav.getCurrentService()
            if not service: return
            sid = "%04X" % service.info().getInfo(iServiceInformation.sSID)
            if action=="add":
                self.session.open(EasyBissInput,sid)
            elif action=="update":
                self.start_update()
            else:
                self.session.open(SelectKeyScreen, sid, lambda line: self.handle(action,sid,line))

    def handle(self,action,sid,line):
        if action=="edit":
            self.session.open(EasyBissInput,sid,"edit",line)
        elif action=="delete":
            create_backup()
            with open(BISS_FILE,"r") as f: lines=f.readlines()
            with open(BISS_FILE,"w") as f:
                for l in lines:
                    if l.strip()!=line.strip(): f.write(l)
            self.session.open(MessageBox,"Key Deleted Successfully",MessageBox.TYPE_INFO,timeout=3)

    def start_update(self):
        create_backup()
        try:
            urlretrieve(UPDATE_URL,"/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key",BISS_FILE)
            self.session.open(MessageBox,"SoftCam Updated Successfully!",MessageBox.TYPE_INFO,timeout=4)
        except Exception as e:
            self.session.open(MessageBox,"Update Failed: %s" % str(e),MessageBox.TYPE_ERROR)

# ===== Plugin Entry =====
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Professional BISS Manager", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="plugin.png")]
