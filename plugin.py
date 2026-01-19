from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
import os, urllib.request, shutil

PLUGIN_NAME = "Biss Pro"
PLUGIN_VERSION = "v1.0"

SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key"
]

BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_FILE = BISS_FILE + ".bak"
USB_PATH = "/media/usb/SoftCam.Key"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

SOFTCAM_BINARY = next(
    (p for p in ["/usr/bin/oscam", "/usr/bin/oscam-emu", "/usr/bin/ncam"] if os.path.exists(p)),
    None
)

def ensureFile():
    if not os.path.exists(BISS_FILE):
        with open(BISS_FILE, "w") as f:
            pass

# ---------------- SCROLL SCREEN ----------------
class ScrollText(Screen):
    skin = """
    <screen position="center,center" size="900,600" title="BISS Keys">
        <widget name="text" position="10,10" size="880,520" font="Regular;22"/>
        <widget name="hint" position="10,540" size="880,40" font="Regular;18"/>
    </screen>
    """
    def __init__(self, session, text):
        Screen.__init__(self, session)
        self["text"] = ScrollLabel(text)
        self["hint"] = Label("▲▼ Scroll   OK / EXIT Close")
        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {
                "ok": self.close,
                "cancel": self.close,
                "up": self["text"].pageUp,
                "down": self["text"].pageDown
            }, -1
        )

# ---------------- EDIT LIST SCREEN ----------------
class EditListScreen(Screen):
    skin = """
    <screen position="center,center" size="900,600" title="Select Key to Edit">
        <widget name="list" position="10,10" size="880,520" font="Regular;20"/>
        <widget name="hint" position="10,540" size="880,40" font="Regular;18"/>
    </screen>
    """
    def __init__(self, session, lines, callback):
        Screen.__init__(self, session)
        self.lines = lines
        self.callback = callback
        self.items = [f"{idx+1:03d}: {line.strip() or '(empty)'}" for idx, line in enumerate(lines)]
        self["list"] = MenuList(self.items)
        self["hint"] = Label("OK=Edit  EXIT=Cancel")
        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["list"].up,
                "down": self["list"].down
            }, -1
        )

    def ok(self):
        idx = self["list"].getSelectionIndex()
        self.callback(idx)
        self.close()

# ---------------- HEX INPUT ----------------
class HexKeyInput(Screen):
    skin = """
    <screen position="center,center" size="900,600" title="Enter BISS Key">
        <widget name="key" position="10,40" size="880,40" font="Regular;24"/>
        <widget name="list" position="10,100" size="880,300" font="Regular;22"/>
        <widget name="hint" position="10,420" size="880,40" font="Regular;18"/>
    </screen>
    """
    def __init__(self, session, callback):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = ""
        self.keys = ["1","2","3","4","5","6","7","8","9",
                     "A","B","C","D","E","F","0","DEL","SAVE"]
        self["key"] = Label("")
        self["list"] = MenuList(self.keys)
        self["hint"] = Label("OK=ADD  RED=DEL  YELLOW=SAVE  EXIT=Cancel")
        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions","NumberActions"],
            {**{str(i): lambda x=str(i): self.add(x) for i in range(10)},
             "ok": self.ok, "red": self.delete, "yellow": self.save, "cancel": self.close},
            -1
        )
        self.update()

    def ok(self):
        s = self["list"].getCurrent()
        if s == "DEL":
            self.delete()
        elif s == "SAVE":
            self.save()
        else:
            self.add(s)

    def add(self, c):
        if len(self.key) < 32:
            self.key += c
            self.update()

    def delete(self):
        self.key = self.key[:-1]
        self.update()

    def update(self):
        v = self.key.ljust(32, "-")
        self["key"].setText(" ".join(v[i:i+4] for i in range(0, 32, 4)))

    def save(self):
        if len(self.key) not in (16, 32):
            self.session.open(MessageBox, "Key must be 16 or 32 HEX", MessageBox.TYPE_ERROR)
            return
        self.callback(self.key)
        self.close()

# ---------------- HEX INPUT WITH PREFILL ----------------
class HexKeyInputPrefill(HexKeyInput):
    def __init__(self, session, prefill, callback):
        super().__init__(session, callback)
        self.key = prefill
        self.update()

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="600,500" title="BISS Pro">
        <widget name="menu" position="10,10" size="580,420" />
        <widget name="status" position="10,440" size="580,40" font="Regular;18"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
