# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_HALIGN_CENTER, ePicLoad
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
from urllib.request import urlopen, urlretrieve
import os, re, shutil, time

# الحصول على مسار البلجن الحالي تلقائياً
CUR_PATH = os.path.dirname(__file__)

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

class AutoScale:
    def __init__(self):
        d = getDesktop(0).size()
        self.scale = min(d.width() / 1920.0, d.height() / 1080.0)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(20, v * self.scale))

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
        items = [
            ("Add BISS Manually", "add", "add.png"), 
            ("Update SoftCam.Key", "upd", "update.png"), 
            ("Auto Add BISS", "auto", "autoadd.png")
        ]
        lst = []
        for text, action, icon_name in items:
            # تجربة مسارين: مجلد icons أو المجلد الرئيسي
            p = os.path.join(CUR_PATH, "icons", icon_name)
            if not os.path.exists(p):
                p = os.path.join(CUR_PATH, icon_name)
            
            # استخدام LoadPixmap بشكل مباشر وبسيط لضمان التوافق
            pix = None
            if os.path.exists(p):
                pix = LoadPixmap(p)

            lst.append((action, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(30), self.ui.px(15)), size=(self.ui.px(80), self.ui.px(80)), png=pix),
                MultiContentEntryText(pos=(self.ui.px(140), self.ui.px(25)), size=(self.ui.px(850), self.ui.px(60)), font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)
        if hasattr(self["menu"].l, 'setFont'): self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    # --- الدوال الأساسية تظل ثابتة ---
    def ok(self):
        curr = self["menu"].getCurrent()
        if curr:
            action = curr[0]
            service = self.session.nav.getCurrentService()
            if action == "add" and service:
                self.session.openWithCallback(self.manual_done, HexInputScreen, service.info().getName())
            elif action == "upd":
                self["status"].setText("Updating..."); Thread(target=self.do_update).start()
            elif action == "auto":
                self["status"].setText("Searching..."); Thread(target=self.do_auto, args=(service,)).start()

    def manual_done(self, key=None):
        if not key: return
        service = self.session.nav.getCurrentService()
        if service:
            info = service.info()
            comb_id = "%04X%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF, info.getInfo(iServiceInformation.sVideoPID) & 0xFFFF if info.getInfo(iServiceInformation.sVideoPID) != -1 else 0)
            if self.save_biss_key(comb_id, key, info.getName()): self.res = (True, "Saved!")
            else: self.res = (False, "Error")
            self.timer.start(100, True)

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path()); os.system(f"chmod 644 {get_softcam_path()}")
            self.restart_softcam(); self.res = (True, "Updated")
        except: self.res = (False, "Fail")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
            raw = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt").read().decode("utf-8")
            m = re.search(sid + r'.*?([0-9A-Fa-f]{16})', raw, re.I)
            if m:
                vpid = "%04X" % (info.getInfo(iServiceInformation.sVideoPID) & 0xFFFF if info.getInfo(iServiceInformation.sVideoPID) != -1 else 0)
                if self.save_biss_key(sid+vpid, m.group(1), info.getName()): self.res = (True, "Auto Added")
                else: self.res = (False, "Write Err")
            else: self.res = (False, "Not Found")
        except: self.res = (False, "Server Err")
        self.timer.start(100, True)

    def restart_softcam(self):
        os.system("killall -9 oscam ncam 2>/dev/null; sleep 1")
        for s in ["/etc/init.d/softcam", "/etc/init.d/softcam.oscam", "/etc/init.d/softcam.ncam"]:
            if os.path.exists(s): os.system(f"{s} restart &")

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        try:
            os.system(f"sed -i '/F {full_id.upper()}/d' {target}")
            with open(target, "a") as f: f.write(f"F {full_id.upper()} 00000000 {key.upper()} ;{name}\n")
            self.restart_softcam(); return True
        except: return False

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=4)
        self["status"].setText("Ready")

# --- واجهة المفاتيح (HexInputScreen) مع إصلاح الألوان والحروف ---
class HexInputScreen(Screen):
    def __init__(self, session, ch_name=""):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="1000,500" title="BISS Editor" backgroundColor="#1a1a1a">
            <widget name="channel" position="10,20" size="980,50" font="Regular;32" halign="center" transparent="1" />
            <widget name="keylabel" position="10,100" size="980,100" font="Regular;65" halign="center" foregroundColor="#f0a30a" transparent="1" />
            <widget name="char_list" position="10,270" size="980,80" font="Regular;42" halign="center" foregroundColor="#00ff00" transparent="1" />
            <eLabel position="0,420" size="1000,80" backgroundColor="#252525" zPosition="-1" />
            <eLabel position="30,445" size="25,25" backgroundColor="#ff0000" />
            <widget name="key_red" position="65,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="270,445" size="25,25" backgroundColor="#00ff00" />
            <widget name="key_green" position="305,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="510,445" size="25,25" backgroundColor="#ffff00" />
            <widget name="key_yellow" position="545,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="750,445" size="25,25" backgroundColor="#0000ff" />
            <widget name="key_blue" position="785,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
        </screen>"""
        self["channel"], self["keylabel"], self["char_list"] = Label(ch_name), Label(""), Label("")
        self["key_red"], self["key_green"] = Label("EXIT"), Label("SAVE")
        self["key_yellow"], self["key_blue"] = Label("CLEAR"), Label("RESET")
        self.key_list, self.index, self.char_idx = ["0"]*16, 0, 0
        self.chars = "0123456789ABCDEF"
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "NumberActions"], {
            "ok": self.confirm, "cancel": self.close, "red": self.close, "green": self.save,
            "yellow": self.clr_one, "blue": self.clr_all, "left": self.L, "right": self.R, "up": self.U, "down": self.D,
            "0": lambda: self.keyN("0"), "1": lambda: self.keyN("1"), "2": lambda: self.keyN("2"), "3": lambda: self.keyN("3"),
            "4": lambda: self.keyN("4"), "5": lambda: self.keyN("5"), "6": lambda: self.keyN("6"), "7": lambda: self.keyN("7"),
            "8": lambda: self.keyN("8"), "9": lambda: self.keyN("9")}, -1)
        self.update()

    def update(self):
        txt = "".join(["[%s]" % self.key_list[i] if i == self.index else self.key_list[i] for i in range(16)])
        self["keylabel"].setText(txt)
        c_txt = "  ".join(self.chars).replace(self.chars[self.char_idx], "> %s <" % self.chars[self.char_idx])
        self["char_list"].setText(c_txt)
    def U(self): self.char_idx = (self.char_idx-1)%16; self.update()
    def D(self): self.char_idx = (self.char_idx+1)%16; self.update()
    def confirm(self): self.key_list[self.index] = self.chars[self.char_idx]; self.index = min(15, self.index+1); self.update()
    def keyN(self, n): self.key_list[self.index] = n; self.index = min(15, self.index+1); self.update()
    def L(self): self.index = max(0, self.index-1); self.update()
    def R(self): self.index = min(15, self.index+1); self.update()
    def clr_one(self): self.key_list[self.index] = "0"; self.update()
    def clr_all(self): self.key_list, self.index = ["0"]*16, 0; self.update()
    def save(self): self.close("".join(self.key_list))

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="v3.3 Final Fixed", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
