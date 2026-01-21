# -*- coding: utf-8 -*-
from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eTimer, iServiceInformation
import os, time, threading

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.0"

SOFTCAM_PATHS = [
    "/etc/tuxbox/config/oscam/SoftCam.Key",
    "/etc/tuxbox/config/SoftCam.Key",
    "/usr/keys/SoftCam.Key",
    "/var/keys/SoftCam.Key"
]

def get_key_path():
    for p in SOFTCAM_PATHS:
        if os.path.exists(p):
            return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

def restartSoftcam():
    os.system("killall -15 oscam ncam gcam 2>/dev/null")
    time.sleep(2)
    os.system("killall -9 oscam ncam gcam 2>/dev/null")

def get_existing_key(sid):
    if not os.path.exists(BISS_FILE):
        return None
    try:
        sid_hex = "%04X" % int(sid)
        with open(BISS_FILE, "r") as f:
            for line in f:
                if line.upper().startswith("F %s" % sid_hex):
                    parts = line.split()
                    for p in parts:
                        if len(p) == 16:
                            return p
    except:
        pass
    return None

# ================= Easy Input Screen =================

class EasyBissInput(Screen):
    skin = """
    <screen name="EasyBissInput" position="center,center" size="720,320" title="Enter BISS Key">
        <widget name="title" position="20,10" size="680,40" font="Regular;32" halign="center" foregroundColor="#00aaff"/>
        <widget name="keyline" position="30,80" size="660,60" font="Regular;36" halign="center" foregroundColor="#00ff00"/>
        <widget name="hint" position="20,160" size="680,40" font="Regular;22" halign="center" foregroundColor="#aaaaaa"/>
        <widget name="keys" position="20,210" size="680,40" font="Regular;20" halign="center" foregroundColor="#ffffff"/>
    </screen>
    """

    def __init__(self, session, current_key=None):
        Screen.__init__(self, session)
        self.key = list(current_key if (current_key and len(current_key) == 16) else "0000000000000000")
        self.pos = 0
        self["title"] = Label("Edit BISS Key")
        self["hint"] = Label("◀ ▶ Move   ▲ ▼ Change   0-9 Direct")
        self["keys"] = Label("🟢 Save    🟡 Clear    🔴 Cancel")
        self["keyline"] = Label("")
        self.refresh()
        self["actions"] = ActionMap(
            ["ColorActions", "DirectionActions", "NumberActions", "OkCancelActions"],
            {
                "left": self.left, "right": self.right, "up": self.up, "down": self.down,
                "0": lambda: self.set_char("0"), "1": lambda: self.set_char("1"),
                "2": lambda: self.set_char("2"), "3": lambda: self.set_char("3"),
                "4": lambda: self.set_char("4"), "5": lambda: self.set_char("5"),
                "6": lambda: self.set_char("6"), "7": lambda: self.set_char("7"),
                "8": lambda: self.set_char("8"), "9": lambda: self.set_char("9"),
                "green": self.save, "yellow": self.clear,
                "red": self.close, "cancel": self.close,
            }, -1)

    def refresh(self):
        txt = ""
        for i, c in enumerate(self.key):
            txt += "[%s] " % c if i == self.pos else " %s  " % c
        self["keyline"].setText(txt)

    def left(self): self.pos = (self.pos - 1) % 16; self.refresh()
    def right(self): self.pos = (self.pos + 1) % 16; self.refresh()
    def up(self):
        v = (int(self.key[self.pos], 16) + 1) % 16
        self.key[self.pos] = "%X" % v
        self.refresh()
    def down(self):
        v = (int(self.key[self.pos], 16) - 1) % 16
        self.key[self.pos] = "%X" % v
        self.refresh()
    def set_char(self, ch):
        self.key[self.pos] = ch
        self.right()
    def clear(self):
        self.key = list("0000000000000000")
        self.pos = 0
        self.refresh()
    def save(self):
        self.close("".join(self.key))

# ================= Main Screen =================

class BISSPro(Screen):
    skin = """
    <screen name="BISSPro" position="center,center" size="800,500" title="BissPro v1.0">
        <widget name="title" position="20,10" size="760,50" font="Regular;36" halign="center" foregroundColor="#00aaff"/>
        <widget name="menu" position="120,90" size="560,240" font="Regular;28" itemHeight="60"/>
        <widget name="progress" position="80,350" size="640,18"/>
        <widget name="status" position="40,380" size="720,90" font="Regular;24" halign="center" foregroundColor="#ffffff"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [
            ("⬇️ Update Softcam Online", "update"),
            ("➕ Add/Edit BISS Key", "add"),
            ("🔄 Restart Softcam", "restart"),
            ("📊 Keys Count", "count"),
        ]
        self["title"] = Label("BissPro v1.0 | Smart Editor")
        self["menu"] = MenuList(self.menu_items)
        self["status"] = Label("Select option")
        self["progress"] = ProgressBar()
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok, "cancel": self.close,
                "up": self["menu"].up, "down": self["menu"].down
            }, -1)

    def ok(self):
        cmd = self["menu"].getCurrent()[1]
        if cmd == "update": self.start_update()
        elif cmd == "restart":
            restartSoftcam()
            self["status"].setText("♻️ Softcam Restarted")
        elif cmd == "count":
            count = 0
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE, "r") as f:
                    count = sum(1 for l in f if l.upper().startswith("F "))
            self["status"].setText("📊 Total Keys in File: %d" % count)
        elif cmd == "add":
            self.add_key()

    def add_key(self):
        s = self.session.nav.getCurrentService()
        if not s:
            self["status"].setText("❌ Error: No active channel found")
            return
        sid = s.info().getInfo(iServiceInformation.sSID)
        old = get_existing_key(sid)
        self.session.openWithCallback(self.save_key, EasyBissInput, old)

    def save_key(self, key):
        if not key:
            return
        s = self.session.nav.getCurrentService().info()
        sid_hex = "%04X" % s.getInfo(iServiceInformation.sSID)
        name = s.getName()
        line = "F %s1FFF 00 %s ; %s\n" % (sid_hex, key, name)

        parent_dir = os.path.dirname(BISS_FILE)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        lines = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                lines = [l for l in f if not l.upper().startswith("F %s" % sid_hex)]

        lines.append(line)
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)

        restartSoftcam()
        self["status"].setText("✅ Key Saved for: %s" % name)

    def start_update(self):
        self["status"].setText("⬇️ Downloading...")
        self["progress"].setValue(10)
        threading.Thread(target=self.update_process).start()

    def update_process(self):
        try:
            urlretrieve(UPDATE_URL, BISS_FILE)
            eTimer.singleShot(100, lambda: self["status"].setText("✅ Online Update Success"))
            eTimer.singleShot(100, lambda: self["progress"].setValue(100))
            restartSoftcam()
        except:
            eTimer.singleShot(100, lambda: self["status"].setText("❌ Download Failed! Check Internet"))

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="Edit BISS Key or Update Online v1.0",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        )
    ]
