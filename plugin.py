# -*- coding: utf-8 -*-
from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eTimer, iServiceInformation
import os, shutil, time, threading

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
    os.system("killall -15 oscam ncam 2>/dev/null")
    time.sleep(2)
    os.system("killall -9 oscam ncam 2>/dev/null")

def get_existing_key(sid):
    if not os.path.exists(BISS_FILE): return None
    sid_hex = "%04X" % sid
    try:
        with open(BISS_FILE, "r") as f:
            for line in f:
                if sid_hex in line and len(line.strip()) > 16:
                    parts = line.strip().split()
                    if parts:
                        potential_key = parts[-1]
                        if len(potential_key) == 16: return potential_key
    except: pass
    return None

def read_all_keys():
    keys = []
    if not os.path.exists(BISS_FILE): return keys
    with open(BISS_FILE, "r") as f:
        for line in f:
            if line.startswith("F "):
                parts = line.strip().split()
                if len(parts) >= 4:
                    sid = parts[1][:4]
                    key = parts[3]
                    keys.append((sid, key))
    return keys

class ShowKeysScreen(Screen):
    skin = """
    <screen name="ShowKeysScreen" position="center,center" size="820,520" title="All Keys">
        <widget name="title" position="20,20" size="780,60" font="Regular;34" halign="center" foregroundColor="#00aaff"/>
        <widget name="list" position="40,100" size="740,340" font="Regular;24" itemHeight="40" foregroundColor="#ffffff" selectionColor="#00aaff"/>
        <widget name="hint" position="40,450" size="740,60" font="Regular;20" halign="center" foregroundColor="#aaaaaa"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["title"] = Label("All Keys in SoftCam.Key")
        self["hint"] = Label("Press Red to exit")
        self["list"] = MenuList(read_all_keys())
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "cancel": self.close, "red": self.close, "up": self["list"].up, "down": self["list"].down
        }, -1)

class BissInputScreen(Screen):
    skin = """
    <screen name="BissInputScreen" position="center,center" size="860,560" title="Biss Key Input">
        <widget name="bg1" position="0,0" size="860,560" backgroundColor="#000000"/>
        <eLabel position="40,110" size="780,380" backgroundColor="#1b1b1b" />
        <widget name="title" position="40,30" size="780,60" font="Regular;36" halign="center" foregroundColor="#00aaff"/>
        <widget name="channel" position="60,130" size="720,40" font="Regular;26" halign="center" foregroundColor="#ffffff"/>
        <widget name="ids" position="60,175" size="720,35" font="Regular;22" halign="center" foregroundColor="#00ffcc"/>
        <widget name="existing" position="60,215" size="720,30" font="Regular;20" halign="center" foregroundColor="#ffaa00"/>
        <eLabel position="120,250" size="540,180" backgroundColor="#0f0f0f" />
        <widget name="line1" position="140,270" size="500,40" font="Regular;32" halign="center" foregroundColor="#00ff00"/>
        <widget name="line2" position="140,310" size="500,40" font="Regular;32" halign="center" foregroundColor="#00ff00"/>
        <widget name="line3" position="140,350" size="500,40" font="Regular;32" halign="center" foregroundColor="#00ff00"/>
        <widget name="line4" position="140,390" size="500,40" font="Regular;32" halign="center" foregroundColor="#00ff00"/>
        <widget name="letters" position="690,270" size="140,200" font="Regular;26" halign="left" foregroundColor="#0000ff"/>
        <widget name="hint" position="60,455" size="740,60" font="Regular;20" halign="center" foregroundColor="#aaaaaa"/>
    </screen>
    """

    def __init__(self, session, channel_name="", sid=0, tsid=0, onid=0):
        Screen.__init__(self, session)
        self.channel_name = channel_name
        self.sid = sid
        self.tsid = tsid
        self.onid = onid
        self.lines = ["0000", "0000", "0000", "0000"]
        self.current, self.pos = 0, 0

        existing = get_existing_key(sid)
        if existing:
            self.lines = [existing[0:4], existing[4:8], existing[8:12], existing[12:16]]

        self["title"] = Label("Enter BISS Key")
        self["channel"] = Label("Channel: %s" % self.channel_name)
        self["ids"] = Label("SID:%04X  TSID:%04X  ONID:%04X" % (sid, tsid, onid))
        self["existing"] = Label("Current: %s" % (existing if existing else "None"))
        self["letters"] = Label("A  B  C\nD  E  F")
        self["line1"] = Label(""); self["line2"] = Label(""); self["line3"] = Label(""); self["line4"] = Label("")
        self["hint"] = Label("Arrows: move/change | Green: Save | Yellow: Clear | Red: Cancel")
        self.refresh()

        self["actions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions", "NumberActions"], {
            "ok": self.next_group, "cancel": self.close, "red": self.close, "green": self.finish,
            "yellow": self.clear_key,
            "left": self.move_left, "right": self.move_right, "up": self.increment_char, "down": self.decrement_char,
            "0": lambda: self.add_char("0"), "1": lambda: self.add_char("1"), "2": lambda: self.add_char("2"),
            "3": lambda: self.add_char("3"), "4": lambda: self.add_char("4"), "5": lambda: self.add_char("5"),
            "6": lambda: self.add_char("6"), "7": lambda: self.add_char("7"), "8": lambda: self.add_char("8"),
            "9": lambda: self.add_char("9")
        }, -1)

    def get_line_text(self, idx):
        mark = ">" if idx == self.current else " "
        return "%s %s" % (mark, self.lines[idx])

    def refresh(self):
        for i in range(1, 5): self["line%d" % i].setText(self.get_line_text(i-1))

    def clear_key(self):
        self.lines = ["0000", "0000", "0000", "0000"]
        self.current, self.pos = 0, 0
        self.refresh()

    def add_char(self, ch):
        g = list(self.lines[self.current]); g[self.pos] = ch
        self.lines[self.current] = "".join(g)
        self.pos += 1
        if self.pos >= 4:
            self.pos = 0; self.current = min(self.current + 1, 3)
        self.refresh()

    def move_left(self): self.pos = (self.pos - 1) % 4; self.refresh()
    def move_right(self): self.pos = (self.pos + 1) % 4; self.refresh()
    def next_group(self): self.current = (self.current + 1) % 4; self.pos = 0; self.refresh()

    def increment_char(self):
        g = list(self.lines[self.current])
        val = (int(g[self.pos], 16) + 1) % 16
        g[self.pos] = "%X" % val
        self.lines[self.current] = "".join(g)
        self.refresh()

    def decrement_char(self):
        g = list(self.lines[self.current])
        val = (int(g[self.pos], 16) - 1) % 16
        g[self.pos] = "%X" % val
        self.lines[self.current] = "".join(g)
        self.refresh()

    def finish(self): self.close("".join(self.lines))

class BISSPro(Screen):
    skin = """
    <screen name="BISSPro" position="center,center" size="820,520" title="BissPro v1.0">
        <widget name="bg1" position="0,0" size="820,520" backgroundColor="#000000"/>
        <eLabel position="40,110" size="780,380" backgroundColor="#1b1b1b" />
        <widget name="title" position="40,30" size="780,60" font="Regular;36" halign="center" foregroundColor="#00aaff"/>
        <widget name="menu" position="60,130" size="700,260" font="Regular;26" itemHeight="60" foregroundColor="#ffffff" selectionColor="#00aaff"/>
        <widget name="progress" position="60,390" size="700,25" borderWidth="1" borderColor="#555555"/>
        <widget name="status" position="60,430" size="700,80" font="Regular;22" halign="center" foregroundColor="#00ffcc"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [
            ("Update Softcam Online", "update"),
            ("Add Key to Current Channel", "add"),
            ("Show Current Key", "show"),
            ("Show All Keys", "showall"),
            ("Restart Softcam", "restart"),
            ("Show Keys Count", "view"),
        ]
        self["menu"] = MenuList(self.menu_items)
        self["status"] = Label("Welcome to BissPro v1.0")
        self["progress"] = ProgressBar()
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down
        }, -1)

    def ok(self):
        cmd = self["menu"].getCurrent()[1]
        if cmd == "update": self.start_update()
        elif cmd == "restart":
            restartSoftcam()
            self["status"].setText("Softcam restarted")
        elif cmd == "view":
            count = 0
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE, "r") as f:
                    count = sum(1 for l in f if l.startswith("F ") or l.startswith("BISS"))
            self["status"].setText("Total Keys Found: %d" % count)
        elif cmd == "add": self.add_key_logic()
        elif cmd == "show": self.show_current_key()
        elif cmd == "showall": self.session.open(ShowKeysScreen)

    def add_key_logic(self):
        s = self.session.nav.getCurrentService()
        if s:
            info = s.info()
            sid = info.getInfo(iServiceInformation.sSID)
            tsid = info.getInfo(iServiceInformation.sTSID)
            onid = info.getInfo(iServiceInformation.sONID)
            name = info.getName()
            self.session.openWithCallback(self.save_to_file, BissInputScreen, name, sid, tsid, onid)
        else: self["status"].setText("No Active Channel!")

    def show_current_key(self):
        s = self.session.nav.getCurrentService()
        if not s:
            self["status"].setText("No Active Channel!")
            return

        info = s.info()
        sid = info.getInfo(iServiceInformation.sSID)
        tsid = info.getInfo(iServiceInformation.sTSID)
        onid = info.getInfo(iServiceInformation.sONID)
        key = get_existing_key(sid)

        if key:
            self["status"].setText("Current Key: %s | SID:%04X TSID:%04X ONID:%04X" % (key, sid, tsid, onid))
        else:
            self["status"].setText("No Key Found for this Channel")

    def save_to_file(self, key):
        if not key: return
        sid = "%04X" % self.session.nav.getCurrentService().info().getInfo(iServiceInformation.sSID)
        tsid = "%04X" % self.session.nav.getCurrentService().info().getInfo(iServiceInformation.sTSID)
        onid = "%04X" % self.session.nav.getCurrentService().info().getInfo(iServiceInformation.sONID)
        name = self.session.nav.getCurrentService().info().getName()

        new_line = "F %s1FFF 00 %s ; Channel: %s | SID:%s TSID:%s ONID:%s\n" % (sid, key, name, sid, tsid, onid)
        try:
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE, "r") as f: lines = f.readlines()
            else: lines = []

            lines = [l for l in lines if sid not in l]
            lines.append(new_line)
            with open(BISS_FILE, "w") as f: f.writelines(lines)
            self["status"].setText("Key Saved & Applied!")
            restartSoftcam()
        except Exception as e:
            self["status"].setText("Error: %s" % str(e))

    def start_update(self):
        self["status"].setText("Downloading...")
        self["progress"].setValue(20)
        threading.Thread(target=self.update_process).start()

    def update_process(self):
        try:
            urlretrieve(UPDATE_URL, BISS_FILE)
            restartSoftcam()
            eTimer.singleShot(10, lambda: self["status"].setText("Update Success!"))
            eTimer.singleShot(10, lambda: self["progress"].setValue(100))
        except:
            eTimer.singleShot(10, lambda: self["status"].setText("Update Failed!"))

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Manage Biss Keys v1.0", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
