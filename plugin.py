# -*- coding: utf-8 -*-
# Biss Pro v1.0 – Stable Enhanced Version
from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eTimer
import os, shutil, time, urllib.request, ssl, threading

PLUGIN_NAME = "Biss Pro"
PLUGIN_VERSION = "1.0"

SOFTCAM_PATHS = [
    "/etc/tuxbox/config/SoftCam.Key",
    "/var/keys/SoftCam.Key",
    "/usr/keys/SoftCam.Key",
    "/usr/local/etc/SoftCam.Key",
]

BISS_FILE = next((p for p in SOFTCAM_PATHS if os.path.exists(p)), SOFTCAM_PATHS[0])
BACKUP_DIR = "/etc/tuxbox/config/bisspro_backups/"
MAX_BACKUPS = 3
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
SCHEDULE_CONFIG = "/etc/tuxbox/config/bisspro_schedule_config.txt"

# ---------------- Utils ----------------
def ensure():
    if not os.path.exists(BISS_FILE):
        open(BISS_FILE, "w").close()
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def backup():
    ensure()
    name = time.strftime("SoftCam.Key_%Y%m%d_%H%M%S")
    shutil.copy(BISS_FILE, os.path.join(BACKUP_DIR, name))
    files = sorted(os.listdir(BACKUP_DIR))
    while len(files) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, files.pop(0)))

def clean(lines):
    seen = set()
    out = []
    for l in lines:
        if l.strip() and l not in seen:
            seen.add(l)
            out.append(l)
    return out

def restartSoftcam():
    os.system("killall -15 oscam ncam 2>/dev/null")
    time.sleep(2)
    os.system("killall -9 oscam ncam 2>/dev/null")

def record_update_time():
    with open(os.path.join(BACKUP_DIR, "last_update.txt"), "w") as f:
        f.write(str(int(time.time())))

def read_schedule_config():
    if os.path.exists(SCHEDULE_CONFIG):
        try:
            with open(SCHEDULE_CONFIG) as f:
                parts = f.read().split(",")
                return int(parts[0]), parts[1].strip().upper() == "ON"
        except:
            return 3, True
    return 3, True

def write_schedule_config(hour, state):
    with open(SCHEDULE_CONFIG, "w") as f:
        f.write(f"{hour},{ 'ON' if state else 'OFF'}")

# ---------------- GUI Safe Helpers ----------------
def runOnMainThread(session, func, *args):
    try:
        session.timer = eTimer()
        session.timer.callback.append(lambda: func(*args))
        session.timer.start(10, False)
    except:
        pass

def safe_set_text(session, text):
    runOnMainThread(session, lambda: session["status"].setText(text))

def safe_set_progress(session, val):
    runOnMainThread(session, lambda: session["progress"].setValue(val))

