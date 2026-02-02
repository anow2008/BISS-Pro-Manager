# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.MultiContent import MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_HALIGN_CENTER
import os, re, shutil, time
from urllib.request import urlopen, urlretrieve

# مسار ملف الشفرات
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

def restart_softcam_global():
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
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager v1.0">
            <widget name="menu" position="{self.ui.px(50)},{self.ui.px(30)}" size="{self.ui.px(1000)},{self.ui.px(450)}" itemHeight="{self.ui.px(90)}" scrollbarMode="showOnDemand" transparent="1"/>
            
            <eLabel position="{self.ui.px(50)},{self.ui.px(500)}" size="{self.ui.px(1000)},{self.ui.px(2)}" backgroundColor="#333333" />
            
            <eLabel position="{self.ui.px(70)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#00ff00" />
            <eLabel text="Add Key" position="{self.ui.px(110)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            
            <eLabel position="{self.ui.px(300)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ffff00" />
            <eLabel text="Update" position="{self.ui.px(340)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            
            <eLabel position="{self.ui.px(530)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#0000ff" />
            <eLabel text="Auto" position="{self.ui.px(570)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            
            <eLabel position="{self.ui.px(760)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ff0000" />
            <eLabel text="Manage" position="{self.ui.px(800)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />

            <widget name="status" position="{self.ui.px(50)},{self.ui.px(620)}" size="{self.ui.px(1000)},{self.ui.px(80)}" font="Regular;{self.ui.font(32)}" halign="center" valign="center" transparent="1" foregroundColor="#f0a30a"/>
        </screen>"""
        
        self["status"] = Label("Select option or use Color Buttons")
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"], {
            "ok": self.ok, 
            "cancel": self.close, 
            "up": self["menu"].up, 
            "down": self["menu"].down,
            "green": self.action_add,
            "yellow": self.action_update,
            "blue": self.action_auto,
            "red": self.action_manage
        }, -1)
        
        self.timer = eTimer()
        try: self.timer.callback.append(self.show_result)
        except: self.timer.timeout.connect(self.show_result)
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        # القائمة تعتمد الآن على النص فقط مع خلفية أو فراغ للأيقونة
        items = [
            ("Add BISS Manually", "add"),
            ("Update SoftCam.Key File", "upd"),
            ("Auto Search Online", "auto"),
            ("Manage / Delete Stored Keys", "manage")
        ]
        lst = []
        for text, action in items:
            lst.append((action, [
                MultiContentEntryText(pos=(self.ui.px(20), self.ui.px(15)), size=(self.ui.px(950), self.ui.px(60)), font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)
        if hasattr(self["menu"].l, 'setFont'): self["menu"].l.setFont(0, gFont("Regular", self.ui.font(34)))

    def ok(self):
        curr = self["menu"].getCurrent()
        if curr:
            act = curr[0]
            if act == "add": self.action_add()
            elif act == "upd": self.action_update()
            elif act == "auto": self.action_auto()
            elif act == "manage": self.action_manage()

    def action_add(self):
        service = self.session.nav.getCurrentService()
        if service:
            self.session.openWithCallback(self.manual_done, HexInputScreen, service.info().getName())
        else:
            self.session.open(MessageBox, "No Active Channel!", MessageBox.TYPE_ERROR)

    def action_update(self):
        self["status"].setText("Updating Softcam... Please wait")
        Thread(target=self.do_update).start()

    def action_auto(self):
        service = self.session.nav.getCurrentService()
        if service:
            self["status"].setText("Searching Online Database...")
            Thread(target=self.do_auto, args=(service,)).start()
        else:
            self.session.open(MessageBox, "No Active Channel!", MessageBox.TYPE_ERROR)

    def action_manage(self):
        self.session.open(BissManagerList)

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
            self.res = (True, f"Key Saved: {info.getName()}")
        else:
            self.res = (False, "File Write Error")
        self.timer.start(100, True)

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        full_sid = full_id.zfill(8).upper()
        try:
            if not os.path.exists(target): os.system(f'touch {target}')
            os.system(f"sed -i '/F {full_sid}/d' {target}")
            new_entry = f"F {full_sid} 00000000 {key.upper()} ;{name}"
            os.system(f'echo "{new_entry}" >> {target}')
            restart_softcam_global()
            return True
        except: return False

    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path())
            restart_softcam_global()
            self.res = (True, "SoftCam File Updated Successfully")
        except: self.res = (False, "Server Connection Error")
        self.timer.start(100, True)

    def do_auto(self, service):
        try:
            info = service.info()
            raw_sid = info.getInfo(iServiceInformation.sSID)
            hex_sid = "%04X" % (raw_sid & 0xFFFF)
            raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
            hex_vpid = "%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000"
            combined_id = hex_sid + hex_vpid
            raw_data = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt", timeout=10).read().decode("utf-8")
            m = re.search(hex_sid + r'.*?([0-9A-Fa-f]{16})', raw_data, re.I)
            if m and self.save_biss_key(combined_id, m.group(1), info.getName()):
                self.res = (True, f"Found & Added: {info.getName()}")
            else:
                self.res = (False, f"No Key Found for SID: {hex_sid}")
        except: self.res = (False, "Online Server Error")
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready")

class BissManagerList(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1000)},{self.ui.px(700)}" title="BissPro v1.0 - Key Manager">
            <widget name="keylist" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(960)},{self.ui.px(550)}" itemHeight="{self.ui.px(50)}" scrollbarMode="showOnDemand" />
            <eLabel position="0,{self.ui.px(600)}" size="{self.ui.px(1000)},{self.ui.px(100)}" backgroundColor="#252525" />
            <eLabel position="{self.ui.px(30)},{self.ui.px(635)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ff0000" />
            <widget name="key_red" position="{self.ui.px(70)},{self.ui.px(630)}" size="{self.ui.px(300)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" halign="left" />
        </screen>"""
        self["keylist"] = MenuList([])
        self["key_red"] = Label("Delete Key")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close,
            "red": self.delete_confirm
        }, -1)
        self.onLayoutFinish.append(self.load_keys)

    def load_keys(self):
        path = get_softcam_path()
        keys = []
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    if line.strip().upper().startswith("F "):
                        keys.append(line.strip())
        self["keylist"].setList(keys)

    def delete_confirm(self):
        current = self["keylist"].getCurrent()
        if current:
            self.session.openWithCallback(self.delete_key, MessageBox, f"Confirm delete:\n{current}", MessageBox.TYPE_YESNO)

    def delete_key(self, answer):
        if answer:
            current = self["keylist"].getCurrent()
            path = get_softcam_path()
            try:
                safe_line = re.escape(current)
                os.system(f"sed -i '/{safe_line}/d' {path}")
                self.load_keys()
                restart_softcam_global()
            except: pass

