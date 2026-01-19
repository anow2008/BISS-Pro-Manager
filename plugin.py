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
    skin = """
    <screen position="center,center" size="900,600" title="BISS Keys">
        <widget name="text" position="10,10" size="880,520" font="Regular;22" />
        <widget name="hint" position="10,540" size="880,40" font="Regular;18" />
    </screen>
    """
    def __init__(self, session, text):
        Screen.__init__(self, session)
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
        if s == "DEL": self.delete()
        elif s == "SAVE": self.save()
        else: self.add(s)

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

# ---------- SETTINGS SCREEN ----------
class SettingsScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.auto = SETTINGS["auto"]
        self.hours = SETTINGS["hours"]
        self.hoursList = [6,12,24,48]

        self.menu = []
        self.buildMenu()
        self["menu"] = MenuList(self.menu)

        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {"ok": self.ok,"cancel": self.close,"left": self.left,"right": self.right},
            -1
        )

    def buildMenu(self):
        self.menu = [
            "Auto Update : " + ("ON" if self.auto else "OFF"),
            "Update Interval : %s Hours" % self.hours,
            "Save & Exit"
        ]
        if "menu" in self:
            self["menu"].setList(self.menu)

    def left(self):
        i = self["menu"].getSelectionIndex()
        if i == 0: self.auto = not self.auto
        elif i == 1:
            idx = self.hoursList.index(self.hours)
            self.hours = self.hoursList[idx-1]
        self.buildMenu()

    def right(self):
        i = self["menu"].getSelectionIndex()
        if i == 0: self.auto = not self.auto
        elif i == 1:
            idx = self.hoursList.index(self.hours)
            self.hours = self.hoursList[(idx+1)%len(self.hoursList)]
        self.buildMenu()

    def ok(self):
        if self["menu"].getSelectionIndex() == 2:
            saveSettings(self.auto,self.hours)
            SETTINGS["auto"] = self.auto
            SETTINGS["hours"] = self.hours
            self.close()

# ---------- AUTO UPDATER -------
