from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from enigma import eTimer
import os, time, urllib.request, shutil, re

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
            {
                "ok": self.close,
                "cancel": self.close,
                "up": self["text"].pageUp,
                "down": self["text"].pageDown
            }, -1
        )

# ---------- SETTINGS SCREEN ----------
class SettingsScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.auto = SETTINGS["auto"]
        self.hours = SETTINGS["hours"]
        self.hoursList = [6, 12, 24, 48]

        self.menu = []
        self.buildMenu()

        self["menu"] = MenuList(self.menu)
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "left": self.left,
                "right": self.right
            }, -1
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
        if i == 0:
            self.auto = not self.auto
        elif i == 1:
            idx = self.hoursList.index(self.hours)
            self.hours = self.hoursList[idx - 1]
        self.buildMenu()

    def right(self):
        i = self["menu"].getSelectionIndex()
        if i == 0:
            self.auto = not self.auto
        elif i == 1:
            idx = self.hoursList.index(self.hours)
            self.hours = self.hoursList[(idx + 1) % len(self.hoursList)]
        self.buildMenu()

    def ok(self):
        if self["menu"].getSelectionIndex() == 2:
            saveSettings(self.auto, self.hours)
            SETTINGS["auto"] = self.auto
            SETTINGS["hours"] = self.hours
            self.close()

# ---------- AUTO UPDATER ----------
class AutoUpdater:
    def __init__(self, session):
        self.session = session
        self.timer = eTimer()
        self.timer.callback.append(self.run)
        self.start()

    def start(self):
        self.timer.startLongTimer(SETTINGS["hours"] * 3600)

    def run(self):
        if not SETTINGS["auto"]:
            self.start()
            return

        try:
            data = urllib.request.urlopen(GITHUB_URL, timeout=10).read().decode()
        except:
            self.start()
            return

        merged = {}
        for l in open(BISS_FILE):
            if l.startswith("F "):
                p = l.split()
                merged[f"{p[1]} {p[2]} {p[3]}"] = l.strip()

        for l in data.splitlines():
            if l.startswith("F "):
                p = l.split()
                merged[f"{p[1]} {p[2]} {p[3]}"] = l.strip()

        shutil.copy(BISS_FILE, BACKUP_FILE)
        open(BISS_FILE, "w").write("\n".join(merged.values()) + "\n")
        log("Auto update completed")

        if os.path.exists("/etc/init.d/softcam"):
            os.system("/etc/init.d/softcam restart")

        self.session.open(
            MessageBox,
            "BISS Auto Update completed successfully",
            MessageBox.TYPE_INFO,
            timeout=5
        )

        self.start()

# ---------- MAIN SCREEN ----------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        ensureFile()

        self.menu = [
            "Add / Edit BISS Key",
            "View Keys",
            "Delete Key",
            "Smart Merge from GitHub",
            "Export Keys to USB",
            "Import Keys from USB",
            "Restore Backup",
            "Restart Softcam",
            "Settings",
            "Exit"
        ]

        self["menu"] = MenuList(self.menu)
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close}, -1
        )

    def view(self):
        self.session.open(ScrollText, open(BISS_FILE).read() or "No Keys")

    def ok(self):
        [
            lambda: None,  # Add / Edit (يمكن إضافة لاحقاً)
            self.view,
            lambda: None,  # Delete
            lambda: None,  # Merge
            lambda: None,  # Export USB
            lambda: None,  # Import USB
            lambda: None,  # Restore
            lambda: os.system("/etc/init.d/softcam restart"),
            lambda: self.session.open(SettingsScreen),
            self.close
        ][self["menu"].getSelectionIndex()]()

# ---------- INIT ----------
updater = None

def main(session, **kwargs):
    global updater
    if updater is None:
        updater = AutoUpdater(session)
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager v2.5",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
