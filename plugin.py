from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
import os, shutil

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
    def __init__(self, session, text):
        Screen.__init__(self, session)
        from Components.Sources.ScrollLabel import ScrollLabel
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
    def __init__(self, session, callback, prefill=""):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = prefill
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

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self["menu"] = MenuList(["Manage BISS Keys"])
        self["status"] = Label("BISS Pro Ready")
        # Action map example
        self["actions"] = ActionMap(["OkCancelActions","DirectionActions"],
                                    {"ok": self.menuSelected, "cancel": self.close,
                                     "up": self["menu"].up, "down": self["menu"].down}, -1)

    def menuSelected(self):
        # هنا هتفتح شاشة إدارة المفاتيح (مثال)
        self.session.open(MessageBox, "Feature coming soon", MessageBox.TYPE_INFO)

# ---------------- PLUGIN ENTRY ----------------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Manage BISS Keys", 
                             where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