# ---------------- Update Core ----------------
def update_keys_thread(session):
    backup()
    try:
        temp_file = BISS_FILE + ".tmp"
        context = ssl._create_unverified_context()

        def reporthook(blocknum, blocksize, totalsize):
            if totalsize > 0 and session:
                percent = int(blocknum * blocksize * 100 / totalsize)
                if percent <= 100:
                    safe_set_progress(session, percent)
                    safe_set_text(session, f"⏳ جاري التحميل: {percent}%")

        urllib.request.urlretrieve(UPDATE_URL, temp_file, reporthook)
        
        with open(temp_file, "r") as f:
            lines = clean(f.readlines())
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)
        if os.path.exists(temp_file): os.remove(temp_file)

        record_update_time()
        restartSoftcam()
        safe_set_text(session, "✅ تم تحديث المفاتيح بنجاح وإعادة تشغيل الايمو")
        safe_set_progress(session, 100)

        # تحذير إذا المفاتيح قليلة
        with open(BISS_FILE, "r") as f:
            count = sum(1 for l in f if l.startswith("BISS"))
        if count < 5:
            safe_set_text(session, "⚠️ عدد مفاتيح BISS قليل: " + str(count))

    except Exception as e:
        safe_set_text(session, f"❌ خطأ: {str(e)}")
        safe_set_progress(session, 0)

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    skin = """
        <screen name="BISSPro" position="center,center" size="600,500" title="Biss Pro v1.4">
            <widget name="menu" position="10,10" size="580,280" scrollbarMode="showOnDemand"/>
            <widget name="progress" position="20,310" size="560,25" backgroundColor="#222222" borderWidth="1" borderColor="#cccccc" />
            <widget name="status" position="10,350" size="580,130" font="Regular;22" halign="center" valign="center" foregroundColor="#ffffff" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        ensure()
        self.main_menu_items = [
            ("View Keys Count", "view"),
            ("Add/Edit BISS from Channel", "add"),
            ("Update & Schedule Options", "submenu"),
            ("Restart Softcam", "restart")
        ]
        self.update_menu_items = [
            ("Update Keys from Internet", "update_now"),
            ("Schedule Daily Update (ON/OFF & Hour)", "set_schedule"),
            ("Back", "back")
        ]
        self["menu"] = MenuList(self.main_menu_items)
        self["status"] = Label("مرحباً بك في Biss Pro v1.4")
        self["progress"] = ProgressBar()
        self["progress"].setValue(0)

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok,
            "cancel": self.close,
            "up": self["menu"].up,
            "down": self["menu"].down
        }, -1)

        # الموقت الذكي للتحقق اليومي
        self.schedule_timer = eTimer()
        self.schedule_timer.callback.append(self.check_daily_update)
        self.schedule_timer.start(60000, False)

    def check_daily_update(self):
        hour, state = read_schedule_config()
        now = time.localtime()
        if state and now.tm_hour == hour and now.tm_min == 0:
            self.start_update()

    def ok(self):
        sel = self["menu"].getCurrent()
        if not sel: return
        cmd = sel[1]

        if cmd == "view": self.view()
        elif cmd == "add": self.add_or_edit_BISS()
        elif cmd == "restart": 
            restartSoftcam()
            safe_set_text(self, "SoftCam تم إعادة تشغيله!")
        elif cmd == "submenu": self["menu"].setList(self.update_menu_items)
        elif cmd == "update_now": self.start_update()
        elif cmd == "set_schedule":
            self.session.openWithCallback(self.schedule_callback, MessageBox, 
                "أدخل الساعة (0-23) ثم مسافة ثم ON أو OFF\nمثال: 3 ON", MessageBox.TYPE_INPUT)
        elif cmd == "back": self["menu"].setList(self.main_menu_items)

    def start_update(self):
        safe_set_text(self, "⏳ جاري الاتصال بالسيرفر...")
        safe_set_progress(self, 0)
        threading.Thread(target=update_keys_thread, args=(self,)).start()

    def schedule_callback(self, value):
        if value:
            try:
                parts = value.split()
                hour = int(parts[0])
                state = parts[1].upper() == "ON"
                write_schedule_config(hour, state)
                safe_set_text(self, f"تم الحفظ: الساعة {hour}:00 ({'مفعل' if state else 'معطل'})")
            except:
                safe_set_text(self, "خطأ في الصيغة! استخدم: 3 ON")

    def view(self):
        try:
            with open(BISS_FILE, "r") as f:
                count = sum(1 for l in f if l.startswith("BISS"))
            safe_set_text(self, f"عدد شفرات BISS حالياً: {count}")
        except:
            safe_set_text(self, "الملف غير موجود")

    def add_or_edit_BISS(self):
        try:
            from enigma import iServiceInformation
            s = self.session.nav.getCurrentService()
            if not s: return
            info = s.info()
            sid, tsid, onid = info.getInfo(iServiceInformation.sSID), info.getInfo(iServiceInformation.sTSID), info.getInfo(iServiceInformation.sONID)
            key = "1234567890ABCDEF"
            line = "BISS %04X:%04X:%04X:%s" % (sid, tsid, onid, key)

            backup()
            # إضافة المفتاح أو تعديل المفتاح إذا موجود
            lines = []
            if os.path.exists(BISS_FILE):
                with open(BISS_FILE, "r") as f:
                    lines = f.readlines()
            found = False
            for i, l in enumerate(lines):
                if l.startswith("BISS %04X:%04X:%04X" % (sid, tsid, onid)):
                    lines[i] = line + "\n"
                    found = True
            if not found:
                lines.append(line + "\n")
            with open(BISS_FILE, "w") as f:
                f.writelines(clean(lines))
            restartSoftcam()
            safe_set_text(self, "تم إضافة/تعديل شفرة القناة بنجاح")
        except:
            safe_set_text(self, "فشل جلب بيانات القناة أو تعديل المفتاح")

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Biss Pro Smart Auto + Safe GUI v1.0", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
