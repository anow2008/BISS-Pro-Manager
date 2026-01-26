# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer
from Tools.LoadPixmap import LoadPixmap
from threading import Thread
import os, time, shutil, re
from datetime import datetime

# استيراد مكتبات الشبكة (دعم بايثون 2 و 3)
try:
    from urllib.request import urlopen, urlretrieve
except ImportError:
    from urllib2 import urlopen
    from urllib import urlretrieve

# ================== 1. الإعدادات والمسارات ==================
PLUGIN_NAME = "BissPro"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"

UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

TMP_BISS = "/tmp/biss.txt"
BISS_CACHE_TIME = 10 * 60  # تحديث الكاش كل 10 دقائق

# ================== 2. دوال معالجة الملفات والكام ==================

def get_key_path():
    """تحديد مسار ملف SoftCam.Key المعتمد في الجهاز"""
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def create_backup():
    """إنشاء نسخة احتياطية قبل التعديل"""
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        return b
    return None

def restartSoftcam():
    """إعادة تشغيل المحاكي النشط لتنشيط الشفرة الجديدة"""
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]
    active = next((c for c in cams if os.system("pgrep -x %s >/dev/null 2>&1" % c) == 0), None)
    for c in cams: os.system("killall %s 2>/dev/null" % c)
    time.sleep(2)
    for c in cams: os.system("pgrep -x %s >/dev/null || killall -9 %s 2>/dev/null" % (c, c))
    cam_to_run = active if active else "oscam"
    path = "/usr/bin/" + cam_to_run
    os.system("%s -b >/dev/null 2>&1 &" % (path if os.path.exists(path) else cam_to_run))

def clean_biss_key(key):
    """تنظيف الشفرة من المسافات والرموز غير الصحيحة"""
    return re.sub(r'[^0-9A-F]', '', key.upper())

def normalize(text):
    """تبسيط اسم القناة للمقارنة"""
    return ''.join(c for c in text.upper() if c.isalnum())

def get_biss_data():
    """جلب بيانات biss.txt مع دعم الكاش لتسريع الأداء"""
    if os.path.exists(TMP_BISS):
        if time.time() - os.path.getmtime(TMP_BISS) < BISS_CACHE_TIME:
            with open(TMP_BISS, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().upper()
    try:
        data = urlopen(BISS_TXT_URL, timeout=10).read()
        if isinstance(data, bytes): data = data.decode("utf-8", errors="ignore")
        data = data.upper()
        with open(TMP_BISS, "w", encoding="utf-8") as f: f.write(data)
        return data
    except: return None

# ================== 3. دالة البحث التلقائي (Auto Search) ==================

def import_biss_from_github(service):
    try:
        info = service.info()
        sid_int = info.getInfo(iServiceInformation.sSID)
        if sid_int is None: return False, "SID not found"
        sid_hex = "%08X" % sid_int
        cur_name = normalize(info.getName())
        transponder = info.getInfoObject(iServiceInformation.sTransponderData)
        if not transponder: return False, "No transponder info"
        
        freq = str(transponder.get("frequency", ""))[:5]
        data = get_biss_data()
        if not data: return False, "GitHub Connection Error"

        lines = [l.strip() for l in data.splitlines() if l.strip()]
        blocks, i = [], 0
        while i < len(lines):
            if "E" in lines[i] and len(lines[i]) <= 5:
                if i + 3 < len(lines): blocks.append(lines[i:i + 4])
                i += 4
            else: i += 1

        found = None
        for b in blocks:
            b_name = normalize(b[1])
            parts = b[2].split()
            b_freq = parts[0] if len(parts) > 0 else ""
            if b_freq == freq and (b_name == cur_name or sid_hex in b[3].replace(" ", "")):
                found = clean_biss_key(b[3])
                break

        if not found: return False, "No Key found in Database"
        
        new_line = "F %s 00000000 %s ;%s" % (sid_hex, found, cur_name)
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                if any(l.strip() == new_line.strip() for l in f): return False, "Key already exists"

        create_backup()
        with open(BISS_FILE, "a", encoding="utf-8") as f: f.write(new_line + "\n")
        restartSoftcam()
        return True, "Success: Key Added!"
    except Exception as e: return False, str(e)

# ================== 4. واجهات المستخدم (Screens) ==================

class SelectKeyScreen(Screen):
    """شاشة عرض الشفرات الحالية للحذف أو التعديل"""
    skin = """<screen position="center,center" size="720,420" title="Manage Keys"><widget name="list" position="20,20" size="680,320"/></screen>"""
    
    def __init__(self, session, sid, callback):
        Screen.__init__(self, session)
        self.sid = sid
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.ok, "cancel": self.close}, -1)
        self.load()

    def load(self):
        items = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for l in f:
                    p = l.strip().split()
                    if len(p) >= 4 and p[0].upper() == "F" and p[1].upper() == self.sid.upper(): items.append((l.strip(), l.strip()))
        if not items: 
            self.session.open(MessageBox, "No keys found for this SID", MessageBox.TYPE_INFO, 3)
            self.close()
            return
        self["list"].setList(items)

    def ok(self):
        sel = self["list"].getCurrent()
        self.close(sel[0] if sel else None)

