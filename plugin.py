# -*- coding: utf-8 -*-

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.Skin import loadSkin
from enigma import iServiceInformation
import os, time

PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro/"

# تحميل الـ Skin مرة واحدة
if os.path.exists(PLUGIN_PATH + "skin.xml"):
    loadSkin(PLUGIN_PATH + "skin.xml")

# ================= Helpers =================
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

def restartSoftcam():
    os.system("killall oscam ncam gcam 2>/dev/null")
    time.sleep(1)
    os.system("oscam -b >/dev/null 2>&1 &")

def read_keys():
    if not os.path.exists(BISS_FILE):
        return []
    return [l.strip() for l in open(BISS_FILE, "r", errors="ignore") if l.startswith("F ")]

def find_key_by_sid(sid):
    sid4 = sid[-4:].upper()
    for l in read_keys():
        parts = l.split()
        if len(parts) > 3 and parts[1].upper() == sid4:
            return l
    return None

# ================= Manual Input =================
class EasyBissInput(Screen):
    def __init__(self, session, sid, mode="add", old=None, name="Channel"):
        Screen.__init__(self, session)

        self.sid = sid[-4:]
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
        self.session.open(MessageBox, "Key Saved", MessageBox.TYPE_INFO, 3)
        self.close()

# ================= Main Screen =================
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)

        self["menu"] = MenuList([
            ("Add BISS Key", "add"),
            ("Edit BISS Key", "edit"),
            ("Delete BISS Key", "delete"),
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

    def ok(self):
        service = self.session.nav.getCurrentService()
        info = service.info() if service else None
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        name = info.getName().replace(" ", "_")

        sel = self["menu"].getCurrent()[1]

        if sel == "add":
            self.session.open(EasyBissInput, sid, "add", None, name)

        elif sel == "edit":
            old = find_key_by_sid(sid)
            if old:
                self.session.open(EasyBissInput, sid, "edit", old, name)
            else:
                self.session.open(MessageBox, "No key for this channel", MessageBox.TYPE_INFO, 3)

        elif sel == "delete":
            old = find_key_by_sid(sid)
            if old:
                with open(BISS_FILE, "w") as f:
                    for l in read_keys():
                        if l != old:
                            f.write(l + "\n")
                restartSoftcam()

# ================= Entry =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="BissPro",
            description="BISS Manager",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="icon.png",
            fnc=main
        )
    ]
