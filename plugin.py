from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from enigma import eTimer
import os, time, urllib.request, shutil

# ---------- PATHS ----------
SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key"
]

BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_FILE = BISS_FILE + ".bak"
USB_PATH = "/media/usb/SoftCam.Key"
LOG_FILE = "/tmp/bisspro.log"
SETTINGS_FILE = "/etc/bisspro.conf"

GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

SOFTCAM_BINARY = next(
    (p for p in ["/usr/bin/oscam", "/usr/bin/ncam", "/usr/local/bin/oscam"] if os.path.exists(p)),
    None
)

# ---------- SETTINGS ----------
def loadSettings():
    if not os.path.exists(SETTINGS_FILE):
        return {"auto": True, "hours": 12}
    try:
        auto, hours = open(SETTINGS_FILE).read().strip().split("|")
        return {"auto": auto == "1", "hours": int(hours)}
    except:
        return {"auto": True, "hours": 12}

def saveSettings(auto, hours):
    open(SETTINGS_FILE, "w").write("%s|%s" % ("1" if auto else "0", hours))

SETTINGS = loadSettings()

# ---------- UTILS ----------
def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))

def ensureFile():
    if not os.path.exists(BISS_FILE):
        open(BISS_FILE, "w").close()

# ---------- SCROLL SCREEN ----------
class ScrollText(Screen):
    def __init__(self, session, text):
        Screen.__init__(self, session)
        from enigma import eWindow
        self.skinName = "BissPorScroll"
        self["text"] = ScrollLabel(text)
        self["hint"] = Label("▲▼ Scroll   OK / EXIT Close")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok": self.close, "cancel": self.close, "up": self["text"].pageUp, "down": self["text"].pageDown},
            -1
        )

# ---------- HEX INPUT SCREEN ----------
class HexKeyInput(Screen):
    def __init__(self, session, callback):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = ""
        self.keys = ["1","2","3","4","5","6","7","8","9","A","B","C","D","E","F","0","DEL","SAVE"]
        self["key"] = Label("")
        self["list"] = MenuList(self.keys)
        self["hint"] = Label("OK=ADD   RED=DEL   YELLOW=SAVE   EXIT=Cancel")
        self["actions"] = ActionMap(
            ["OkCancel]()
