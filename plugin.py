from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Tools.Directories import fileExists
import os, time, urllib.request, shutil, re

# ---------- PATHS ----------
SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key"
]

BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_FILE = BISS_FILE + ".bak"
LOG_FILE = "/tmp/bisspro.log"
USB_PATH = "/media/usb/SoftCam.Key"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

SOFTCAM_BINARY = next(
    (p for p in ["/usr/bin/oscam", "/usr/bin/ncam", "/usr/local/bin/oscam"] if os.path.exists(p)),
    None
)

# ---------- UTILS ----------
def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))

def ensureFile():
    if not os.path.exists(BISS_FILE):
        open(BISS_FILE, "w").close()

# ---------- HEX INPUT ----------
class HexKeyInput(Screen):
    def __init__(self, session, callback):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = ""
        self.keys = ["1","2","3","4","5","6","7","8","9",
                     "A","B","C","D","E","F","0","DEL","SAVE"]

        self["key"] = Label("")
        self["list"] = MenuList(self.keys)
        self["hint"] = Label("OK=ADD   RED=DEL   YELLOW=SAVE   EXIT=Cancel")

        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions","NumberActions"],
            {
                "ok": self.ok,
                "red": self.delete,
                "yellow": self.save,
                "cancel": self.close,
                **{str(i): lambda x=str(i): self.add(x) for i in range(10)}
            }, -1
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
        if c.upper() not in "0123456789ABCDEF":
            return
        if len(self.key) < 32:
            self.key += c.upper()
            self.update()

    def delete(self):
        self.key = self.key[:-1]
        self.update()

    def update(self):
        v = self.key.ljust(32, "-")
        self["key"].setText(" ".join(v[i:i+4] for i in r
