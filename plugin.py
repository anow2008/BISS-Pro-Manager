from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS
from gettext import bindtextdomain, dgettext
import os, time, urllib.request

# ------------------------- Paths -------------------------
BISS_FILE = "/etc/tuxbox/config/SoftCam.Key"
BACKUP_FILE = "/etc/tuxbox/config/SoftCam.Key.bak"
UPDATE_FLAG = "/tmp/bisspro_last_update"
GITHUB_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/softcam.key"
SKIN_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/BISSPro/skin.xml"

# ------------------------- Translation -------------------------
PluginLanguageDomain = "BISSPro"
PluginLanguagePath = "Extensions/BISSPro/locale"
bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))
def _(txt): return dgettext(PluginLanguageDomain, txt)

# ================= HEX INPUT SCREEN =================
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
        self["hint"] = Label(_("RED=DEL  YELLOW=ADD  EXIT=Cancel"))

        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions","NumberActions"],
            {
                "ok": self.ok,
                "red": self.delete,
                "yellow": self.save,
                "cancel": self.close,
                "0": lambda: self.addChar("0"),
                "1": lambda: self.addChar("1"),
                "2": lambda: self.addChar("2"),
                "3": lambda: self.addChar("3"),
                "4": lambda: self.addChar("4"),
                "5": lambda: self.addChar("5"),
                "6": lambda: self.addChar("6"),
                "7": lambda: self.addChar("7"),
                "8": lambda: self.addChar("8"),
                "9": lambda: self.addChar("9"),
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
        view = self.key.ljust(32, "-")
        self["key"].setText(" ".join(view[i:i+4] for i in range(0, 32, 4)))

    def save(self):
        if len(self.key) not in (16, 32):
            self.session.open(MessageBox, _("Key must be 16 or 32 HEX"), MessageBox.TYPE_ERROR)
            return
        self.callback(self.key)
        self.close()


# ================= MAIN PLUGIN =================
class BISSPro(Screen):
    def __init__(self, session):
        if os.path.exists(SKIN_FILE):
            with open(SKIN_FILE) as f:
                skin_data = f.read()
            Screen.__init__(self, session, screen=skin_data)
        else:
            Screen.__init__(self, session)

        self.session = session
        self.menu = [
            _("Add BISS Key"),
            _("View Keys"),
            _("Delete Key"),
            _("Update from GitHub"),
            _("Restart Softcam"),
            _("Exit")
        ]
        self["menu"] = MenuList(self.menu)
        self["hint"] = Label(_("RED:Add  GREEN:View  YELLOW:Delete  BLUE:Restart"))

        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions"],
            {
                "ok": self.okPressed,
                "red": self.addKey,
                "green": self.showKeys,
                "yellow": self.deleteKey,
                "blue": self.restartSoftcam,
                "cancel": self.close
            }, -1
        )

        self.autoUpdateGit()

    # ---------- Utilities ----------
    def getSID(self):
        service = self.session.nav.getCurrentService()
        if not service:
            return None, None
        info = service.info()
        sid = "%04X" % info.getInfo(info.sSID)
        name = info.getName()
        return sid, name

    # ---------- Add / Edit Key ----------
    def addKey(self):
        sid, name = self.getSID()
        if not sid:
            self.session.open(MessageBox, _("No active channel"), MessageBox.TYPE_ERROR)
            return

        existing_key = ""
        if os.path.exists(BISS_FILE):
            for line in open(BISS_FILE):
                if line.strip().startswith("F %s " % sid):
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        existing_key = parts[3]
                    break

        self.session.open(HexKeyInput, lambda key: self.saveKey(key, sid, name), existing_key)

    # ---------- Save / Update ----------
    def updateOrAddKey(self, sid, new_line):
        lines = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("F %s " % sid):
                lines[i] = new_line + "\n"
                found = True
                break
        if not found:
            lines.append(new_line + "\n")
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)
        return found

    def saveKey(self, key, sid, name):
        key = key.replace(" ", "").upper()
        if len(key) == 16: mode="00"
        elif len(key) == 32: mode="01"
        else:
            self.session.open(MessageBox,_("Invalid Key Length"),MessageBox.TYPE_ERROR)
            return
        channel_name = name.replace("\n","").strip()
        date = time.strftime("%Y-%m-%d")
        line = f"F {sid} {mode} {key} ; {channel_name} | {date}"
        if os.path.exists(BISS_FILE):
            os.system(f"cp {BISS_FILE} {BACKUP_FILE}")
        updated = self.updateOrAddKey(sid,line)
        self.restartSoftcam()
        msg = _("Key updated for channel:\n%s") % channel_name if updated else _("Key added for channel:\n%s") % channel_name
        self.session.open(MessageBox,msg,MessageBox.TYPE_INFO)

    # ---------- Show ----------
    def showKeys(self):
        try:
            with open(BISS_FILE) as f:
                data = f.readlines()
        except:
            data = [_("No keys")]
        self.session.open(KeysViewer,data)

    # ---------- Delete ----------
    def deleteKey(self):
        try:
            self.lines = [l.strip() for l in open(BISS_FILE) if l.strip()]
        except:
            self.lines = []
        if not self.lines:
            self.session.open(MessageBox,_("No keys"),MessageBox.TYPE_INFO)
            return
        self.session.openWithCallback(self.confirmDelete, KeysViewer,self.lines, True)

    def confirmDelete(self,line):
        with open(BISS_FILE) as f:
            data = f.read().replace(line,"")
        with open(BISS_FILE,"w") as f:
            f.write(data)
        self.restartSoftcam()

    # ---------- GitHub AutoUpdate ----------
    def autoUpdateGit(self):
        today = time.strftime("%Y%m%d")
        if fileExists(UPDATE_FLAG):
            with open(UPDATE_FLAG) as f:
                if f.read().strip()==today: return
        try:
            data=urllib.request.urlopen(GITHUB_URL,timeout=8).read().decode("utf-8")
            if os.path.exists(BISS_FILE): os.system(f"cp {BISS_FILE} {BACKUP_FILE}")
            with open(BISS_FILE,"w") as f: f.write(data)
            with open(UPDATE_FLAG,"w") as f: f.write(today)
            self.restartSoftcam()
        except: pass

    # ---------- Restart OSCam / NCam ----------
    def restartSoftcam(self):
        os.system("killall -9 oscam 2>/dev/null")
        os.system("killall -9 ncam 2>/dev/null")
        time.sleep(1)
        if os.path.exists("/usr/bin/oscam"):
            os.system("oscam &")
        elif os.path.exists("/usr/bin/ncam"):
            os.system("ncam &")

    # ---------- OK ----------
    def okPressed(self):
        idx=self["menu"].getSelectionIndex()
        if idx==0: self.addKey()
        elif idx==1: self.showKeys()
        elif idx==2: self.deleteKey()
        elif idx==3: self.autoUpdateGit()
        elif idx==4: self.restartSoftcam()
        else: self.close()


# ================= VIEWER =================
class KeysViewer(Screen):
    skin = """
    <screen name="KeysViewer" position="center,center" size="720,480" title="Keys">
        <widget name="list" position="20,20" size="680,440"/>
    </screen>
    """
    def __init__(self,session,data,select=False):
        Screen.__init__(self,session)
        self.select=select
        self["list"]=MenuList(data)
        self["actions"]=ActionMap(["OkCancelActions"],{"ok":self.ok,"cancel":self.close},-1)
    def ok(self):
        if self.select: self.close(self["list"].getCurrent())
        else: self.close()


# ================= PLUGIN INIT =================
def main(session,**kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager",
        description="Universal BISS Manager with GitHub Auto Update + Edit Keys + OSCam/NCam Support",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )

