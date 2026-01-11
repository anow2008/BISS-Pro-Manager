from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, fileExists
from gettext import bindtextdomain, dgettext
import os, time
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
        elif idx == 5: self.restartOscam()
        elif idx == 6: self.about()
        else: self.close()

    def getSID(self):
        service = self.session.nav.getCurrentService()
        if not service: return None, None
        info = service.info()
        sid = "%04X" % info.getInfo(info.sSID)
        name = info.getName() or "Unknown"
        return sid, name

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

    # باقي الدوال showKeys, deleteKey, importUSB, restoreBackup, restartOscam, about كما هي...
