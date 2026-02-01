# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
from urllib.request import urlopen, urlretrieve
import os, re, shutil

# المسارات الديناميكية
PLUGIN_PATH = os.path.dirname(__file__)
ICON_PATH = os.path.join(PLUGIN_PATH, "icons")

def get_softcam_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/ncam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/oscam/SoftCam.Key"

class AutoScale:
    def __init__(self):
        d = getDesktop(0).size()
        self.scale = min(d.width() / 1920.0, d.height() / 1080.0)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(18, v * self.scale))

class BISSPro(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v3.3">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(550)}" itemHeight="{self.ui.px(110)}" scrollbarMode="showOnDemand" transparent="1"/>
            <eLabel position="{self.ui.px(50)},{self.ui.px(600)}" size="{self.ui.px(1000)},{self.ui.px(2)}" backgroundColor="#333333" />
            <widget name="progress" position="{self.ui.px(50)},{self.ui.px(620)}" size="{self.ui.px(1000)},{self.ui.px(15)}" transparent="1" />
            <widget name="status" position="{self.ui.px(50)},{self.ui.px(650)}" size="{self.ui.px(1000)},{self.ui.px(60)}" font="Regular;{self.ui.font(30)}" halign="center" valign="center" transparent="1" foregroundColor="#f0a30a"/>
        </screen>"""
        self["status"] = Label("Ready")
        self["progress"] = ProgressBar()
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {"ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)
        self.timer = eTimer()
        try: self.timer.callback.append(self.show_result)
        except: self.timer.timeout.connect(self.show_result)
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [("Add BISS Manually", "add", "add.png"), ("Update SoftCam.Key", "upd", "update.png"), ("Auto Add BISS", "auto", "autoadd.png")]
        lst = []
        for text, action, icon_name in items:
            p = os.path.join(ICON_PATH, icon_name)
            pix = LoadPixmap(path=p) if os.path.exists(p) else None
            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(25), self.ui.px(15)), size=(self.ui.px(80), self.ui.px(80)), png=pix),
                MultiContentEntryText(pos=(self.ui.px(130), self.ui.px(25)), size=(self.ui.px(800), self.ui.px(60)), font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_sid = full_id.zfill(8).upper()
        try:
            os.system(f"sed -i '/F {full_sid}/d' {target}")
            new_entry = f"F {full_sid} 00000000 {key.upper()} ;{name}"
            os.system(f'echo "{new_entry}" >> {target}')
            os.system("killall -9 oscam ncam >/dev/null 2>&1")
            if os.path.exists("/etc/init.d/softcam"): os.system("/etc/init.d/softcam restart >/dev/null 2>&1")
            return True
        except: return False

    def ok(self):
        curr = self["menu"].getCurrent()
        if curr and curr[0] == "add": self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif curr:
            service = self.session.nav.getCurrentService()
            if curr[0] == "upd": Thread(target=self.do_update).start()
            else: Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key=None):
        if not key: return
        service = self.session.nav.getCurrentService()
        if service:
            info = service.info()
            raw_sid, raw_vpid = info.getInfo(iServiceInformation.sSID), info.getInfo(iServiceInformation.sVideoPID)
            combined_id = "%04X%04X" % (raw_sid & 0xFFFF, raw_vpid & 0xFFFF if raw_vpid != -1 else 0)
            if self.save_biss_key(combined_id, key, info.getName()): self.res = (True, f"Saved: {combined_id}")
            else: self.res = (False, "Error")
            self.timer.start(100, True)

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            self.res = (True, "Updated")
        except: self.res = (False, "Error")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
            vpid = info.getInfo(iServiceInformation.sVideoPID)
            combined = "%s%04X" % (sid, vpid & 0xFFFF if vpid != -1 else 0)
            data = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt").read().decode("utf-8")
            m = re.search(sid + r'.*?([0-9A-Fa-f]{16})', data, re.I)
            if m and self.save_biss_key(combined, m.group(1), info.getName()): self.res = (True, "Auto Saved")
            else: self.res = (False, "Not Found")
        except: self.res = (False, "Error")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(900)},{self.ui.px(500)}" title="BISS KEY INPUT" backgroundColor="#1a1a1a">
            <eLabel position="0,0" size="900,80" backgroundColor="#f0a30a" zPosition="-1" />
            <widget name="title" position="20,10" size="860,60" font="Regular;{self.ui.font(38)}" halign="center" valign="center" transparent="1" />
            <eLabel position="50,110" size="800,100" backgroundColor="#333333" cornerRadius="10" />
            <widget name="keylabel" position="60,120" size="780,80" font="Regular;{self.ui.font(50)}" halign="center" valign="center" foregroundColor="#f0a30a" backgroundColor="#333333" transparent="1" />
            
            <widget name="hexlist" position="350,230" size="200,200" itemHeight="{self.ui.px(60)}" font="Regular;{self.ui.font(45)}" scrollbarMode="showNever" transparent="1" />
            
            <ePixmap pixmap="skin_default/buttons/green.png" position="380,440" size="30,30" alphatest="on" />
            <widget name="key_green" position="420,440" size="150,30" font="Regular;22" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="650,440" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="690,440" size="150,30" font="Regular;22" transparent="1" />
        </screen>"""
        self["title"] = Label("USE NUMBERS FOR 0-9 & MENU FOR A-F")
        self["keylabel"] = Label("")
        self["key_green"] = Label("SAVE")
        self["key_yellow"] = Label("DELETE")
        self.key = ""
        # هنا تم إخفاء الأرقام وترك الحروف فقط
        self["hexlist"] = MenuList(["A", "B", "C", "D", "E", "F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions"], {
            "ok": self.add_from_list, "cancel": self.close, "green": self.save, "yellow": self.backspace,
            "0": lambda: self.add("0"), "1": lambda: self.add("1"), "2": lambda: self.add("2"), "3": lambda: self.add("3"),
            "4": lambda: self.add("4"), "5": lambda: self.add("5"), "6": lambda: self.add("6"), "7": lambda: self.add("7"),
            "8": lambda: self.add("8"), "9": lambda: self.add("9")}, -1)
        self.update_label()

    def update_label(self):
        display = self.key + "_" * (16 - len(self.key))
        formatted = "  ".join([display[i:i+4] for i in range(0, 16, 4)])
        self["keylabel"].setText(formatted)

    def add(self, char):
        if len(self.key) < 16: self.key += char; self.update_label()

    def add_from_list(self):
        char = self["hexlist"].getCurrent()
        self.add(char)

    def backspace(self):
        if self.key: self.key = self.key[:-1]; self.update_label()

    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "Need 16 digits!", MessageBox.TYPE_ERROR)

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="v3.3 (A-F Only Menu)", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
