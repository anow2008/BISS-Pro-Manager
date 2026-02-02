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

def get_softcam_path():
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/ncam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/oscam/SoftCam.Key"

PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = os.path.join(PLUGIN_PATH, "icons")

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
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v2.9">
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
        if hasattr(self["menu"].l, 'setFont'): self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_sid = full_id.zfill(8).upper()
        
        try:
            if not os.path.exists(target):
                os.system(f'touch {target}')
            os.system(f'chmod 644 {target}')

            # حذف الشفرة القديمة
            os.system(f"sed -i '/F {full_sid}/d' {target}")

            # إضافة الشفرة الجديدة
            new_entry = f"F {full_sid} 00000000 {key.upper()} ;{name}"
            os.system(f'echo "{new_entry}" >> {target}')
            
            # --- إعادة تشغيل السوفتكام لضمان التفعيل ---
            os.system("killall -9 oscam ncam >/dev/null 2>&1")
            if os.path.exists("/etc/init.d/softcam"):
                os.system("/etc/init.d/softcam restart >/dev/null 2>&1")
            elif os.path.exists("/etc/init.d/cardserver"):
                os.system("/etc/init.d/cardserver restart >/dev/null 2>&1")
            
            return True
        except:
            return False

    def ok(self):
        curr = self["menu"].getCurrent()
        action = curr[0] if curr else None
        service = self.session.nav.getCurrentService()
        if action == "add":
            self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif action in ["upd", "auto"]:
            self["progress"].setValue(30)
            if action == "upd":
                self["status"].setText("Updating...")
                Thread(target=self.do_update).start()
            else:
                self["status"].setText("Searching Online...")
                Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key=None):
        if not key: return
        service = self.session.nav.getCurrentService()
        if not service: return
        info = service.info()
        
        # استخراج SID + VPID
        raw_sid = info.getInfo(iServiceInformation.sSID)
        raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
        
        hex_sid = "%04X" % (raw_sid & 0xFFFF)
        hex_vpid = "%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000"
        combined_id = hex_sid + hex_vpid
        
        if self.save_biss_key(combined_id, key, info.getName()):
            self.res = (True, f"Saved & Restarted: {combined_id}")
        else:
            self.res = (False, "Write Error")
        self.timer.start(100, True)

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            os.system(f"chmod 644 {get_softcam_path()}")
            self.res = (True, "SoftCam Updated")
        except: self.res = (False, "Download Error")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            raw_sid = info.getInfo(iServiceInformation.sSID)
            raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
            
            hex_sid = "%04X" % (raw_sid & 0xFFFF)
            hex_vpid = "%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000"
            combined_id = hex_sid + hex_vpid
            
            raw_data = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt", timeout=10).read().decode("utf-8")
            m = re.search(hex_sid + r'.*?([0-9A-Fa-f]{16})', raw_data, re.I)
            
            if m and self.save_biss_key(combined_id, m.group(1), info.getName()):
                self.res = (True, f"Auto Saved & Restarted: {combined_id}")
            else:
                self.res = (False, f"Not Found: {hex_sid}")
        except: self.res = (False, "Server Error")
        self.timer.start(100, True)

    def show_result(self):
        self["progress"].setValue(100)
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready"); self["progress"].setValue(0)

class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(800)},{self.ui.px(550)}" title="BISS Key Input">
            <widget name="keylabel" position="20,20" size="760,60" font="Regular;{self.ui.font(44)}" halign="center" foregroundColor="#f0a30a" />
            <widget name="hexlist" position="250,100" size="300,300" itemHeight="{self.ui.px(60)}" font="Regular;{self.ui.font(36)}" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="40,430" size="30,30" alphatest="on" />
            <widget name="key_red" position="80,430" size="150,30" font="Regular;22" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="280,430" size="30,30" alphatest="on" />
            <widget name="key_green" position="320,430" size="150,30" font="Regular;22" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="520,430" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="560,430" size="150,30" font="Regular;22" />
        </screen>"""
        self["keylabel"] = Label("____ ____ ____ ____")
        self["key_red"] = Label("Exit"); self["key_green"] = Label("Save"); self["key_yellow"] = Label("Delete")
        self.key = ""
        self["hexlist"] = MenuList(["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions"], {
            "ok": self.add, "cancel": lambda: self.close(None), "red": lambda: self.close(None), "green": self.save, "yellow": self.backspace,
            "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), "2": lambda: self.keyNum("2"), "3": lambda: self.keyNum("3"),
            "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"), "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"),
            "8": lambda: self.keyNum("8"), "9": lambda: self.keyNum("9")}, -1)
    def update_label(self):
        d = self.key + "_" * (16 - len(self.key))
        self["keylabel"].setText(" ".join([d[i:i+4] for i in range(0, 16, 4)]))
    def add(self):
        if len(self.key) < 16: self.key += self["hexlist"].getCurrent(); self.update_label()
    def keyNum(self, n):
        if len(self.key) < 16: self.key += n; self.update_label()
    def backspace(self):
        if self.key: self.key = self.key[:-1]; self.update_label()
    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "16 digits required!", MessageBox.TYPE_ERROR)

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="Manager v2.9 (Restart Fixed)", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
