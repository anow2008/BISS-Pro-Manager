# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop, RT_VALIGN_CENTER
import os, re, shutil, time
from urllib.request import urlopen, urlretrieve
from threading import Thread

def get_softcam_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/ncam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/oscam/SoftCam.Key"

def restart_softcam_global():
    os.system("killall -9 oscam ncam vicardd gbox 2>/dev/null")
    time.sleep(1.2)
    scripts = ["/etc/init.d/softcam", "/etc/init.d/cardserver", "/etc/init.d/softcam.oscam", "/etc/init.d/softcam.ncam"]
    for s in scripts:
        if os.path.exists(s):
            os.system(f"'{s}' restart >/dev/null 2>&1")
            break

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
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Smart Sync v1.0">
            <widget name="menu" position="{self.ui.px(50)},{self.ui.px(30)}" size="{self.ui.px(1000)},{self.ui.px(450)}" itemHeight="{self.ui.px(90)}" scrollbarMode="showOnDemand" transparent="1"/>
            <eLabel position="{self.ui.px(50)},{self.ui.px(500)}" size="{self.ui.px(1000)},{self.ui.px(2)}" backgroundColor="#333333" />
            <eLabel position="{self.ui.px(70)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#00ff00" />
            <eLabel text="Add Key" position="{self.ui.px(110)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            <eLabel position="{self.ui.px(300)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ffff00" />
            <eLabel text="Update" position="{self.ui.px(340)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            <eLabel position="{self.ui.px(530)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#0000ff" />
            <eLabel text="Auto" position="{self.ui.px(570)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            <eLabel position="{self.ui.px(760)},{self.ui.px(540)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ff0000" />
            <eLabel text="Key Editor" position="{self.ui.px(800)},{self.ui.px(535)}" size="{self.ui.px(150)},{self.ui.px(40)}" font="Regular;{self.ui.font(26)}" transparent="1" />
            <widget name="status" position="{self.ui.px(50)},{self.ui.px(620)}" size="{self.ui.px(1000)},{self.ui.px(80)}" font="Regular;{self.ui.font(32)}" halign="center" valign="center" transparent="1" foregroundColor="#f0a30a"/>
        </screen>"""
        self["status"] = Label("Ready")
        self["menu"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.ok, "cancel": self.close, "green": self.action_add, "yellow": self.action_update, "blue": self.action_auto, "red": self.action_editor
        }, -1)
        self.timer = eTimer()
        try: self.timer_callback = self.show_result; self.timer.callback.append(self.timer_callback)
        except: self.timer.timeout.connect(self.show_result)
        self.onLayoutFinish.append(self.build_menu)

    def build_menu(self):
        items = [("Add BISS Manually", "add"), ("Update SoftCam.Key File", "upd"), ("Smart Auto Search (Internet)", "auto"), ("Key Editor (Edit/Delete)", "editor")]
        lst = []
        for text, action in items:
            lst.append((action, [MultiContentEntryText(pos=(self.ui.px(20), self.ui.px(15)), size=(self.ui.px(950), self.ui.px(60)), font=0, text=text, flags=RT_VALIGN_CENTER)]))
        self["menu"].l.setList(lst)
        if hasattr(self["menu"].l, 'setFont'): self["menu"].l.setFont(0, gFont("Regular", self.ui.font(34)))

    def ok(self):
        curr = self["menu"].getCurrent(); act = curr[0] if curr else ""
        if act == "add": self.action_add()
        elif act == "upd": self.action_update()
        elif act == "auto": self.action_auto()
        elif act == "editor": self.action_editor()

    def action_add(self):
        service = self.session.nav.getCurrentService()
        if service: self.session.openWithCallback(self.manual_done, HexInputScreen, service.info().getName())
        else: self.session.open(MessageBox, "No Active Channel!", MessageBox.TYPE_ERROR)

    def action_editor(self):
        self.session.open(BissManagerList)

    def manual_done(self, key=None):
        if not key: return
        service = self.session.nav.getCurrentService()
        if not service: return
        info = service.info()
        raw_sid = info.getInfo(iServiceInformation.sSID)
        raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
        combined_id = ("%04X" % (raw_sid & 0xFFFF)) + ("%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000")
        if self.save_biss_key(combined_id, key, info.getName()): self.res = (True, f"Saved: {info.getName()}")
        else: self.res = (False, "File Error")
        self.timer.start(100, True)

    def save_biss_key(self, full_id, key, name):
        target = get_softcam_path()
        try:
            lines = []
            if os.path.exists(target):
                with open(target, "r") as f:
                    for line in f:
                        if f"F {full_id.upper()}" not in line.upper(): lines.append(line)
            lines.append(f"F {full_id.upper()} 00000000 {key.upper()} ;{name}\n")
            with open(target, "w") as f: f.writelines(lines)
            restart_softcam_global()
            return True
        except: return False

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=5)
        self["status"].setText("Ready")

    def action_update(self): self["status"].setText("Updating..."); Thread(target=self.do_update).start()
    def do_update(self):
        try:
            urlretrieve("https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key", "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", get_softcam_path()); restart_softcam_global(); self.res = (True, "Updated")
        except: self.res = (False, "Error")
        self.timer.start(100, True)

    def action_auto(self):
        service = self.session.nav.getCurrentService()
        if service: self["status"].setText("Auto Search..."); Thread(target=self.do_auto, args=(service,)).start()
        else: self.session.open(MessageBox, "No Channel", MessageBox.TYPE_ERROR)

    def do_auto(self, service):
        try:
            info = service.info(); ch_name = info.getName(); t_data = info.getInfoObject(iServiceInformation.sTransponderData)
            curr_freq = str(int(t_data.get("frequency", 0) / 1000 if t_data.get("frequency", 0) > 50000 else t_data.get("frequency", 0)))
            raw_sid = info.getInfo(iServiceInformation.sSID); combined_id = ("%04X" % (raw_sid & 0xFFFF)) + ("%04X" % (info.getInfo(iServiceInformation.sVideoPID) & 0xFFFF))
            raw_data = urlopen("https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt", timeout=10).read().decode("utf-8")
            m = re.search(re.escape(curr_freq) + r'.*?' + re.escape(ch_name.split()[0].lower()) + r'.*?(([0-9A-Fa-f]{2}[\s\t]*){8})', raw_data, re.I | re.S)
            if m:
                key = m.group(1).replace(" ", "").upper()
                if self.save_biss_key(combined_id, key, ch_name): self.res = (True, f"Found: {key}")
                else: self.res = (False, "Save Error")
            else: self.res = (False, "Not Found")
        except Exception as e: self.res = (False, str(e))
        self.timer.start(100, True)

class BissManagerList(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1000)},{self.ui.px(700)}" title="BissPro - Key Editor">
            <widget name="keylist" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(960)},{self.ui.px(520)}" itemHeight="{self.ui.px(50)}" scrollbarMode="showOnDemand" />
            <eLabel position="0,{self.ui.px(560)}" size="{self.ui.px(1000)},{self.ui.px(140)}" backgroundColor="#252525" zPosition="-1" />
            <eLabel position="{self.ui.px(30)},{self.ui.px(590)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#00ff00" />
            <eLabel text="OK: Edit Key" position="{self.ui.px(75)},{self.ui.px(585)}" size="{self.ui.px(300)},{self.ui.px(40)}" font="Regular;26" transparent="1" />
            <eLabel position="{self.ui.px(30)},{self.ui.px(635)}" size="{self.ui.px(30)},{self.ui.px(30)}" backgroundColor="#ff0000" />
            <eLabel text="RED: Delete" position="{self.ui.px(75)},{self.ui.px(630)}" size="{self.ui.px(300)},{self.ui.px(40)}" font="Regular;26" transparent="1" />
        </screen>"""
        self["keylist"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"ok": self.edit_key, "cancel": self.close, "red": self.delete_confirm}, -1)
        self.onLayoutFinish.append(self.load_keys)

    def load_keys(self):
        path = get_softcam_path(); keys = []
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    if line.strip().upper().startswith("F "): keys.append(line.strip())
        self["keylist"].setList(keys)

    def edit_key(self):
        current = self["keylist"].getCurrent()
        if current:
            parts = current.split()
            if len(parts) >= 4:
                ch_name = current.split(";")[-1] if ";" in current else "Unknown"
                self.old_line = current
                self.session.openWithCallback(self.finish_edit, HexInputScreen, ch_name)

    def finish_edit(self, new_key=None):
        if new_key is None: return # حماية من الكراش عند الضغط على Exit
        path = get_softcam_path()
        parts = self.old_line.split()
        parts[3] = str(new_key).upper()
        new_line = " ".join(parts)
        try:
            with open(path, "r") as f: lines = f.readlines()
            with open(path, "w") as f:
                for line in lines:
                    if line.strip() == self.old_line.strip(): f.write(new_line + "\n")
                    else: f.write(line)
            self.load_keys(); restart_softcam_global()
        except: pass

    def delete_confirm(self):
        current = self["keylist"].getCurrent()
        if current: self.session.openWithCallback(self.delete_key, MessageBox, "Delete this key?", MessageBox.TYPE_YESNO)

    def delete_key(self, answer):
        if answer:
            current = self["keylist"].getCurrent(); path = get_softcam_path()
            try:
                with open(path, "r") as f: lines = f.readlines()
                with open(path, "w") as f:
                    for line in lines:
                        if line.strip() != current.strip(): f.write(line)
                self.load_keys(); restart_softcam_global()
            except: pass

class HexInputScreen(Screen):
    def __init__(self, session, channel_name=""):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        self.skin = f"""
        <screen position="center,center" size="1000,550" title="BISS Editor" backgroundColor="#1a1a1a">
            <widget name="channel" position="10,20" size="980,60" font="Regular;42" halign="center" foregroundColor="#00ff00" transparent="1" />
            <eLabel text="Use UP/DOWN to change Letters (A-F)" position="10,85" size="980,35" font="Regular;22" halign="center" foregroundColor="#aaaaaa" transparent="1" />
            <eLabel text="Use LEFT/RIGHT or Numbers to move" position="10,115" size="980,35" font="Regular;22" halign="center" foregroundColor="#aaaaaa" transparent="1" />
            <widget name="keylabel" position="10,170" size="980,120" font="Regular;80" halign="center" foregroundColor="#f0a30a" transparent="1" />
            <widget name="char_list" position="10,320" size="980,80" font="Regular;45" halign="center" foregroundColor="#ffffff" transparent="1" />
            <eLabel position="0,470" size="1000,80" backgroundColor="#252525" zPosition="-1" />
            <eLabel position="30,495" size="25,25" backgroundColor="#ff0000" zPosition="1" />
            <widget name="key_red" position="65,490" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="270,495" size="25,25" backgroundColor="#00ff00" zPosition="1" />
            <widget name="key_green" position="305,490" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="510,495" size="25,25" backgroundColor="#ffff00" zPosition="1" />
            <widget name="key_yellow" position="545,490" size="160,35" font="Regular;24" halign="left" transparent="1" />
            <eLabel position="750,495" size="25,25" backgroundColor="#0000ff" zPosition="1" />
            <widget name="key_blue" position="785,490" size="160,35" font="Regular;24" halign="left" transparent="1" />
        </screen>"""
        self["channel"] = Label(f"{channel_name}")
        self["keylabel"] = Label(""); self["char_list"] = Label("")
        self["key_red"] = Label("EXIT"); self["key_green"] = Label("SAVE")
        self["key_yellow"] = Label("CLEAR"); self["key_blue"] = Label("RESET")
        self.key_list = ["0"] * 16; self.index = 0; self.chars = ["A","B","C","D","E","F"]; self.char_index = 0
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions", "DirectionActions"], {
            "ok": self.confirm_digit, "cancel": self.exit_clean, "red": self.exit_clean, "green": self.save,
            "yellow": self.clear_current_digit, "blue": self.clear_all, "left": self.move_left, "right": self.move_right,
            "up": self.move_char_up, "down": self.move_char_down, "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), 
            "2": lambda: self.keyNum("2"), "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"), 
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"), "9": lambda: self.keyNum("9")}, -1)
        self.update_display()

    def update_display(self):
        d_text = "".join(["[%s]" % self.key_list[i] if i == self.index else self.key_list[i] for i in range(16)])
        self["keylabel"].setText(d_text)
        current_char = self.chars[self.char_index]
        self["char_list"].setText("  ".join(self.chars).replace(current_char, "> %s <" % current_char))

    def move_char_up(self): self.char_index = (self.char_index - 1) % len(self.chars); self.update_display()
    def move_char_down(self): self.char_index = (self.char_index + 1) % len(self.chars); self.update_display()
    def confirm_digit(self): self.key_list[self.index] = self.chars[self.char_index]; self.index = min(15, self.index + 1); self.update_display()
    def keyNum(self, n): self.key_list[self.index] = n; self.index = min(15, self.index + 1); self.update_display()
    def move_left(self): self.index = max(0, self.index - 1); self.update_display()
    def move_right(self): self.index = min(15, self.index + 1); self.update_display()
    def clear_current_digit(self): self.key_list[self.index] = "0"; self.update_display()
    def clear_all(self): self.key_list = ["0"] * 16; self.index = 0; self.update_display()
    def exit_clean(self): self.close(None) # إرسال None بوضوح عند الخروج
    def save(self): self.close("".join(self.key_list))

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro Smart", description="Auto Manager v1.0 Smart Sync", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
