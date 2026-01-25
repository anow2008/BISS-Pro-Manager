# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
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
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

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

def create_backup():
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        return b
    return None

def restartSoftcam():
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]
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
    os.system("%s -b >/dev/null 2>&1 &" % (path if os.path.exists(path) else cam_to_run))
    time.sleep(1)

class SelectKeyScreen(Screen):
    skin = """
    <screen position="center,center" size="720,420" title="Select BISS Key">
        <widget name="list" position="20,20" size="680,320"/>
    </screen>
    """
    def __init__(self, session, sid, callback):
        Screen.__init__(self, session)
        self.sid = sid
        self.callback = callback
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.ok,
            "cancel": self.close
        }, -1)
        self.load()

    def load(self):
        items = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                for l in f:
                    l = l.strip()
                    parts = l.split()
                    if len(parts) >= 4 and parts[0].upper() == "F" and parts[1].upper() == self.sid.upper():
                        items.append((l, l))
        self["list"].setList(items)

    def ok(self):
        sel = self["list"].getCurrent()
        self.close(sel[0] if sel else None)

class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="820,300" title="BISS Editor">
        <widget name="key" position="110,100" size="600,80" font="Console;50"
            halign="center" valign="center" foregroundColor="#ffffff"/>
        <widget name="hexlist" position="720,100" size="80,200" itemHeight="40"/>
    </screen>
    """
    def __init__(self, session, sid, mode="add", key_line=None, sname="Unknown"):
        Screen.__init__(self, session)
        self.sid = sid
        self.mode = mode
        self.key_line = key_line
        self.sname = ''.join(c for c in sname if c.isalnum() or c in ('_', '-')) or "Unknown"

        self.key = list("0000000000000000")
        self.pos = 0

        # ظƒظ„ ظ‚ظٹظ… HEX
        self.allchars = list("0123456789ABCDEF")

        if key_line:
            self.load_from_line()

        self["key"] = Label("")
        self["hexlist"] = MenuList([(c, c) for c in ["A", "B", "C", "D", "E", "F"]])

        self["actions"] = ActionMap(
            ["DirectionActions", "NumberActions", "ColorActions", "OkCancelActions"],
            {
                "left": self.left,
                "right": self.right,
                "up": self.up,
                "down": self.down,
                "ok": self.select_hex,
                "green": self.save,
                "cancel": self.close,
                **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}
            }, -1
        )
        self.refresh()

    def load_from_line(self):
        parts = self.key_line.split()
        if len(parts) >= 4:
            key = parts[3]
            if len(key) == 16:
                self.key = list(key)

    def refresh(self):
        res = "".join(
            ["[%s]" % c if i == self.pos else " %s " % c for i, c in enumerate(self.key)]
        )
        self["key"].setText(res)

    def left(self):
        self.pos = (self.pos - 1) % 16
        self.refresh()

    def right(self):
        self.pos = (self.pos + 1) % 16
        self.refresh()

    # ===== ط§ظ„طھط¹ط¯ظٹظ„ ظ‡ظ†ط§ =====
    def up(self):
        cur = self.key[self.pos]
        if cur not in self.allchars:
            cur = "0"
        self.key[self.pos] = self.allchars[
            (self.allchars.index(cur) + 1) % len(self.allchars)
        ]
        self.right()

    def down(self):
        cur = self.key[self.pos]
        if cur not in self.allchars:
            cur = "F"
        self.key[self.pos] = self.allchars[
            (self.allchars.index(cur) - 1) % len(self.allchars)
        ]
        self.right()
    # ======================

    def set_num(self, c):
        self.key[self.pos] = c
        self.right()

    def select_hex(self):
        sel = self["hexlist"].getCurrent()
        if sel:
            self.key[self.pos] = sel[0]
            self.right()

    def save(self):
        new_key = "".join(self.key)
        new_line = "F %s 00000000 %s ;%s" % (self.sid, new_key, self.sname)

        create_backup()
        lines = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                lines = [l.strip() for l in f]

        with open(BISS_FILE, "w") as f:
            for l in lines:
                if self.mode == "edit" and self.key_line and l == self.key_line:
                    continue
                if l:
                    f.write(l + "\n")
            f.write(new_line + "\n")

        restartSoftcam()
        self.session.openWithCallback(
            lambda _: self.close(),
            MessageBox,
            "Key saved successfully",
            MessageBox.TYPE_INFO,
            3
        )

class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1024,768" title="BissPro v1.0">
        <widget name="menu" position="40,100" size="940,540"
            itemHeight="150" scrollbarMode="showOnDemand"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [
            ("Add Key", "add", "add.png"),
            ("Edit Key", "edit", "edit.png"),
            ("Delete Key", "delete", "delete.png"),
            ("Update SoftCam", "update", "update.png"),
        ]
        self.menu_list = []
        for t, a, i in self.menu_items:
            pix = LoadPixmap(ICON_PATH + i)
            self.menu_list.append(
                (a, [
                    MultiContentEntryPixmapAlphaTest(
                        pos=(10, 10), size=(128, 128), png=pix),
                    MultiContentEntryText(
                        pos=(160, 50), size=(760, 60), font=0, text=t)
                ])
            )
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", 32))
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            }, -1
        )

    def ok(self):
        sel = self["menu"].getCurrent()
        if not sel:
            return
        action = sel[0]
        service = self.session.nav.getCurrentService()
        if not service:
            return
        info = service.info()
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        sname = info.getName().replace(' ', '_')

        if action == "add":
            self.session.open(EasyBissInput, sid, "add", None, sname)
        elif action in ("edit", "delete"):
            self.session.openWithCallback(
                lambda line: self.handle(action, sid, line, sname),
                SelectKeyScreen, sid, lambda x: x
            )
        elif action == "update":
            create_backup()
            try:
                urlretrieve(UPDATE_URL, "/tmp/SoftCam.Key")
                if os.path.exists("/tmp/SoftCam.Key"):
                    shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
                    restartSoftcam()
                    self.session.open(
                        MessageBox,
                        "SoftCam updated successfully",
                        MessageBox.TYPE_INFO,
                        3
                    )
            except:
                self.session.open(
                    MessageBox,
                    "Update failed!",
                    MessageBox.TYPE_ERROR,
                    3
                )

    def handle(self, action, sid, line, sname):
        if not line:
            return
        if action == "edit":
            self.session.open(EasyBissInput, sid, "edit", line, sname)
        elif action == "delete":
            self.session.openWithCallback(
                lambda c: self.delete_confirmed(c, line),
                MessageBox,
                "Are you sure you want to delete this key?",
                MessageBox.TYPE_YESNO,
                3
            )

    def delete_confirmed(self, confirmed, line):
        if not confirmed:
            return
        create_backup()
        with open(BISS_FILE, "r") as f:
            lines = f.readlines()
        with open(BISS_FILE, "w") as f:
            for l in lines:
                if l.strip() != line.strip():
                    f.write(l)
        restartSoftcam()
        self.session.open(
            MessageBox,
            "Key deleted successfully",
            MessageBox.TYPE_INFO,
            3
        )

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="Professional BISS Manager",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main,
            icon="plugin.png"
        )
    ]
