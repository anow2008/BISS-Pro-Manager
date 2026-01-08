from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.InputBox import InputBox
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from enigma import eServiceCenter
import os
import time

BISS_FILE = "/etc/tuxbox/config/SoftCam.Key"
BACKUP_DIR = "/etc/tuxbox/config/biss_backup"

def backupKeys():
    if not os.path.exists(BACKUP_DIR):
        os.mkdir(BACKUP_DIR)
    t = time.strftime("%Y%m%d_%H%M%S")
    os.system("cp %s %s/SoftCam.Key.%s" % (BISS_FILE, BACKUP_DIR, t))

class BissPro(Screen):
    skin = """
    <screen position="center,center" size="600,400" title="BISS Pro Manager">
        <widget name="list" position="10,10" size="580,300"/>
        <widget name="info" position="10,320" size="580,60" font="Regular;18"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["info"] = Label(
            "أحمر: إضافة | أخضر: حذف | أصفر: Restart Cam | أزرق: Backup"
        )

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions"],
            {
                "red": self.addKey,
                "green": self.deleteKey,
                "yellow": self.restartCam,
                "blue": self.makeBackup,
                "cancel": self.close
            }, -1
        )

        self.loadKeys()

    def loadKeys(self):
        keys = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r") as f:
                for line in f:
                    if line.strip().startswith("F"):
                        keys.append(line.strip())
        self["list"] = MenuList(keys)

    def getCurrentSID(self):
        service = self.session.nav.getCurrentService()
        info = service and service.info()
        if info:
            return hex(info.getInfo(info.sSID))
        return "1FFF"

    def addKey(self):
        sid = self.getCurrentSID()
        example = "F %s XXXXXXXX YYYYYYYY ; Channel Name" % sid
        self.session.openWithCallback(
            self.saveKey,
            InputBox,
            title="أدخل شفرة BISS",
            text=example
        )

    def saveKey(self, key):
        if key:
            backupKeys()
            with open(BISS_FILE, "a") as f:
                f.write("\n" + key)
            self.loadKeys()
            self.message("تمت إضافة الشفرة بنجاح ✅")

    def deleteKey(self):
        sel = self["list"].getCurrent()
        if not sel:
            return
        self.session.openWithCallback(
            lambda x: self.confirmDelete(x, sel),
            MessageBox,
            "حذف الشفرة؟",
            MessageBox.TYPE_YESNO
        )

    def confirmDelete(self, answer, key):
        if answer:
            backupKeys()
            with open(BISS_FILE, "r") as f:
                lines = f.readlines()
            with open(BISS_FILE, "w") as f:
                for l in lines:
                    if l.strip() != key:
                        f.write(l)
            self.loadKeys()
            self.message("تم حذف الشفرة 🗑️")

    def restartCam(self):
        os.system("/etc/init.d/softcam restart")
        self.message("تم Restart SoftCam 🔄")

    def makeBackup(self):
        backupKeys()
        self.message("تم عمل Backup 💾")

    def message(self, text):
        self.session.open(
            MessageBox,
            text,
            MessageBox.TYPE_INFO,
            timeout=3
        )

def main(session, **kwargs):
    session.open(BissPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager",
        description="Full BISS Keys Manager",
        where=PluginDescriptor.WHERE_EXTENSIONSMENU,
        fnc=main
    )