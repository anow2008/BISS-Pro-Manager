from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Tools.Directories import fileExists
import os, time, urllib.request

# ---------------- PATHS ----------------
SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key"
]
BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_FILE = BISS_FILE + ".bak"
UPDATE_FLAG = "/tmp/bisspro_last_update"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"

SOFTCAM_BINARY = None
for p in ("/usr/bin/oscam", "/usr/bin/ncam", "/usr/local/bin/oscam"):
    if os.path.exists(p):
        SOFTCAM_BINARY = p
        break

# ---------------- HEX INPUT ----------------
class HexKeyInput(Screen):
    def __init__(self, session, callback, existing_key=""):
        Screen.__init__(self, session)
        self.callback = callback
        self.key = existing_key.upper()

        self.keys = [
            "1","2","3","4",
            "5","6","7","8",
            "9","A","B","C",
            "D","E","F","0",
            "DEL","ADD"
        ]

        self["key"] = Label("")
        self["list"] = MenuList(self.keys, enableWrapAround=True)
        self["hint"] = Label("RED=DEL  YELLOW=ADD  EXIT=Cancel")

        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions","NumberActions"],
            {
                "ok": self.ok,
                "red": self.delete,
                "yellow": self.save,
                "cancel": self.close,
                **{str(i): lambda x=str(i): self.addChar(x) for i in range(10)}
            }, -1
        )
        self.update()

    def ok(self):
        sel = self["list"].getCurrent()
        if sel == "DEL":
            self.delete()
        elif sel == "ADD":
            self.save()
        else:
            self.addChar(sel)

    def addChar(self, ch):
        if len(self.key) < 32:
            self.key += ch
            self.update()

    def delete(self):
        self.key = self.key[:-1]
        self.update()

    def update(self):
        view = self.key.ljust(32,"-")
        self["key"].setText(" ".join(view[i:i+4] for i in range(0, 32, 4)))

    def save(self):
        if len(self.key) not in (16, 32):
            self.session.open(MessageBox, "Key must be 16 or 32 HEX", MessageBox.TYPE_ERROR)
            return
        self.callback(self.key)
        self.close()

# ---------------- MAIN ----------------
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="720,480" title="BISS Pro Manager">
        <widget name="menu" position="40,60" size="640,360"/>
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session

        self.menu = [
            "Add / Edit BISS Key (Auto Feed)",
            "View Keys",
            "Delete Key",
            "Update from GitHub (Smart Merge)",
            "Restart Softcam",
            "Exit"
        ]
        self["menu"] = MenuList(self.menu)

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    def getServiceIDs(self):
        s = self.session.nav.getCurrentService()
        if not s:
            return None
        i = s.info()
        return {
            "sid":  "%04X" % i.getInfo(i.sSID),
            "tsid": "%04X" % i.getInfo(i.sTSID),
            "onid": "%04X" % i.getInfo(i.sONID),
            "name": i.getName().strip()
        }

    def addKey(self):
        ids = self.getServiceIDs()
        if not ids: return
        self.session.open(
            HexKeyInput,
            lambda k: self.saveKey(
                ids["sid"], ids["tsid"], ids["onid"], k, ids["name"]
            )
        )

    def saveKey(self, sid, tsid, onid, key, name):
        mode = "00" if len(key)==16 else "01"
        date = time.strftime("%Y-%m-%d")
        line = f"F {sid} {tsid} {onid} {mode} {key} ; {name} | {date}"

        if os.path.exists(BISS_FILE):
            os.system(f"cp {BISS_FILE} {BACKUP_FILE}")

        lines = []
        if os.path.exists(BISS_FILE):
            for l in open(BISS_FILE):
                if not l.startswith(f"F {sid} {tsid} {onid}"):
                    lines.append(l)
        lines.append(line + "\n")

        with open(BISS_FILE, "w") as f:
            f.writelines(lines)

        self.restartSoftcam()

    def smartMergeGit(self):
        today = time.strftime("%Y%m%d")
        if fileExists(UPDATE_FLAG) and open(UPDATE_FLAG).read().strip() == today:
            return
        try:
            data = urllib.request.urlopen(GITHUB_URL, timeout=8).read().decode("utf-8")
            merged = {}

            if os.path.exists(BISS_FILE):
                for l in open(BISS_FILE):
                    if l.startswith("F "):
                        p = l.split()
                        k = f"{p[1]} {p[2]} {p[3]}"
                        merged[k] = l.strip()

            for l in data.splitlines():
                if l.startswith("F "):
                    p = l.split()
                    k = f"{p[1]} {p[2]} {p[3]}"
                    merged[k] = l.strip()

            if os.path.exists(BISS_FILE):
                os.system(f"cp {BISS_FILE} {BACKUP_FILE}")

            with open(BISS_FILE,"w") as f:
                for v in merged.values():
                    f.write(v + "\n")

            open(UPDATE_FLAG,"w").write(today)
            self.restartSoftcam()
        except Exception as e:
            self.session.open(MessageBox, str(e), MessageBox.TYPE_ERROR)

    def viewKeys(self):
        data = open(BISS_FILE).read() if os.path.exists(BISS_FILE) else "No Keys"
        self.session.open(MessageBox, data, MessageBox.TYPE_INFO)

    def deleteKey(self):
        if not os.path.exists(BISS_FILE): return
        lines = open(BISS_FILE).read().splitlines()
        self.session.openWithCallback(self.doDelete, MenuList, lines)

    def doDelete(self, line):
        if not line: return
        with open(BISS_FILE,"w") as f:
            f.writelines([l+"\n" for l in open(BISS_FILE).read().splitlines() if l!=line])
        self.restartSoftcam()

    def restartSoftcam(self):
        os.system("killall oscam 2>/dev/null")
        os.system("killall ncam 2>/dev/null")
        time.sleep(1)
        if SOFTCAM_BINARY:
            os.system(f"{SOFTCAM_BINARY} &")

    def ok(self):
        i = self["menu"].getSelectionIndex()
        if   i==0: self.addKey()
        elif i==1: self.viewKeys()
        elif i==2: self.deleteKey()
        elif i==3: self.smartMergeGit()
        elif i==4: self.restartSoftcam()
        else: self.close()

# ---------------- INIT ----------------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
