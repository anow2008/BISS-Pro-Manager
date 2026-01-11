from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, fileExists
from gettext import bindtextdomain, dgettext
import os, time, urllib.request
from Crypto.Cipher import AES
import base64

PluginLanguageDomain = "BISSPro"
PluginLanguagePath = "Extensions/BISSPro/locale"
bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))
def _(txt): return dgettext(PluginLanguageDomain, txt)

BISS_FILE = "/etc/tuxbox/config/SoftCam.Key"
USB_PATH = "/media/usb/SoftCam.Key"
BACKUP_PATH = "/etc/tuxbox/config/SoftCam.Key.bak"
LOG_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/BISSPro/debug.log"
SKIN_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/BISSPro/skin.xml"
SECRET_KEY = b"MySecretKey12345"
DEBUG_MODE = True

def log(msg):
    if DEBUG_MODE:
        try:
            with open(LOG_FILE, "a") as f:
                f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        except: pass

def encrypt_line(line):
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    padding = 16 - len(line) % 16
    line_padded = line + " " * padding
    encrypted = cipher.encrypt(line_padded.encode())
    return base64.b64encode(encrypted).decode()

def decrypt_line(enc_line):
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    decoded = base64.b64decode(enc_line)
    decrypted = cipher.decrypt(decoded).decode().rstrip()
    return decrypted

# ---------------------- واجهة إضافة الشفرة StarSat ----------------------
class AddKeyScreen(Screen):
    skin = """
    <screen name="AddKeyScreen" position="center,center" size="600,200" title="Add BISS Key">
        <widget name="label" position="20,20" size="560,40" font="Regular;22" halign="center" valign="center"/>
        <widget name="keyinput" position="20,80" size="560,50" font="Regular;24"/>
    </screen>
    """
    def __init__(self, session, sid, callback):
        Screen.__init__(self, session)
        self.sid = sid
        self.callback = callback
        self["label"] = Label("Channel SID: %s\nEnter BISS / BISS-E Key:" % sid)
        self["keyinput"] = InputBox()
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.okPressed, "cancel": self.close}, -1)

    def okPressed(self):
        key = self["keyinput"].getText().replace(" ","").upper()
        if key:
            self.callback(key)
        self.close()

