# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, RT_VALIGN_CENTER
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
import os, re, shutil
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

PLUGIN_PATH = os.path.dirname(__file__)
ICON_PATH = os.path.join(PLUGIN_PATH, "icons")

def get_softcam_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/ncam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/oscam/SoftCam.Key"

class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.skin = """
        <screen position="center,center" size="1100,750" title="BissPro Manager v4.2 (Final Match)">
            <widget name="menu" position="20,20" size="1060,550" itemHeight="110" transparent="1"/>
            <eLabel position="50,600" size="1000,2" backgroundColor="#444444" />
            <widget name="status" position="50,650" size="1000,60" font="Regular;30" halign="center" valign="center" transparent="1" foregroundColor="#3498db"/>
        </screen>"""
        self["status"] = Label("Ready")
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
                MultiContentEntryPixmapAlphaTest(pos=(25, 15), size=(80, 80), png=pix),
                MultiContentEntryText(pos=(130, 25), size=(800, 60), font=0, text=text, flags=RT_VALIGN_CENTER)
            ]))
        self["menu"].l.setList(lst)

    def unified_save(self, key, name):
        service = self.session.nav.getCurrentService()
        if not service: return False
        info = service.info()
        raw_sid = info.getInfo(iServiceInformation.sSID) & 0xFFFF
        raw_vpid = info.getInfo(iServiceInformation.sVideoPID)
        hex_sid = "%04X" % raw_sid
        hex_vpid = "%04X" % (raw_vpid & 0xFFFF) if raw_vpid != -1 else "0000"
        combined_id = (hex_sid + hex_vpid).upper().zfill(8)
        target = get_softcam_path()
        try:
            os.system("chmod 644 %s" % target)
            os.system("sed -i '/F %s/d' %s" % (combined_id, target))
            new_line = "F %s 00000000 %s ;%s" % (combined_id, key.upper(), name)
            os.system('echo "%s" >> %s' % (new_line, target))
            os.system("killall -9 oscam ncam >/dev/null 2>&1")
            return combined_id
        except: return False

    def ok(self):
        curr = self["menu"].getCurrent()
        if curr and curr[0] == "add": self.session.openWithCallback(self.manual_done, HexInputScreen)
        elif curr and curr[0] == "auto":
            self["status"].setText("Searching Online...")
            Thread(target=self.do_auto).start()

    def manual_done(self, key=None):
        if not key: return
        name = self.session.nav.getCurrentService().info().getName()
        res_id = self.unified_save(key, name)
        self.res = (True, "Saved: %s" % res_id) if res_id else (False, "Error")
        self.timer.start(100, True)

    def do_auto(self):
        try:
            service = self.session.nav.getCurrentService()
            info = service.info()
            
            # بيانات القناة الحالية
            c_name = info.getName().upper().replace(" ", "")
            sid_hex = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
            
            tp_info = info.getInfoObject(iServiceInformation.sTransponderData)
            freq = str(tp_info.get("frequency", 0))[:4] # نأخذ أول 4 أرقام للتردد لضمان المطابقة المرنة (مثل 1167)

            # طلب الملف مع User-Agent لمنع الحجب
            url = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urlopen(req, timeout=10).read().decode("utf-8")
            
            found_key = None
            for line in data.splitlines():
                line_up = line.upper()
                # شرط البحث: الـ SID يجب أن يكون موجوداً
                if sid_hex in line_up:
                    # مطابقة إضافية بالتردد أو الاسم
                    if freq in line_up or c_name in line_up.replace(" ", ""):
                        match = re.search(r'([0-9A-Fa-f]{16})', line)
                        if match:
                            found_key = match.group(1)
                            break
            
            if found_key:
                res_id = self.unified_save(found_key, info.getName())
                self.res = (True, "Success matched!\nID: %s\nKey: %s" % (res_id, found_key))
            else:
                self.res = (False, "No match found for SID %s" % sid_hex)
                
        except Exception as e:
            self.res = (False, "Error: %s" % str(e))
        self.timer.start(100, True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, timeout=6)
        self["status"].setText("Ready")

class HexInputScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.skin = """
        <screen position="center,center" size="900,550" title="BISS Input" backgroundColor="#121212">
            <eLabel position="0,0" size="900,80" backgroundColor="#3498db" zPosition="-1" />
            <widget name="keylabel" position="60,110" size="780,90" font="Regular;60" halign="center" valign="center" foregroundColor="#3498db" backgroundColor="#1f1f1f" transparent="0" />
            <widget name="hexlist" position="350,230" size="200,220" itemHeight="70" font="Regular;50" selectionColor="#3498db" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="415,480" size="30,30" alphatest="on" />
            <widget name="key_green" position="455,480" size="150,30" font="Regular;22" />
        </screen>"""
        self.key = ""
        self["keylabel"] = Label("")
        self["key_green"] = Label("Save")
        self["hexlist"] = MenuList(["A", "B", "C", "D", "E", "F"])
        self["actions"] = ActionMap(["OkCancelActions", "NumberActions", "DirectionActions", "ColorActions"], {
            "ok": self.add_from_list, "cancel": self.close, "green": self.save,
            "up": self["hexlist"].up, "down": self["hexlist"].down,
            "0": lambda: self.add("0"), "1": lambda: self.add("1"), "2": lambda: self.add("2"), "3": lambda: self.add("3"),
            "4": lambda: self.add("4"), "5": lambda: self.add("5"), "6": lambda: self.add("6"), "7": lambda: self.add("7"),
            "8": lambda: self.add("8"), "9": lambda: self.add("9")}, -1)
        self.update_label()

    def update_label(self):
        d = self.key + "_" * (16 - len(self.key))
        self["keylabel"].setText(" ".join([d[i:i+4] for i in range(0, 16, 4)]))

    def add(self, n):
        if len(self.key) < 16: self.key += n; self.update_label()

    def add_from_list(self):
        self.add(self["hexlist"].getCurrent())

    def save(self):
        if len(self.key) == 16: self.close(self.key)
        else: self.session.open(MessageBox, "Need 16 chars!", MessageBox.TYPE_ERROR)

def main(session, **kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name="BissPro", description="v4.2 Final Stable", icon="plugin.png", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
