from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Tools.Directories import fileExists
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
LOG_FILE = "/tmp/bisspro.log"
USB_PATH = "/media/usb/SoftCam.Key"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

AUTO_UPDATE = True
AUTO_UPDATE_HOURS = 12

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

# ---------- SCROLL SCREEN ----------
class ScrollText(Screen):
    skin = """
    <screen name="ScrollText" position="center,center" size="900,600" title="BISS Keys">
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
        self["key"].setText(" ".join(v[i:i+4] for i in range(0, 32, 4)))

    def save(self):
        if len(self.key) not in (16, 32):
            self.session.open(MessageBox, "Key must be 16 or 32 HEX", MessageBox.TYPE_ERROR)
            return
        if not re.match("^[0-9A-F]+$", self.key):
            self.session.open(MessageBox, "Invalid HEX characters", MessageBox.TYPE_ERROR)
            return
        self.callback(self.key)
        self.close()

# ---------- KEY LIST ----------
class KeyList(Screen):
    def __init__(self, session, keys, callback):
        Screen.__init__(self, session)
        self.callback = callback
        self["list"] = MenuList(keys)
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close}, -1
        )

    def ok(self):
        self.callback(self["list"].getCurrent())
        self.close()

# ---------- AUTO UPDATER ----------
class AutoUpdater:
    def __init__(self):
        self.timer = eTimer()
        self.timer.callback.append(self.run)
        self.start()

    def start(self):
        self.timer.startLongTimer(AUTO_UPDATE_HOURS * 3600)

    def run(self):
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
        log("Auto update done")

        if os.path.exists("/etc/init.d/softcam"):
            os.system("/etc/init.d/softcam restart")

        self.start()

# ---------- MAIN ----------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
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
            "Exit"
        ]

        self["menu"] = MenuList(self.menu)
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close}, -1
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
        line = f"F {ids['sid']} {ids['tsid']} {ids['onid']} {mode} {key} ; {ids['name']}"
        shutil.copy(BISS_FILE, BACKUP_FILE)
        lines = [l for l in open(BISS_FILE) if not l.startswith(f"F {ids['sid']} {ids['tsid']} {ids['onid']}")]
        lines.append(line + "\n")
        open(BISS_FILE, "w").writelines(lines)
        self.restart()

    def view(self):
        txt = open(BISS_FILE).read() or "No Keys"
        self.session.open(ScrollText, txt)

    def deleteKey(self):
        lines = [l.strip() for l in open(BISS_FILE) if l.startswith("F ")]
        if lines:
            self.session.open(KeyList, lines, self.confirmDelete)

    def confirmDelete(self, line):
        def go(ans):
            if ans:
                shutil.copy(BISS_FILE, BACKUP_FILE)
                lines = open(BISS_FILE).read().splitlines()
                open(BISS_FILE, "w").write("\n".join([l for l in lines if l != line]) + "\n")
                self.restart()

        self.session.openWithCallback(go, MessageBox, "Delete key?\n\n" + line, MessageBox.TYPE_YESNO)

    def mergeGit(self):
        self.session.openWithCallback(
            lambda a: a and AutoUpdater().run(),
            MessageBox,
            "Merge from GitHub?",
            MessageBox.TYPE_YESNO
        )

    def exportUSB(self):
        if os.path.exists("/media/usb"):
            shutil.copy(BISS_FILE, USB_PATH)

    def importUSB(self):
        if os.path.exists(USB_PATH):
            self.session.openWithCallback(
                lambda a: a and shutil.copy
