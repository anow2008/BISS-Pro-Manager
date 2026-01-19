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

# ---------- SCROLL TEXT ----------
class ScrollText(Screen):
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
            },
            -1
        )

# ---------- HEX KEY INPUT ----------
class HexKeyInput(Screen):
    def __init__(self, session, callback):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = ""

        self.keys = [
            "1","2","3","4","5","6","7","8","9",
            "A","B","C","D","E","F","0",
            "DEL","SAVE"
        ]

        self["key"] = Label("")
        self["list"] = MenuList(self.keys)
        self["hint"] = Label("OK=ADD   RED=DEL   YELLOW=SAVE   EXIT=Cancel")

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "NumberActions"],
            {
                "ok": self.ok,
                "red": self.delete,
                "yellow": self.save,
                "cancel": self.close,
                **{str(i): lambda x=str(i): self.add(x) for i in range(10)}
            },
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
            self.session.open(
                MessageBox,
                "Key must be 16 or 32 HEX",
                MessageBox.TYPE_ERROR
            )
            return
        self.callback(self.key)
        self.close()

# ---------- SETTINGS SCREEN ----------
class SettingsScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.auto = SETTINGS["auto"]
        self.hours = SETTINGS["hours"]
        self.hoursList = [6, 12, 24, 48]

        self["menu"] = MenuList([])
        self.buildMenu()

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "left": self.left,
                "right": self.right
            },
            -1
        )

    def buildMenu(self):
        self["menu"].setList([
            "Auto Update : " + ("ON" if self.auto else "OFF"),
            "Update Interval : %s Hours" % self.hours,
            "Save & Exit"
        ])

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

        self["menu"] = MenuList([
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
        ])

        self["status"] = Label("Ready")

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    def getIDs(self):
        s = self.session.nav.getCurrentService()
        if not s:
            return None
        i = s.info()
        return {
            "sid": "%04X" % i.getInfo(i.sSID),
            "tsid": "%04X" % i.getInfo(i.sTSID),
            "onid": "%04X" % i.getInfo(i.sONID),
            "name": i.getName().strip()
        }

    def addKey(self):
        ids = self.getIDs()
        if ids:
            self.session.open(HexKeyInput, lambda k: self.saveKey(ids, k))

    def saveKey(self, ids, key):
        mode = "00" if len(key) == 16 else "01"
        line = f"F {ids['sid']} {ids['tsid']} {ids['onid']} {mode} {key} ; {ids['name']} | {time.strftime('%Y-%m-%d')}"
        shutil.copy(BISS_FILE, BACKUP_FILE)

        lines = [l for l in open(BISS_FILE) if not l.startswith(f"F {ids['sid']} {ids['tsid']} {ids['onid']}")]
        lines.append(line + "\n")

        open(BISS_FILE, "w").writelines(lines)
        log("Key saved")
        self.restart()

    def view(self):
        self.session.open(ScrollText, open(BISS_FILE).read() or "No Keys")

    def deleteKey(self):
        lines = open(BISS_FILE).read().splitlines()
        if not lines:
            return
        self.session.openWithCallback(
            self.confirmDelete,
            MessageBox,
            "Delete last key?",
            MessageBox.TYPE_YESNO
        )

    def confirmDelete(self, answer):
        if answer:
            shutil.copy(BISS_FILE, BACKUP_FILE)
            lines = open(BISS_FILE).read().splitlines()
            open(BISS_FILE, "w").writelines([l + "\n" for l in lines[:-1]])
            log("Key deleted")
            self.restart()

    def mergeGit(self):
        try:
            data = urllib.request.urlopen(GITHUB_URL, timeout=10).read().decode()
        except:
            self.session.open(MessageBox, "GitHub not reachable", MessageBox.TYPE_ERROR)
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
        log("GitHub merged")
        self.restart()

    def exportUSB(self):
        if os.path.exists("/media/usb"):
            shutil.copy(BISS_FILE, USB_PATH)
            self["status"].setText("Exported to USB")

    def importUSB(self):
        if os.path.exists(USB_PATH):
            shutil.copy(USB_PATH, BISS_FILE)
            self.restart()

    def restart(self):
        os.system("killall oscam ncam 2>/dev/null")
        if os.path.exists("/etc/init.d/softcam"):
            os.system("/etc/init.d/softcam restart")
        elif SOFTCAM_BINARY:
            os.system(SOFTCAM_BINARY + " &")

    def ok(self):
        [
            self.addKey,
            self.view,
            self.deleteKey,
            self.mergeGit,
            self.exportUSB,
            self.importUSB,
            lambda: shutil.copy(BACKUP_FILE, BISS_FILE) if os.path.exists(BACKUP_FILE) else None,
            self.restart,
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
        name="BISS Pro v1.0",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
