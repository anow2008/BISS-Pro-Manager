# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_HALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
from urllib.request import urlopen, urlretrieve
import os, re, shutil, time

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

    def restart_softcam(self):
        os.system("killall -9 oscam ncam vicardd gbox 2>/dev/null")
        time.sleep(1.5)
        scripts = ["/etc/init.d/softcam", "/etc/init.d/cardserver", "/etc/init.d/softcam.oscam", "/etc/init.d/softcam.ncam"]
        restarted = False
        for s in scripts:
            if os.path.exists(s):
                os.system(f"{s} restart >/dev/null 2>&1")
                restarted = True; break
        if not restarted:
            if os.path.exists("/usr/bin/oscam"): os.system("/usr/bin/oscam -b &")
            elif os.path.exists("/usr/bin/ncam"): os.system("/usr/bin/ncam -b &")

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_sid = full_id.zfill(8).upper()
        try:
            if not os.path.exists(target): os.system(f'touch {target}')
            os.system(f'chmod 644 {target}')
            os.system(f"sed -i '/F {full_sid}/d' {target}")
            new_entry = f"F {full_sid} 00000000 {key.upper()} ;{name}"
            os.system(f'echo "{new_entry}" >> {target}')
            self.restart_softcam()
            return True
        except: return False

    def ok(self):
        curr = self["menu"].getCurrent()
        action = curr[0] if curr else None
        service = self.session.nav.getCurrentService()
        if action == "add":
            if service:
                info = service.info()
                sname = info.getName()
                self.session.openWithCallback(self.manual_done, HexInputScreen, sname)
            else:
                self.session.open(MessageBox, "No Active Channel!", MessageBox.TYPE_ERROR)
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
        raw_sid = info.getInfo(iServiceInformation.sSID)
        raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
        hex_sid = "%04X" % (raw_sid & 0xFFFF)
        hex_vpid = "%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000"
        combined_id = hex_sid + hex_vpid
        if self.save_biss_key(combined_id, key, info.getName()):
            self.res = (True, f"Saved & Restarted: {info.getName()}")
        else:
            self.res = (False, "Write Error")
        self.timer.start(100, True)

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            os.system(f"chmod 644 {get_softcam_path()}")
            self.restart_softcam()
            self.res = (True, "SoftCam Updated & Restarted")
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
                self.res = (True, f"Auto Added: {info.getName()}")
            else:
                self.res = (False, f"Not Found: {hex_sid}")
        except: self.res = (False, "Server Error")
        self.timer.start(100, True)

    def show_result(self):
        self["progress"].setValue(100)
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready"); self["progress"].setValue(0)

class HexInputScreen(Screen):
    def __init__(self, session, channel_name=""):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        # إزالة الاعتماد على الخطوط الخارجية واستخدام إحداثيات مركزية
        self.skin = f"""
        <screen position="center,center" size="1000,500" title="BISS Key Editor" backgroundColor="#101010">
            <widget name="channel" position="10,20" size="980,50" font="Regular;30" halign="center" transparent="1" foregroundColor="#ffffff" />
            
            <widget name="keylabel" position="10,100" size="980,100" font="Regular;60" halign="center" foregroundColor="#f0a30a" transparent="1" />
            
            <eLabel text="Select Char (Up/Down) then press OK:" position="10,220" size="980,40" font="Regular;25" halign="center" foregroundColor="#ffffff" transparent="1" />
            <widget name="char_list" position="10,270" size="980,80" font="Regular;45" halign="center" foregroundColor="#00ff00" transparent="1" />
            
            <eLabel position="0,420" size="1000,80" backgroundColor="#202020" />
            <widget name="key_red" position="20,440" size="200,40" font="Regular;22" halign="center" foregroundColor="#ff0000" />
            <widget name="key_green" position="260,440" size="200,40" font="Regular;22" halign="center" foregroundColor="#00ff00" />
            <widget name="key_yellow" position="500,440" size="200,40" font="Regular;22" halign="center" foregroundColor="#ffff00" />
            <widget name="key_blue" position="740,440" size="200,40" font="Regular;22" halign="center" foregroundColor="#0000ff" />
        </screen>"""
        
        self["channel"] = Label(f"CH: {channel_name}")
        self["keylabel"] = Label("")
        self["char_list"] = Label("")
        self["key_red"] = Label("EXIT")
        self["key_green"] = Label("SAVE")
        self["key_yellow"] = Label("CLEAR") 
        self["key_blue"] = Label("RESET")
        
        self.key_list = ["0"] * 16
        self.index = 0
        self.chars = ["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"]
        self.char_index = 0
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "DirectionActions"], {
            "ok": self.confirm_digit, 
            "cancel": self.close,
            "red": self.close, 
            "green": self.save,
            "yellow": self.clear_current_digit, 
            "blue": self.clear_all,
            "left": self.move_left, 
            "right": self.move_right,
            "up": self.move_char_up, 
            "down": self.move_char_down,
            "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), "2": lambda: self.keyNum("2"), 
            "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"), 
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"), 
            "9": lambda: self.keyNum("9")}, -1)
        self.update_display()

    def update_display(self):
        # عرض الشفرة الحالية
        d_text = ""
        for i in range(16):
            if i == self.index: d_text += "_%s_" % self.key_list[i]
            else: d_text += self.key_list[i]
            if (i + 1) % 4 == 0 and i < 15: d_text += " "
        self["keylabel"].setText(d_text)

        # عرض شريط الحروف بشكل مبسط جداً لضمان الظهور
        c_text = "  ".join(self.chars)
        # تمييز الحرف المختار بأسهم واضحة
        current_char = self.chars[self.char_index]
        c_text = c_text.replace(current_char, " >%s< " % current_char)
        self["char_list"].setText(c_text)

    def move_char_up(self):
        self.char_index = (self.char_index - 1) % len(self.chars)
        self.update_display()

    def move_char_down(self):
        self.char_index = (self.char_index + 1) % len(self.chars)
        self.update_display()

    def confirm_digit(self):
        self.key_list[self.index] = self.chars[self.char_index]
        if self.index < 15: self.index += 1
        self.update_display()

    def keyNum(self, n):
        self.key_list[self.index] = n
        if self.index < 15: self.index += 1
        self.update_display()

    def move_left(self):
        if self.index > 0: self.index -= 1
        self.update_display()

    def move_right(self):
        if self.index < 15: self.index += 1
        self.update_display()

    def clear_current_digit(self):
        self.key_list[self.index] = "0"
        self.update_display()

    def clear_all(self):
        self.key_list = ["0"] * 16
        self.index = 0
        self.update_display()

    def save(self):
        self.close("".join(self.key_list))

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="Manager v3.3 English Fixed", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
