# -*- coding: utf-8 -*-
# =========================================================
# BissPro Manager – OpenATV – STABLE FINAL
# =========================================================

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import iServiceInformation
import os, time, urllib.request

PLUGIN_NAME = "BissPro"

UPDATE_URL   = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"

# ================= Paths =================
def get_key_path():
    for p in (
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ):
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

# ================= Manual Input =================
class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="950,320" title="Manual BISS Key">

        <!-- 16 HEX boxes -->
        <widget name="k0"  position="80,80"  size="40,60"/>
        <widget name="k1"  position="130,80" size="40,60"/>
        <widget name="k2"  position="180,80" size="40,60"/>
        <widget name="k3"  position="230,80" size="40,60"/>

        <widget name="k4"  position="300,80" size="40,60"/>
        <widget name="k5"  position="350,80" size="40,60"/>
        <widget name="k6"  position="400,80" size="40,60"/>
        <widget name="k7"  position="450,80" size="40,60"/>

        <widget name="k8"  position="520,80" size="40,60"/>
        <widget name="k9"  position="570,80" size="40,60"/>
        <widget name="k10" position="620,80" size="40,60"/>
        <widget name="k11" position="670,80" size="40,60"/>

        <widget name="k12" position="740,80" size="40,60"/>
        <widget name="k13" position="790,80" size="40,60"/>
        <widget name="k14" position="840,80" size="40,60"/>
        <widget name="k15" position="890,80" size="40,60"/>

        <widget name="hexlist" position="415,170" size="120,120"/>
    </screen>
    """

    def __init__(self, session, sid, mode="add", old=None, name="Channel"):
        Screen.__init__(self, session)

        self.sid = sid
        self.mode = mode
        self.old = old
        self.name = name

        self.key = list("0000000000000000")
        if old:
            self.key = list(old.split()[3])

        self.pos = 0
        self.labels = []

        for i in range(16):
            self["k%d" % i] = Label("0")
            self["k%d" % i].instance.setFont(self["k%d" % i].instance.getFont())
            self.labels.append(self["k%d" % i])

        self["hexlist"] = MenuList([(c, c) for c in "ABCDEF"])

        self["actions"] = ActionMap(
            ["DirectionActions", "NumberActions", "OkCancelActions"],
            {
                "left": self.left,
                "right": self.right,
                "ok": self.pick_hex,
                "green": self.save,
                "cancel": self.close,
                **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}
            }, -1
        )

        self.refresh()

    def refresh(self):
        for i in range(16):
            self.labels[i].setText(self.key[i])
            if i == self.pos:
                self.labels[i].instance.setBackgroundColor(0x0059B3)
                self.labels[i].instance.setForegroundColor(0xFFFFFF)
            else:
                self.labels[i].instance.setBackgroundColor(0x000000)
                self.labels[i].instance.setForegroundColor(0xFFFFFF)

    def left(self):
        self.pos = (self.pos - 1) % 16
        self.refresh()

    def right(self):
        self.pos = (self.pos + 1) % 16
        self.refresh()

    def set_num(self, n):
        self.key[self.pos] = n
        self.right()

    def pick_hex(self):
        c = self["hexlist"].getCurrent()
        if c:
            self.key[self.pos] = c[0]
            self.right()

    def save(self):
        new = "F %s 00000000 %s ;%s" % (
            self.sid, "".join(self.key), self.name
        )

        with open(BISS_FILE, "w") as f:
            for l in read_keys():
                if self.mode == "edit" and l == self.old:
                    continue
                f.write(l + "\n")
            f.write(new + "\n")

        restartSoftcam()
        self.close()

# ================= Main Screen =================
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1100,620" title="BissPro Manager">
        <widget name="menu" position="100,90" size="900,360"
            selectionBackgroundColor="#0059b3"
            selectionForegroundColor="#ffffff"/>
        <widget name="status" position="100,470" size="900,30"
            font="Regular;22" halign="center"/>
        <widget name="progress" position="100,510" size="900,18"/>
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
        self["progress"] = ProgressBar()
        self["progress"].setValue(0)

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    def setProgress(self, text, value):
        self["status"].setText(text)
        self["progress"].setValue(value)

    def ok(self):
        sel = self["menu"].getCurrent()[1]
        service = self.session.nav.getCurrentService()
        info = service.info() if service else None
        sid = "%08X" % info.getInfo(iServiceInformation.sSID) if info else ""
        name = info.getName().replace(" ", "_") if info else "Channel"

        if sel == "add":
            self.session.open(EasyBissInput, sid, "add", None, name)

        elif sel == "edit":
            old = find_key_by_sid(sid)
            if old:
                self.session.open(EasyBissInput, sid, "edit", old, name)

        elif sel == "delete":
            self.setProgress("Deleting...", 50)
            old = find_key_by_sid(sid)
            if old:
                with open(BISS_FILE, "w") as f:
                    for l in read_keys():
                        if l != old:
                            f.write(l + "\n")
            restartSoftcam()
            self.setProgress("Done", 100)

        elif sel == "update":
            self.setProgress("Updating...", 30)
            if download(UPDATE_URL, BISS_FILE):
                self.setProgress("Restarting cam...", 70)
                restartSoftcam()
                self.setProgress("Done", 100)

        elif sel == "import":
            self.setProgress("Importing...", 30)
            tmp = "/tmp/biss.txt"
            if download(BISS_TXT_URL, tmp):
                with open(BISS_FILE, "a") as out, open(tmp) as inp:
                    for l in inp:
                        if l.startswith("F "):
                            out.write(l)
                self.setProgress("Restarting cam...", 70)
                restartSoftcam()
                self.setProgress("Done", 100)

# ================= Entry =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Manager Stable",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="icon.png",
        fnc=main
    )]