# شاشة إدخال الشفرة يدوياً
class EasyBissInput(Screen):
    skin = """<screen position="center,center" size="820,300" title="Manual BISS Entry">
                <widget name="key" position="110,100" size="600,80" font="Console;50" halign="center" valign="center" foregroundColor="#ffffff"/>
                <widget name="hexlist" position="720,100" size="80,200" itemHeight="40"/>
              </screen>"""
    def __init__(self, session, sid, mode="add", key_line=None, sname="Unknown"):
        Screen.__init__(self, session)
        self.sid, self.mode, self.key_line, self.sname = sid, mode, key_line, sname
        self.key, self.pos, self.allchars = list("0000000000000000"), 0, list("0123456789ABCDEF")
        if key_line:
            p = key_line.split()
            if len(p) >= 4 and len(p[3]) == 16: self.key = list(p[3])
        self["key"], self["hexlist"] = Label(""), MenuList([(c, c) for c in "ABCDEF"])
        self["actions"] = ActionMap(["DirectionActions", "NumberActions", "ColorActions", "OkCancelActions"], {
            "left": self.left, "right": self.right, "up": self.up, "down": self.down, "ok": self.select_hex, "green": self.save, "cancel": self.close,
            **{str(i): (lambda x=str(i): self.set_num(x)) for i in range(10)}}, -1)
        self.refresh()

    def refresh(self): 
        self["key"].setText("".join(["[%s]" % c if i == self.pos else " %s " % c for i, c in enumerate(self.key)]))

    def left(self): 
        self.pos = (self.pos - 1) % 16
        self.refresh()

    def right(self): 
        self.pos = (self.pos + 1) % 16
        self.refresh()

    def up(self): 
        self.key[self.pos] = self.allchars[(self.allchars.index(self.key[self.pos]) + 1) % 16]
        self.right()

    def down(self): 
        self.key[self.pos] = self.allchars[(self.allchars.index(self.key[self.pos]) - 1) % 16]
        self.right()

    def set_num(self, c): 
        self.key[self.pos] = c
        self.right()

    def select_hex(self):
        sel = self["hexlist"].getCurrent()
        if sel: 
            self.key[self.pos] = sel[0]
            self.right()

    def save(self):
        new_line = "F %s 00000000 %s ;%s" % (self.sid, "".join(self.key), self.sname)
        create_backup()
        lines = []
        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f: 
                lines = [l.rstrip() for l in f]
        with open(BISS_FILE, "w", encoding="utf-8") as f:
            for l in lines:
                if self.mode == "edit" and self.key_line and l.strip() == self.key_line.strip(): continue
                if l.strip(): f.write(l + "\n")
            f.write(new_line + "\n")
        restartSoftcam()
        self.session.openWithCallback(lambda _: self.close(), MessageBox, "Key Saved!", MessageBox.TYPE_INFO, 3)

# ================== 5. القائمة الرئيسية للبلجن ==================

class BISSPro(Screen):
    skin = """<screen position="center,center" size="1024,768" title="BissPro Manager">
                <widget name="menu" position="40,100" size="940,540" itemHeight="150" scrollbarMode="showOnDemand"/>
                <widget name="status" position="40,650" size="940,50" font="Regular;28" halign="center" valign="center" foregroundColor="#00ff00"/>
              </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [("Add Key", "add", "add.png"), ("Edit Key", "edit", "edit.png"), ("Delete Key", "delete", "delete.png"), ("Update SoftCam", "update", "update.png"), ("Auto Add", "auto_add", "auto_add.png")]
        self.menu_list = [(a, [MultiContentEntryPixmapAlphaTest(pos=(10, 10), size=(128, 128), png=LoadPixmap(ICON_PATH + i)), MultiContentEntryText(pos=(160, 50), size=(760, 60), font=0, text=t)]) for t, a, i in self.menu_items]
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", 32))
        self["status"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {"ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)

    def ok(self):
        sel = self["menu"].getCurrent()
        service = self.session.nav.getCurrentService()
        if not sel or not service: return
        action, info = sel[0], service.info()
        sid, sname = "%08X" % info.getInfo(iServiceInformation.sSID), info.getName().replace(' ', '_')
        if action == "add": 
            self.session.open(EasyBissInput, sid, "add", None, sname)
        elif action in ("edit", "delete"): 
            self.session.openWithCallback(lambda l: self.handle(action, sid, l, sname), SelectKeyScreen, sid, lambda x: x)
        elif action == "update": 
            self.start_bg(lambda: self.bg_update(BISS_FILE), "Updating SoftCam...")
        elif action == "auto_add": 
            self.start_bg(lambda: self.bg_auto(service), "Searching GitHub...")

    def start_bg(self, target, msg): 
        self["status"].setText(msg)
        Thread(target=target).start()

    def bg_update(self, dest):
        try:
            create_backup()
            urlretrieve(UPDATE_URL, "/tmp/sc.tmp")
            if os.path.exists("/tmp/sc.tmp"): shutil.copy("/tmp/sc.tmp", dest)
            restartSoftcam()
            self.done(True, "SoftCam.Key Updated!")
        except: 
            self.done(False, "Download Failed")

    def bg_auto(self, s): 
        ok, msg = import_biss_from_github(s)
        self.done(ok, msg)

    def done(self, ok, msg): 
        self.res = (ok, msg)
        eTimer.singleShot(100, self.show_res)

    def show_res(self): 
        self["status"].setText("")
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, 3)

    def handle(self, action, sid, line, sname):
        if not line: return
        if action == "edit": 
            self.session.open(EasyBissInput, sid, "edit", line, sname)
        else: 
            self.session.openWithCallback(lambda c: self.del_k(c, line), MessageBox, "Delete this key?", MessageBox.TYPE_YESNO)

    def del_k(self, conf, line):
        if not conf: return
        create_backup()
        lines = []
        with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        with open(BISS_FILE, "w", encoding="utf-8") as f:
            done = False
            for l in lines:
                if not done and l.strip() == line.strip(): 
                    done = True
                    continue
                f.write(l)
        restartSoftcam()
        self.session.open(MessageBox, "Deleted Successfully", MessageBox.TYPE_INFO, 3)

# ================== 6. تشغيل البلجن ==================
def main(session, **kwargs): 
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Pro BISS Keys Manager", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="plugin.png")]
