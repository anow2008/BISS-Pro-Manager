from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
import os, time, urllib.request, shutil

# ==================================================
# PLUGIN INFO
# ==================================================
PLUGIN_NAME = "Biss Pro"
PLUGIN_VERSION = "v1.0"

# ==================================================
# PATHS
# ==================================================
SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key"
]

BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_FILE = BISS_FILE + ".bak"
USB_PATH = "/media/usb/SoftCam.Key"
CW_FILE = "/etc/tuxbox/config/constant.cw"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

SOFTCAM_BINARY = next(
    (p for p in ["/usr/bin/oscam", "/usr/bin/ncam"] if os.path.exists(p)),
    None
)

# ==================================================
# UTILS
# ==================================================
def ensureFile():
    if not os.path.exists(BISS_FILE):
        open(BISS_FILE, "w").close()

# ==================================================
# SCROLL SCREEN
# ==================================================
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
            {"ok": self.close, "cancel": self.close,
             "up": self["text"].pageUp,
             "down": self["text"].pageDown},
            -1
        )

# ==================================================
# HEX INPUT
# ==================================================
class HexKeyInput(Screen):
    skin = """
    <screen position="center,center" size="900,600" title="Enter BISS Key">
        <widget name="key" position="10,50" size="880,40" font="Regular;24"/>
        <widget name="list" position="10,120" size="880,300" font="Regular;22"/>
        <widget name="hint" position="10,440" size="880,40" font="Regular;18"/>
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

# ==================================================
# MAIN SCREEN
# ==================================================
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle(f"{PLUGIN_NAME} {PLUGIN_VERSION}")
        ensureFile()

        self.menu = [
            "Add / Edit BISS Key",
            "View Keys",
            "Delete Last Key",
            "Smart Merge from GitHub",
            "Import constant.cw",
            "Export Keys to USB",
            "Import Keys from USB",
            "Restore Backup",
            "Restart Softcam",
            "Exit"
        ]

        self["menu"] = MenuList(self.menu)
        self["status"] = Label(f"{PLUGIN_NAME} {PLUGIN_VERSION}")

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    # ------------------------------------------------
    def getIDs(self):
        s = self.session.nav.getCurrentService()
        if not s: return None
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
        open(BISS_FILE, "a").write(line + "\n")
        self.restart()

    def view(self):
        self.session.open(ScrollText, open(BISS_FILE).read() or "No Keys")

    def deleteKey(self):
        shutil.copy(BISS_FILE, BACKUP_FILE)
        lines = open(BISS_FILE).read().splitlines()
        open(BISS_FILE, "w").writelines([l+"\n" for l in lines[:-1]])
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
        self.restart()

    # ---------- constant.cw ----------
    def importConstantCW(self):
        if not os.path.exists(CW_FILE):
            self.session.open(MessageBox, "constant.cw not found", MessageBox.TYPE_ERROR)
            return

        added = 0
        existing = open(BISS_FILE).read() if os.path.exists(BISS_FILE) else ""

        for line in open(CW_FILE):
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split(":")
            if len(parts) < 6: continue

            sid = parts[1].upper().zfill(4)
            key = parts[-2].upper()
            if len(key) != 16: continue

            biss = f"F {sid} 0001 0001 00 {key} ; imported from constant.cw"
            if biss not in existing:
                open(BISS_FILE, "a").write(biss + "\n")
                added += 1

        if added:
            self.session.open(MessageBox, f"Imported {added} keys", MessageBox.TYPE_INFO, timeout=5)
            self.restart()
        else:
            self.session.open(MessageBox, "No new keys found", MessageBox.TYPE_INFO, timeout=5)

    def exportUSB(self):
        if os.path.exists("/media/usb"):
            shutil.copy(BISS_FILE, USB_PATH)

    def importUSB(self):
        if os.path.exists(USB_PATH):
            shutil.copy(USB_PATH, BISS_FILE)
            self.restart()

    def restart(self):
        os.system("killall oscam 2>/dev/null; killall ncam 2>/dev/null")
        if os.path.exists("/etc/init.d/softcam"):
            os.system("/etc/init.d/softcam restart")
        elif SOFTCAM_BINARY:
            os.system(SOFTCAM_BINARY + " &")

    def ok(self):
        idx = self["menu"].getSelectionIndex()
        [
            self.addKey,
            self.view,
            self.deleteKey,
            self.mergeGit,
            self.importConstantCW,
            self.exportUSB,
            self.importUSB,
            lambda: shutil.copy(BACKUP_FILE, BISS_FILE) if os.path.exists(BACKUP_FILE) else None,
            self.restart,
            self.close
        ][idx]()

# ==================================================
# INIT
# ==================================================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name=f"{PLUGIN_NAME} {PLUGIN_VERSION}",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
