# -*- coding: utf-8 -*-
# Biss Pro v1.0 – Fully Auto Smart Enigma2 Plugin
# تحديث يومي في ساعة محددة + ON/OFF + شريط تقدم + قائمة فرعية للتحديث

from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
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
UPDATE_RECORD = "/etc/tuxbox/config/bisspro_last_update.txt"
UPDATE_CONFIG = "/etc/tuxbox/config/bisspro_update_config.txt"
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
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out

def restartSoftcam():
    os.system("killall -15 oscam ncam 2>/dev/null")
    time.sleep(2)
    os.system("killall -9 oscam ncam 2>/dev/null")

def record_update_time():
    with open(UPDATE_RECORD, "w") as f:
        f.write(str(int(time.time())))

def last_update_time():
    if os.path.exists(UPDATE_RECORD):
        with open(UPDATE_RECORD) as f:
            return int(f.read())
    return 0

# ---------------- Update Interval ----------------
def get_update_interval():
    if os.path.exists(UPDATE_CONFIG):
        try:
            with open(UPDATE_CONFIG) as f:
                h = int(f.read())
                return max(1, h)
        except:
            return 24
    return 24

def set_update_interval(hours):
    with open(UPDATE_CONFIG, "w") as f:
        f.write(str(hours))

# ---------------- Schedule Config ----------------
def read_schedule_config():
    """إرجاع (hour, on_off)"""
    if os.path.exists(SCHEDULE_CONFIG):
        try:
            with open(SCHEDULE_CONFIG) as f:
                parts = f.read().split(",")
                hour = int(parts[0])
                state = parts[1].strip().upper() == "ON"
                return hour, state
        except:
            return 3, True
    return 3, True  # افتراضي الساعة 03:00 ON

def write_schedule_config(hour, state):
    with open(SCHEDULE_CONFIG, "w") as f:
        f.write(f"{hour},{ 'ON' if state else 'OFF'}")

# ---------------- Update Keys ----------------
def update_keys_thread(session=None):
    backup()
    try:
        context = ssl._create_unverified_context()
        temp_file = BISS_FILE + ".tmp"

        def reporthook(blocknum, blocksize, totalsize):
            if totalsize > 0 and session:
                percent = int(blocknum*blocksize*100/totalsize)
                session["status"].setText(f"جاري التحميل: {percent}%")

        urllib.request.urlretrieve(UPDATE_URL, temp_file, reporthook)
        with open(temp_file) as f:
            lines = clean(f.readlines())
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)
        os.remove(temp_file)

        record_update_time()
        restartSoftcam()
        if session:
            session["status"].setText("✅ تم تحديث المفاتيح بنجاح")
    except Exception as e:
        if session:
            session["status"].setText(f"❌ خطأ أثناء التحديث: {e}")

def update_from_internet(session=None):
    threading.Thread(target=update_keys_thread, args=(session,)).start()

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    skin = """
        <screen name="BISSPro" position="center,center" size="600,500" title="Biss Pro v1.5">
            <widget name="menu" position="10,10" size="580,350" scrollbarMode="showOnDemand"/>
            <widget name="status" position="10,370" size="580,120" font="Regular;20" halign="center"/>
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        ensure()

        self.main_menu_items = [
            "View Keys Count",
            "Add BISS from Channel",
            "Restart Softcam",
            "Update & Schedule Options"
        ]
        self.update_menu_items = [
            "Update Keys from Internet",
            "Set Update Interval (hours)",
            "Schedule Daily Update ON/OFF & Hour",
            "Back"
        ]

        self["menu"] = MenuList(self.main_menu_items)
        self["status"] = Label("")

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            }, -1
        )

        # تفعيل الجدولة اليومية
        self.schedule_daily_update()

    # ---------------- Schedule Thread ----------------
    def schedule_daily_update(self):
        """تحديث يومي محدد الساعة إذا ON"""
        def daily_scheduler():
            while True:
                hour, state = read_schedule_config()
                if state:
                    now = time.localtime()
                    if now.tm_hour == hour and now.tm_min == 0:
                        update_from_internet(session=self)
                        time.sleep(60)
                time.sleep(30)
        threading.Thread(target=daily_scheduler, daemon=True).start()

    # ---------------- OK Action ----------------
    def ok(self):
        i = self["menu"].getSelectionIndex()
        current_list = self["menu"].getList()
        item = current_list[i][0]

        if item == "View Keys Count":
            self.view()
        elif item == "Add BISS from Channel":
            self.addBISSFromChannel()
        elif item == "Restart Softcam":
            restartSoftcam()
            self["status"].setText("SoftCam تم إعادة تشغيله")
        elif item == "Update & Schedule Options":
            self.open_update_menu()
        elif item == "Update Keys from Internet":
            self["status"].setText("جاري التحديث من الإنترنت...")
            update_from_internet(session=self)
        elif item == "Set Update Interval (hours)":
            self.session.openWithCallback(self.set_interval_callback,
                                          MessageBox,
                                          "أدخل عدد ساعات التحديث:",
                                          MessageBox.TYPE_INPUT)
        elif item == "Schedule Daily Update ON/OFF & Hour":
            self.session.openWithCallback(self.schedule_callback,
                                          MessageBox,
                                          "أدخل الساعة (0-23) وON/OFF مفصولة بمسافة، مثال: 3 ON",
                                          MessageBox.TYPE_INPUT)
        elif item == "Back":
            self["menu"].setList(self.main_menu_items)

    # ---------------- Open Submenu ----------------
    def open_update_menu(self):
        self["menu"].setList(self.update_menu_items)

    # ---------------- Callbacks ----------------
    def set_interval_callback(self, value):
        try:
            hours = int(value)
            set_update_interval(hours)
            self["status"].setText(f"تم ضبط فترة التحديث: {hours} ساعة")
        except:
            self["status"].setText("قيمة غير صحيحة")

    def schedule_callback(self, value):
        try:
            parts = value.split()
            hour = int(parts[0])
            state = parts[1].upper() == "ON"
            write_schedule_config(hour, state)
            self["status"].setText(f"جدولة يومية: الساعة {hour}:00 {'ON' if state else 'OFF'}")
        except:
            self["status"].setText("خطأ في إدخال البيانات")

    # ---------------- Main Functions ----------------
    def view(self):
        with open(BISS_FILE) as f:
            biss = [l for l in f if l.startswith("BISS")]
        self["status"].setText(f"Total Keys: {len(biss)}")

    def addBISSFromChannel(self):
        try:
            from enigma import iServiceInformation
            s = self.session.nav.getCurrentService()
            if not s:
                return
            info = s.info()
            sid = info.getInfo(iServiceInformation.sSID)
            tsid = info.getInfo(iServiceInformation.sTSID)
            onid = info.getInfo(iServiceInformation.sONID)
            key = info.getInfo(iServiceInformation.sCrypt)
            if not key or len(key) != 16:
                key = "1234567890ABCDEF"
        except:
            return

        line = "BISS %04X:%04X:%04X:%s" % (sid, tsid, onid, key)
        backup()
        with open(BISS_FILE, "a") as f:
            f.write("\n" + line)
        self.cleanup()
        restartSoftcam()
        self["status"].setText("BISS Key أضيف وتم إعادة تشغيل SoftCam")

    def cleanup(self):
        with open(BISS_FILE) as f:
            lines = clean(f.readlines())
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)

# ---------------- ENTRY ----------------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Pro Smart Auto Add + Daily Scheduled Update (v1.0)",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )]