class HexInputScreen(Screen):
    def __init__(self, session, channel_name=""):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="1000,500" title="BISS Editor v1.0" backgroundColor="#1a1a1a">
            <widget name="channel" position="10,20" size="980,50" font="Regular;32" halign="center" transparent="1" />
            <widget name="keylabel" position="10,100" size="980,100" font="Regular;65" halign="center" foregroundColor="#f0a30a" transparent="1" />
            <widget name="char_list" position="10,270" size="980,80" font="Regular;42" halign="center" foregroundColor="#00ff00" transparent="1" />
            <eLabel position="0,420" size="1000,80" backgroundColor="#252525" zPosition="-1" />
            <eLabel position="30,445" size="25,25" backgroundColor="#ff0000" zPosition="1" />
            <widget name="key_red" position="65,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="270,445" size="25,25" backgroundColor="#00ff00" zPosition="1" />
            <widget name="key_green" position="305,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="510,445" size="25,25" backgroundColor="#ffff00" zPosition="1" />
            <widget name="key_yellow" position="545,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="750,445" size="25,25" backgroundColor="#0000ff" zPosition="1" />
            <widget name="key_blue" position="785,440" size="160,35" font="Regular;24" halign="left" transparent="1" />
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
        self.chars = ["A","B","C","D","E","F"]
        self.char_index = 0
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "DirectionActions"], {
            "ok": self.confirm_digit, "cancel": self.close, "red": self.close, "green": self.save,
            "yellow": self.clear_current_digit, "blue": self.clear_all, "left": self.move_left, "right": self.move_right,
            "up": self.move_char_up, "down": self.move_char_down, "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), 
            "2": lambda: self.keyNum("2"), "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"), 
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"), "9": lambda: self.keyNum("9")}, -1)
        self.update_display()

    def update_display(self):
        d_text = "".join(["[%s]" % self.key_list[i] if i == self.index else self.key_list[i] for i in range(16)])
        self["keylabel"].setText(d_text)
        c_text = "  ".join(self.chars)
        current_char = self.chars[self.char_index]
        c_text = c_text.replace(current_char, " >%s< " % current_char)
        self["char_list"].setText(c_text)

    def move_char_up(self): self.char_index = (self.char_index - 1) % len(self.chars); self.update_display()
    def move_char_down(self): self.char_index = (self.char_index + 1) % len(self.chars); self.update_display()
    def confirm_digit(self): self.key_list[self.index] = self.chars[self.char_index]; self.index = min(15, self.index + 1); self.update_display()
    def keyNum(self, n): self.key_list[self.index] = n; self.index = min(15, self.index + 1); self.update_display()
    def move_left(self): self.index = max(0, self.index - 1); self.update_display()
    def move_right(self): self.index = min(15, self.index + 1); self.update_display()
    def clear_current_digit(self): self.key_list[self.index] = "0"; self.update_display()
    def clear_all(self): self.key_list = ["0"] * 16; self.index = 0; self.update_display()
    def save(self): self.close("".join(self.key_list))

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="Manager v1.0 Final", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
