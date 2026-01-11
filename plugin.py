from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from gettext import bindtextdomain, dgettext
import os, time

PluginLanguageDomain = "BISSPro"
PluginLanguagePath = "Extensions/BISSPro/locale"

bindtextdomain(
    PluginLanguageDomain,
    resolveFilename(SCOPE_PLUGINS, PluginLanguagePath)
)

def _(txt):
    return dgettext(PluginLanguageDomain, txt)

BISS_FILE = "/etc/tuxbox/config/SoftCam.Key"

class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="720,420" title="BISS Pro Manager">
        <widget name="menu" position="20,20" size="680,300" font="Regular;22" />
        <widget name="hint" position="20,340" size="680,50" font="Regular;18" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)

        self.menu = [
            _("Add BISS Key"),
            _("View Keys"),
            _("Delete Key"),
            _("Restart Oscam"),
            _("About"),
            _("Exit")
        ]

        self["menu"] = MenuList(self.menu)
        self["hint"] = Label("RED:Add  GREEN:View  YELLOW:Delete  BLUE:Restart")

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
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
        elif idx == 3: self.restartOscam()
        elif idx == 4: self.about()
        else: self.close()

    def getSID(self):
        service = self.session.nav.getCurrentService()
        if not service:
            return None
        info = service.info()
        return "%04X" % info.getInfo(info.sSID)

    def addKey(self):
        self.sid = self.getSID()
        if not self.sid:
            self.session.open(MessageBox, _("No active channel"), MessageBox.TYPE_ERROR)
            return

        self.session.openWithCallback(
            self.saveKey,
            InputBox,
            title=_("Enter BISS / BISS-E Key"),
            text=""
        )

    def saveKey(self, key):
        if not key:
            return
        key = key.replace(" ", "").upper()

        if len(key) not in (16, 32):
            self.session.open(MessageBox, _("Invalid Key Length"), MessageBox.TYPE_ERROR)
            return

        line = "F %s %s ; Added %s\n" % (self.sid, key, time.strftime("%Y-%m-%d"))

        try:
            with open(BISS_FILE, "r") as f:
                if key in f.read():
                    self.session.open(MessageBox, _("Key already exists"), MessageBox.TYPE_INFO)
                    return
        except:
            pass

        with open(BISS_FILE, "a") as f:
            f.write("\n" + line)

        self.restartOscam()
        self.session.open(MessageBox, _("Key saved successfully"), MessageBox.TYPE_INFO)

    def showKeys(self):
        try:
            with open(BISS_FILE, "r") as f:
                data = [x.strip() for x in f if x.startswith("F ")]
        except:
            data = [_("No keys found")]

        self.session.open(KeysViewer, data)

    def deleteKey(self):
        try:
            with open(BISS_FILE, "r") as f:
                self.lines = [x.strip() for x in f if x.startswith("F ")]
        except:
            self.lines = []

        if not self.lines:
            self.session.open(MessageBox, _("No keys to delete"), MessageBox.TYPE_INFO)
            return

        self.session.openWithCallback(
            self.confirmDelete,
            KeysViewer,
            self.lines,
            True
        )

    def confirmDelete(self, line):
        if not line:
            return

        with open(BISS_FILE, "r") as f:
            data = f.read()

        data = data.replace(line, "")

        with open(BISS_FILE, "w") as f:
            f.write(data)

        self.restartOscam()
        self.session.open(MessageBox, _("Key deleted"), MessageBox.TYPE_INFO)

    def restartOscam(self):
        os.system("killall -9 oscam 2>/dev/null")
        time.sleep(1)
        os.system("oscam &")

    def about(self):
        self.session.open(
            MessageBox,
            "BISS Pro Manager\nVersion 1.0\nOpenATV 7.6\nVU+",
            MessageBox.TYPE_INFO
        )

class KeysViewer(Screen):
    skin = """
    <screen position="center,center" size="720,420" title="BISS Keys">
        <widget name="list" position="20,20" size="680,380" />
    </screen>
    """

    def __init__(self, session, data, selectable=False):
        Screen.__init__(self, session)
        self.selectable = selectable
        self["list"] = MenuList(data)

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {
                "ok": self.ok,
                "cancel": self.close
            }, -1
        )

    def ok(self):
        if self.selectable:
            self.close(self["list"].getCurrent())
        else:
            self.close()

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="BISS Pro Manager",
        description="Professional BISS/BISS-E Manager",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="plugin.png",
        fnc=main
    )