# ---------------------- Main Plugin Screen ----------------------
class BISSPro(Screen):
    def __init__(self, session):
        if fileExists(SKIN_FILE):
            with open(SKIN_FILE) as f:
                skin_data = f.read()
            Screen.__init__(self, session, screen=skin_data)
        else:
            Screen.__init__(self, session)

        self.menu = [
            _("Add BISS Key"),
            _("View Keys"),
            _("Delete Key"),
            _("Import from USB"),
            _("Restore Backup"),
            _("Update Keys from GitHub"),
            _("Restart Oscam"),
            _("About"),
            _("Exit")
        ]
        self["menu"] = MenuList(self.menu)
        self["hint"] = Label("RED:Add  GREEN:View  YELLOW:Delete  BLUE:Restart")
        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions"],
            {
                "ok": self.okPressed,
                "red": self.addKey,
                "green": self.showKeys,
                "yellow": self.deleteKey,
                "blue": self.restartOscam,
                "cancel": self.close
            }, -1
        )

    def okPressed(self):
        idx = self["menu"].getSelectionIndex()
        if idx == 0: self.addKey()
        elif idx == 1: self.showKeys()
        elif idx == 2: self.deleteKey()
        elif idx == 3: self.importUSB()
        elif idx == 4: self.restoreBackup()
        elif idx == 5: self.updateKeysFromGit()
        elif idx == 6: self.restartOscam()
        elif idx == 7: self.about()
        else: self.close()

    def getSID(self):
        service = self.session.nav.getCurrentService()
        if not service: return None, None
        info = service.info()
        sid = "%04X" % info.getInfo(info.sSID)
        name = info.getName() or "Unknown"
        return sid, name

    # ---------------------- إضافة شفرة يدوي ----------------------
    def addKey(self):
        sid, name = self.getSID()
        if not sid:
            self.session.open(MessageBox, _("No active channel"), MessageBox.TYPE_ERROR)
            return
        self.session.open(AddKeyScreen, sid, lambda key: self.saveKey(key, sid, name))

    def saveKey(self, key, sid, name):
        if not key: return
        if len(key) not in (16,32):
            self.session.open(MessageBox, _("Invalid Key Length"), MessageBox.TYPE_ERROR)
            return
        line = "F %s %s ; %s %s" % (sid, key, name, time.strftime("%Y-%m-%d"))
        line_enc = encrypt_line(line)
        if os.path.exists(BISS_FILE):
            os.system("cp %s %s" % (BISS_FILE, BACKUP_PATH))
            log("Backup created")
        with open(BISS_FILE,"a") as f:
            f.write("\n"+line_enc)
        self.restartOscam()
        log("Key added")
        self.session.open(MessageBox, _("Key saved successfully"), MessageBox.TYPE_INFO)

    # ---------------------- استعراض الشفرات ----------------------
    def showKeys(self):
        try:
            with open(BISS_FILE,"r") as f:
                lines = f.readlines()
            data = [decrypt_line(l.strip()) for l in lines if l.strip()]
        except:
            data = [_("No keys found")]
        self.session.open(KeysViewer, data)

    # ---------------------- حذف شفرة ----------------------
    def deleteKey(self):
        try:
            with open(BISS_FILE,"r") as f:
                lines = f.readlines()
            self.lines = [l.strip() for l in lines if l.strip()]
        except:
            self.lines = []

        if not self.lines:
            self.session.open(MessageBox, _("No keys to delete"), MessageBox.TYPE_INFO)
            return
        self.session.openWithCallback(self.confirmDelete, KeysViewer, self.lines, True)

    def confirmDelete(self, line):
        if not line: return
        enc_line = encrypt_line(line)
        with open(BISS_FILE,"r") as f:
            data = f.read()
        data = data.replace(enc_line,"")
        with open(BISS_FILE,"w") as f:
            f.write(data)
        self.restartOscam()
        log("Key deleted")
        self.session.open(MessageBox, _("Key deleted"), MessageBox.TYPE_INFO)

    # ---------------------- استيراد من USB ----------------------
    def importUSB(self):
        if not os.path.exists(USB_PATH):
            self.session.open(MessageBox, _("SoftCam.Key not found on USB"), MessageBox.TYPE_ERROR)
            return
        os.system("cp %s %s" % (USB_PATH,BISS_FILE))
        self.restartOscam()
        log("Imported SoftCam.Key from USB")
        self.session.open(MessageBox, _("Imported from USB ✅"), MessageBox.TYPE_INFO)

    # ---------------------- استرجاع Backup ----------------------
    def restoreBackup(self):
        if not os.path.exists(BACKUP_PATH):
            self.session.open(MessageBox, _("No backup found"), MessageBox.TYPE_ERROR)
            return
        os.system("cp %s %s" % (BACKUP_PATH,BISS_FILE))
        self.restartOscam()
        log("Backup restored")
        self.session.open(MessageBox, _("Backup restored"), MessageBox.TYPE_INFO)

    # ---------------------- سحب الشفرات من GitHub ----------------------
    def updateKeysFromGit(self):
        GIT_RAW_URL = "https://raw.githubusercontent.com/YourUsername/YourRepo/main/SoftCam.Key"

        if os.path.exists(BISS_FILE):
            os.system("cp %s %s" % (BISS_FILE, BACKUP_PATH))
            log("Backup created before Git update")

        try:
            response = urllib.request.urlopen(GIT_RAW_URL)
            git_keys = response.read().decode('utf-8').splitlines()

            existing_keys = []
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE,"r") as f:
                    existing_keys = [l.strip() for l in f.readlines() if l.strip()]

            new_keys = []
            for key in git_keys:
                key = key.strip()
                if key and key not in existing_keys:
                    new_keys.append(key)

            if new_keys:
                with open(BISS_FILE,"a") as f:
                    for nk in new_keys:
                        f.write("\n"+nk)
                log("Added %d new keys from GitHub" % len(new_keys))
                self.session.open(MessageBox, _("Added %d new keys from GitHub") % len(new_keys), MessageBox.TYPE_INFO)
            else:
                self.session.open(MessageBox, _("No new keys to add from GitHub"), MessageBox.TYPE_INFO)

            self.restartOscam()
            log("Oscam restarted after GitHub update")
        except Exception as e:
            log("Error updating keys from GitHub: %s" % str(e))
            self.session.open(MessageBox, _("Error updating keys from GitHub:\n%s") % str(e), MessageBox.TYPE_ERROR)

    # ---------------------- إعادة تشغيل Oscam / NCAM ----------------------
    def restartOscam(self):
        os.system("killall -9 oscam 2>/dev/null")
        os.system("killall -9 ncam 2>/dev/null")
        time.sleep(1)
        os.system("oscam &")
        log("Oscam restarted")

    # ---------------------- About ----------------------
    def about(self):
        self.session.open(MessageBox, "BISS Pro Manager\nVersion 1.3\nOpenATV 7.6\nVU+", MessageBox.TYPE_INFO)

# ---------------------- Viewer للشفرات ----------------------
class KeysViewer(Screen):
    skin = """
    <screen position="center,center" size="720,480" title="BISS Keys">
        <widget name="list" position="20,20" size="680,440"/>
    </screen>
    """
    def __init__(self, session, data, selectable=False):
        Screen.__init__(self, session)
        self.selectable = selectable
        self["list"] = MenuList(data)
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.ok, "cancel": self.close}, -1)

    def ok(self):
        if self.selectable:
            self.close(self["list"].getCurrent())
        else:
            self.close()

# ---------------------- Main Plugin ----------------------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager",
        description="Professional BISS/BISS-E Manager with GitHub update",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="plugin.png",
        fnc=main
    )
