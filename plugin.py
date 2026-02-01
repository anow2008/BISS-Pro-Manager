# -*- coding: utf-8 -*-
# =========================================================
# BissPro Manager – Python 3 – FHD – Online Update
# Fixed Edit/Delete + Plugin Icon
# =========================================================

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.config import (
    config, ConfigSubsection,
    ConfigYesNo, ConfigInteger
)
from enigma import iServiceInformation
import os, time, shutil, urllib.request
from datetime import datetime

# ================= URLs =================
UPDATE_URL   = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"

# ================= Plugin Info =================
PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.6-py3-FHD"

# ================= Config =================
config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.backup_enable = ConfigYesNo(default=True)
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1, 50))

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
def create_backup():
    if not config.plugins.bisspro.backup_enable.value:
        return
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)

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
    except Exception:
        return False

# ================= Manual Input =================
class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="900,320" title="Manual BISS Entry">
        <widget name="key" position="60,120" size="720,80"
            font="Console;50" halign="center" valign="center"/>
        <widget name="hexlist" position="800,90" size="80,200"/>
    </screen>"""

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
        self["hexlist"] = MenuList([(c, c) for c in "ABCDEF"])

        self["actions"] = ActionMap(
            ["DirectionActions", "NumberActions", "ColorActions", "OkCancelActions"],
            {
                "left": self.left,
                "right": self.right,
                "up": self.up,
                "down": self.down,
                "ok": self.pick_hex,
                "green": self.save,
                "cancel": self.close,
                **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}
            }, -1
        )
        self.refresh()

    def refresh(self):
        self["key"].setText("".join(
            ["[%s]" % c if i == self.pos else " %s " % c
             for i, c in enumerate(self.key)]
        ))

    def left(self):
        self.pos = (self.pos - 1) % 16
        self.refresh()

    def right(self):
        self.pos = (self.pos + 1) % 16
        self.refresh()

    def up(self):
        v = "0123456789ABCDEF"
        self.key[self.pos] = v[(v.index(self.key[self.pos]) + 1) % 16]
        self.right()

    def down(self):
        v = "0123456789ABCDEF"
        self.key[self.pos] = v[(v.index(self.key[self.pos]) - 1) % 16]
        self.right()

    def set_num(self, n):
        self.key[self.pos] = n
        self.right()

    def pick_hex(self):
        c = self["hexlist"].getCurrent()
        if c:
            self.key[self.pos] = c[0]
            self.right()

    def save(self):
        create_backup()
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
        self.session.open(MessageBox, "Key Saved", MessageBox.TYPE_INFO, 3)
        self.close()

# ================= Main Screen =================
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1000,540" title="BissPro Manager">
        <widget name="menu" position="80,80" size="840,380"/>
        <widget name="status" position="80,470" size="840,40"
            font="Regular;24" halign="center"/>
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([
            ("Add BISS Key", "add"),
            ("Edit BISS Key", "edit"),
            ("Delete BISS Key", "delete"),
            ("Online Update SoftCam.Key", "update"),
            ("Import BISS from biss.txt", "import"),
        ])
        self["status"] = Label("")
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

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
            if not old:
                self.session.open(MessageBox, "No BISS key for this channel", MessageBox.TYPE_ERROR, 3)
                return
            self.session.open(EasyBissInput, sid, "edit", old, name)

        elif sel == "delete":
            old = find_key_by_sid(sid)
            if not old:
                self.session.open(MessageBox, "No BISS key for this channel", MessageBox.TYPE_ERROR, 3)
                return

            def do_delete(answer):
                if answer:
                    create_backup()
                    write_keys([l for l in read_keys() if l != old])
                    restartSoftcam()
                    self.session.open(MessageBox, "BISS key deleted", MessageBox.TYPE_INFO, 3)

            self.session.openWithCallback(
                do_delete,
                MessageBox,
                "Delete BISS key for this channel?",
                MessageBox.TYPE_YESNO
            )

        elif sel == "update":
            create_backup()
            if download(UPDATE_URL, BISS_FILE):
                restartSoftcam()
                self.session.open(MessageBox, "SoftCam.Key Updated", MessageBox.TYPE_INFO, 3)

        elif sel == "import":
            tmp = "/tmp/biss.txt"
            if download(BISS_TXT_URL, tmp):
                create_backup()
                with open(BISS_FILE, "a") as out, open(tmp) as inp:
                    for l in inp:
                        if l.startswith("F "):
                            out.write(l)
                restartSoftcam()
                self.session.open(MessageBox, "BISS Imported", MessageBox.TYPE_INFO, 3)

# ================= Entry =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Manager PY3 FHD Online",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="icon.png",
        fnc=main
    )]

