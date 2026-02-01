# -*- coding: utf-8 -*-
# =========================================================
# BissPro Manager – OpenATV 7.6 – CLEAN UI
# =========================================================

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from enigma import iServiceInformation
import os, time, urllib.request

PLUGIN_NAME = "BissPro"

UPDATE_URL   = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"

# ================= Paths =================
def get_key_path():
    for p in [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ]:
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
    <screen position="center,center" size="900,360" title="Manual BISS Key">
        <widget name="key" position="40,80" size="820,90"
            font="Console;48" halign="center" valign="center"/>
        <widget name="hexlist" position="390,190" size="120,140"/>
        <widget name="status" position="40,300" size="820,40"
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
        self["status"] = Label("Enter key")
        self["hexlist"] = MenuList([(c, c) for c in "ABCDEF"])

        self["actions"] = ActionMap(
            ["DirectionActions", "NumberActions", "ColorActions", "OkCancelActions"],
            {
                "left": self.left,
                "right": self.right,
                "up": self["hexlist"].up,
                "down": self["hexlist"].down,
                "ok": self.pick_hex,
                "green": self.save,
                "red": self.close,
                "cancel": self.close,
                **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}
            }, -1
        )

        self.refresh()

    def refresh(self):
        txt = ""
        for i, c in enumerate(self.key):
            if i % 4 == 0:
                txt += "  "
            if i == self.pos:
                txt += (
                    '<span backgroundColor="#0059b3" foregroundColor="#ffffff">'
                    ' %s '
                    '</span>' % c
                )
            else:
                txt += (
                    '<span foregroundColor="#ffffff">'
                    ' %s '
                    '</span>' % c
                )
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

    def pick_hex(self):
        c = self["hexlist"].getCurrent()
        if c:
            self.key[self.pos] = c[0]
            self.right()

    def save(self):
        self["status"].setText("Saving key...")
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
        self.close()

# ================= Main Screen =================
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1100,600" title="BissPro Manager">
        <widget name="menu" position="100,100" size="900,380"
            selectionBackgroundColor="#0059b3"
            selectionForegroundColor="#ffffff"/>
        <widget name="status" position="100,510" size="900,40"
            font="Regular;24" halign="center"
            foregroundColor="#ffffff"/>
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
                with open(BISS_FILE, "w") as f:
                    for l in read_keys():
                        if l != old:
                            f.write(l + "\n")
                restartSoftcam()
                self.setStatus("Done")

        elif sel == "update":
            self.setStatus("Updating SoftCam.Key...")
            if download(UPDATE_URL, BISS_FILE):
                restartSoftcam()
                self.setStatus("Done")

        elif sel == "import":
            self.setStatus("Importing BISS keys...")
            tmp = "/tmp/biss.txt"
            if download(BISS_TXT_URL, tmp):
                with open(BISS_FILE, "a") as out, open(tmp) as inp:
                    for l in inp:
                        if l.startswith("F "):
                            out.write(l)
                restartSoftcam()
                self.setStatus("Done")

# ================= Entry =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Manager Clean UI",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="icon.png",
        fnc=main
    )]
