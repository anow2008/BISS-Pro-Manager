# -*- coding: utf-8 -*-
# =========================================================
# BissPro Manager – Python 3 – FHD – BLUE UI – CLEAN STATUS
# =========================================================

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from enigma import iServiceInformation
import os, time, urllib.request

# ================= URLs =================
UPDATE_URL   = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"

PLUGIN_NAME = "BissPro"

# ================= Paths =================
def get_key_path():
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

# ================= Helpers =================
def restartSoftcam():
    os.system("killall oscam ncam gcam 2>/dev/null")
    time.sleep(1)
    os.system("oscam -b >/dev/null 2>&1 &")

def read_keys():
    if not os.path.exists(BISS_FILE):
        return []
    return [l.strip() for l in open(BISS_FILE, "r", errors="ignore") if l.startswith("F ")]

def write_keys(lines):
    with open(BISS_FILE, "w") as f:
        for l in lines:
            f.write(l + "\n")

def find_key_by_sid(sid):
    for l in read_keys():
        if l.split()[1] == sid:
            return l
    return None

def download(url, dest):
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except:
        return False

# ================= Manual BISS Input =================
class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="900,360" title="Manual BISS Key">
        <widget name="key" position="40,60" size="820,90"
            font="Console;52" halign="center" valign="center"/>
        <widget name="hexlist" position="390,190" size="120,150"/>
        <widget name="buttons" position="40,310" size="820,40"
            font="Regular;22" halign="center"/>
    </screen>
    """

    def __init__(self, session, sid, mode="add", old=None, name="Channel"):
        Screen.__init__(self, session)
        self.sid = sid
        self.mode = mode
        self.old = old
        self.name = name
        self.key = list("0000000000000000")
        self.pos = 0

        if old:
            self.key = list(old.split()[3])

        self["key"] = Label("")
        self["buttons"] = Label("GREEN = Save    RED = Exit")
        self["hexlist"] = MenuList([(c, c) for c in "ABCDEF"])

        self["actions"] = ActionMap(
            ["DirectionActions", "NumberActions", "ColorActions", "OkCancelActions"],
            {
                "left": self.left,
                "right": self.right,
                "up": self.hex_up,
                "down": self.hex_down,
                "ok": self.pick_hex,
                "green": self.save,
                "red": self.close,
                "cancel": self.close,
                **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}
            }, -1
        )

        self.refresh()

    # 🔵 Clear & Visible Input
    def refresh(self):
        txt = ""
        for i, c in enumerate(self.key):
            if i == self.pos:
                txt += "\x1b[44m\x1b[97m %s \x1b[0m" % c   # Active
            else:
                txt += "\x1b[37m %s \x1b[0m" % c          # Normal
        self["key"].setText(txt)

    def left(self):
        self.pos = (self.pos - 1) % 16
        self.refresh()

    def right(self):
        self.pos = (self.pos + 1) % 16
        self.refresh()

    def set_num(self, n):
        self.key[self.pos] = n
        self.right()

    def hex_up(self):
        self["hexlist"].up()

    def hex_down(self):
        self["hexlist"].down()

    def pick_hex(self):
        c = self["hexlist"].getCurrent()
        if c:
            self.key[self.pos] = c[0]
            self.right()

    def save(self):
        new = "F %s 00000000 %s ;%s" % (
            self.sid, "".join(self.key), self.name
        )
        lines = read_keys()
        with open(BISS_FILE, "w") as f:
            for l in lines:
                if self.mode == "edit" and l == self.old:
                    continue
                f.write(l + "\n")
            f.write(new + "\n")

        restartSoftcam()
        self.session.open(MessageBox, "BISS Key Saved", MessageBox.TYPE_INFO, 3)
        self.close()

# ================= Main Screen =================
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1100,600" title="BissPro Manager">
        <colors>
            <color name="bgBlue" value="#001a33" />
            <color name="white" value="#ffffff" />
            <color name="selectBlue" value="#0059b3" />
        </colors>

        <ePixmap position="0,0" size="1100,600" backgroundColor="bgBlue" zPosition="-1"/>

        <widget name="menu" position="100,100" size="900,380"
            foregroundColor="white"
            backgroundColor="bgBlue"
            selectionForegroundColor="white"
            selectionBackgroundColor="selectBlue"
            transparent="1"/>

        <widget name="status" position="100,510" size="900,40"
            font="Regular;24" halign="center"
            foregroundColor="white"
            backgroundColor="bgBlue"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([
            ("Add BISS Key", "add"),
            ("Edit BISS Key", "edit"),
            ("Delete BISS Key", "delete"),
            ("Online Update SoftCam.Key", "update"),
            ("Import BISS from biss.txt", "import"),
        ])
        self["menu"].l.setItemHeight(60)
        self["status"] = Label("Ready")

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    def setStatus(self, txt):
        self["status"].setText(txt)

    def ok(self):
        sel = self["menu"].getCurrent()[1]
        service = self.session.nav.getCurrentService()
        info = service.info() if service else None
        sid = "%08X" % info.getInfo(iServiceInformation.sSID) if info else ""
        name = info.getName().replace(" ", "_") if info else "Channel"

        if sel == "add":
            self.setStatus("Opening manual input...")
            self.session.open(EasyBissInput, sid, "add", None, name)

        elif sel == "edit":
            self.setStatus("Loading key...")
            old = find_key_by_sid(sid)
            if old:
                self.session.open(EasyBissInput, sid, "edit", old, name)

        elif sel == "delete":
            self.setStatus("Deleting key...")
            old = find_key_by_sid(sid)
            if old:
                write_keys([l for l in read_keys() if l != old])
                restartSoftcam()
                self.setStatus("Key deleted")

        elif sel == "update":
            self.setStatus("Updating SoftCam.Key...")
            if download(UPDATE_URL, BISS_FILE):
                restartSoftcam()
                self.setStatus("Update completed")

        elif sel == "import":
            self.setStatus("Importing BISS keys...")
            tmp = "/tmp/biss.txt"
            if download(BISS_TXT_URL, tmp):
                with open(BISS_FILE, "a") as out, open(tmp) as inp:
                    for l in inp:
                        if l.startswith("F "):
                            out.write(l)
                restartSoftcam()
                self.setStatus("Import completed")

# ================= Entry =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Manager PY3 FHD BLUE UI",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="icon.png",
        fnc=main
    )]
