from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Tools.Directories import fileExists
import os, time, urllib.request, shutil

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

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))

# ---------- HEX INPUT ----------
class HexKeyInput(Screen):
    def __init__(self, session, callback, existing=""):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = existing.upper()
        self.keys = ["1","2","3","4","5","6","7","8","9","A","B","C","D","E","F","0","DEL","ADD"]

        self["key"] = Label("")
        self["list"] = MenuList(self.keys, enableWrapAround=True)
        self["hint"] = Label("RED=DEL  YELLOW=SAVE  EXIT=Cancel")

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
        elif s == "ADD": self.save()
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

# ---------- MAIN ----------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session

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
        self["status"] = Label("Ready")

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close}, -1
        )

    # ---------- SERVICE ----------
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

    # ---------- ADD ----------
    def addKey(self):
        ids = self.getIDs()
        if not ids: return
        self.session.open(
            HexKeyInput,
            lambda k: self.saveKey(ids, k)
        )

    def saveKey(self, ids, key):
        mode = "00" if len(key)==16 else "01"
        line = f"F {ids['sid']} {ids['tsid']} {ids['onid']} {mode} {key} ; {ids['name']} | {time.strftime('%Y-%m-%d')}"
        shutil.copy(BISS_FILE, BACKUP_FILE)

        lines = [l for l in open(BISS_FILE) if not l.startswith(f"F {ids['sid']} {ids['tsid']} {ids['onid']}")]
        lines.append(line+"\n")
        open(BISS_FILE,"w").writelines(lines)
        log("Key saved")
        self.restart()

    # ---------- VIEW ----------
    def view(self):
        self.session.open(MessageBox, open(BISS_FILE).read(), MessageBox.TYPE_INFO)

    # ---------- DELETE ----------
    def delete(self):
        lines = open(BISS_FILE).read().splitlines()
        self.session.openWithCallback(self.doDelete, MenuList, lines)

    def doDelete(self, l):
        if not l: return
        shutil.copy(BISS_FILE, BACKUP_FILE)
        open(BISS_FILE,"w").writelines([x+"\n" for x in open(BISS_FILE).read().splitlines() if x!=l])
        log("Key deleted")
        self.restart()

    # ---------- MERGE ----------
    def mergeGit(self):
        data = urllib.request.urlopen(GITHUB_URL).read().decode()
        merged = {}

        for l in open(BISS_FILE):
            if l.startswith("F "):
                p=l.split(); merged[f"{p[1]} {p[2]} {p[3]}"]=l.strip()

        for l in data.splitlines():
            if l.startswith("F "):
                p=l.split(); merged[f"{p[1]} {p[2]} {p[3]}"]=l.strip()

        shutil.copy(BISS_FILE, BACKUP_FILE)
        open(BISS_FILE,"w").write("\n".join(merged.values())+"\n")
        log("GitHub merged")
        self.restart()

    # ---------- USB ----------
    def exportUSB(self):
        shutil.copy(BISS_FILE, USB_PATH)
        self["status"].setText("Exported to USB")

    def importUSB(self):
        if os.path.exists(USB_PATH):
            shutil.copy(USB_PATH, BISS_FILE)
            self.restart()

    # ---------- SOFTCAM ----------
    def restart(self):
        os.system("killall oscam 2>/dev/null; killall ncam 2>/dev/null")
        time.sleep(1)
        if SOFTCAM_BINARY:
            os.system(SOFTCAM_BINARY+" &")

    # ---------- OK ----------
    def ok(self):
        i = self["menu"].getSelectionIndex()
        [
            self.addKey, self.view, self.delete,
            self.mergeGit, self.exportUSB, self.importUSB,
            lambda: shutil.copy(BACKUP_FILE,BISS_FILE),
            self.restart, self.close
        ][i]()

# ---------- INIT ----------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager v2",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
