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

# ================== Version Info ==================
PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.1"
PLUGIN_BUILD = "2026-01-27"
PLUGIN_CHANGELOG = [
    "- Added full Settings Menu",
    "- Added Smart/Full restart options",
    "- Added cache control",
    "- Added backup management",
    "- Added auto-add advanced options",
    "- Added language & UI settings",
]

# ================== 1. الإعدادات والمسارات ==================
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"

UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

TMP_BISS = "/tmp/biss.txt"
BISS_CACHE_TIME = 10 * 60  # تحديث الكاش كل 10 دقائق

# ================== 1.5 Config Settings ==================
from Components.config import (
    config, ConfigSubsection,
    ConfigYesNo, ConfigSelection, ConfigInteger
)

config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.restart_mode = ConfigSelection(default="smart", choices=[
    ("smart", "Smart Restart (Active CAM only)"),
    ("full", "Full Restart (All CAMs)")
])
config.plugins.bisspro.match_sid = ConfigYesNo(default=True)
config.plugins.bisspro.match_name = ConfigYesNo(default=True)
config.plugins.bisspro.ignore_hd = ConfigYesNo(default=True)
config.plugins.bisspro.normalize_name = ConfigYesNo(default=True)
config.plugins.bisspro.cache_time = ConfigSelection(default="10", choices=[
    ("0", "Disable Cache"),
    ("5", "5 Minutes"),
    ("10", "10 Minutes"),
    ("30", "30 Minutes"),
    ("60", "60 Minutes"),
])
config.plugins.bisspro.backup_enable = ConfigYesNo(default=True)
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1, 50))
config.plugins.bisspro.confirm_delete = ConfigYesNo(default=True)
config.plugins.bisspro.language = ConfigSelection(default="en", choices=[
    ("en", "English"),
    ("ar", "Arabic")
])
config.plugins.bisspro.debug = ConfigYesNo(default=False)
config.plugins.bisspro.dry_run = ConfigYesNo(default=False)

# ================== 2. Import Lang ==================
from .lang import _

def L(key):
    return _(key, config.plugins.bisspro.language.value)

# ================== 3. دوال معالجة الملفات والكام ==================

def get_key_path():
    """تحديد مسار ملف SoftCam.Key المعتمد في الجهاز"""
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def create_backup():
    """إنشاء نسخة احتياطية قبل التعديل"""
    if not config.plugins.bisspro.backup_enable.value:
        return None

    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        cleanup_backups()
        return b
    return None

def cleanup_backups():
    keep = config.plugins.bisspro.backup_keep.value
    base = os.path.dirname(BISS_FILE)
    name = os.path.basename(BISS_FILE)
    backups = sorted([f for f in os.listdir(base) if f.startswith(name + ".bak_")])
    while len(backups) > keep:
        old = backups.pop(0)
        try:
            os.remove(os.path.join(base, old))
        except:
            pass

def restartSoftcam():
    """
    إعادة تشغيل السوفتكام حسب الإعدادات
    Smart = إعادة تشغيل الكام النشط فقط
    Full = إعادة تشغيل كل الكامات
    """
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]

    if config.plugins.bisspro.restart_mode.value == "smart":
        active = None
        for c in cams:
            if os.system("pidof %s >/dev/null 2>&1" % c) == 0:
                active = c
                break
        if not active:
            active = "oscam"
        os.system("killall %s 2>/dev/null" % active)
        time.sleep(1)
        path = "/usr/bin/" + active
        os.system("%s -b >/dev/null 2>&1 &" % (path if os.path.exists(path) else active))
    else:
        for c in cams:
            os.system("killall %s 2>/dev/null" % c)
        time.sleep(2)
        cam_to_run = "oscam"
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
    cache_time = int(config.plugins.bisspro.cache_time.value)
    if cache_time > 0 and os.path.exists(TMP_BISS):
        if time.time() - os.path.getmtime(TMP_BISS) < cache_time * 60:
            with open(TMP_BISS, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().upper()
    try:
        data = urlopen(BISS_TXT_URL, timeout=10).read()
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        data = data.upper()
        with open(TMP_BISS, "w", encoding="utf-8") as f:
            f.write(data)
        return data
    except:
        return None

# ================== 4. دالة البحث التلقائي ==================

def import_biss_from_github(service):
    try:
        info = service.info()
        sid_int = info.getInfo(iServiceInformation.sSID)
        if sid_int is None:
            return False, "SID not found"

        sid_hex = "%08X" % sid_int
        cur_name = info.getName()
        if config.plugins.bisspro.normalize_name.value:
            cur_name_norm = normalize(cur_name)
        else:
            cur_name_norm = cur_name.upper()

        transponder = info.getInfoObject(iServiceInformation.sTransponderData)
        if not transponder:
            return False, "No transponder info"

        freq = str(transponder.get("frequency", ""))[:5]
        data = get_biss_data()
        if not data:
            return False, "GitHub Connection Error"

        lines = [l.strip() for l in data.splitlines() if l.strip()]
        blocks, i = [], 0

        while i < len(lines):
            if "E" in lines[i] and len(lines[i]) <= 5:
                if i + 3 < len(lines):
                    blocks.append(lines[i:i + 4])
                i += 4
            else:
                i += 1

        found = None
        for b in blocks:
            b_name = b[1]
            if config.plugins.bisspro.normalize_name.value:
                b_name = normalize(b_name)
            else:
                b_name = b_name.upper()

            parts = b[2].split()
            b_freq = parts[0] if parts else ""

            if config.plugins.bisspro.ignore_hd.value:
                b_name = b_name.replace("HD", "").replace("FHD", "").replace("4K", "")
                cur_name_norm = cur_name_norm.replace("HD", "").replace("FHD", "").replace("4K", "")

            match_sid = config.plugins.bisspro.match_sid.value and (sid_hex in b[3].replace(" ", ""))
            match_name = config.plugins.bisspro.match_name.value and (b_freq == freq and b_name == cur_name_norm)

            if match_sid or match_name:
                found = clean_biss_key(b[3])
                break

        if not found:
            return False, "No Key found in Database"

        new_line = "F %s 00000000 %s ;%s" % (sid_hex, found, cur_name_norm)

        if os.path.exists(BISS_FILE):
            with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                if any(l.strip() == new_line.strip() for l in f):
                    return False, L("KEY_EXISTS")

        if config.plugins.bisspro.dry_run.value:
            return True, "Dry Run: Key Found (Not Written)"

        create_backup()
        with open(BISS_FILE, "a", encoding="utf-8") as f:
            f.write(new_line + "\n")

        restartSoftcam()
        return True, L("SUCCESS_ADD")
    except Exception as e:
        if config.plugins.bisspro.debug.value:
            return False, "Error: %s" % str(e)
        return False, L("ERROR")

# ================== 5. واجهات المستخدم ==================

class SelectKeyScreen(Screen):
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
                    if len(p) >= 4 and p[0].upper() == "F" and p[1].upper() == self.sid.upper():
                        items.append((l.strip(), l.strip()))
        if not items:
            self.session.open(MessageBox, L("NO_KEYS_FOR_SID"), MessageBox.TYPE_INFO, 3)
            self.close()
            return
        self["list"].setList(items)

    def ok(self):
        sel = self["list"].getCurrent()
        self.close(sel[0] if sel else None)

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
            if len(p) >= 4 and len(p[3]) == 16:
                self.key = list(p[3])
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
                if self.mode == "edit" and self.key_line and l.strip() == self.key_line.strip():
                    continue
                if l.strip():
                    f.write(l + "\n")
            f.write(new_line + "\n")
        if not config.plugins.bisspro.dry_run.value:
            restartSoftcam()
        self.session.openWithCallback(lambda _: self.close(), MessageBox, L("KEY_SAVED"), MessageBox.TYPE_INFO, 3)

# ================== About Screen ==================

class AboutScreen(Screen):
    skin = """<screen position="center,center" size="720,420" title="About BissPro">
                <widget name="text" position="20,20" size="680,380" font="Regular;22" />
              </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["text"] = Label(self.build_text())
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -1)

    def build_text(self):
        txt = "BissPro Manager\n"
        txt += "Version: %s\n" % PLUGIN_VERSION
        txt += "Build: %s\n\n" % PLUGIN_BUILD
        txt += "Changelog:\n"
        for line in PLUGIN_CHANGELOG:
            txt += "%s\n" % line
        return txt

# ================== Settings Screen ==================

class SettingsScreen(Screen):
    skin = """<screen position="center,center" size="720,520" title="BissPro Settings">
                <widget name="list" position="20,20" size="680,430" scrollbarMode="showOnDemand"/>
                <widget name="version" position="20,460" size="680,40" font="Regular;22" halign="center"/>
              </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([])
        self["version"] = Label("Version: %s   Build: %s" % (PLUGIN_VERSION, PLUGIN_BUILD))
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.ok, "cancel": self.close}, -1)
        self.load()

    def load(self):
        items = [
            ("%s: %s" % (L("RESTART_MODE"), config.plugins.bisspro.restart_mode.value), "restart_mode"),
            ("%s: %s" % (L("MATCH_SID"), "On" if config.plugins.bisspro.match_sid.value else "Off"), "match_sid"),
            ("%s: %s" % (L("MATCH_NAME"), "On" if config.plugins.bisspro.match_name.value else "Off"), "match_name"),
            ("%s: %s" % (L("IGNORE_HD"), "On" if config.plugins.bisspro.ignore_hd.value else "Off"), "ignore_hd"),
            ("%s: %s" % (L("NORMALIZE_NAME"), "On" if config.plugins.bisspro.normalize_name.value else "Off"), "normalize_name"),
            ("%s: %s" % (L("CACHE_TIME"), config.plugins.bisspro.cache_time.value + " min"), "cache_time"),
            ("%s: %s" % (L("BACKUP_ENABLE"), "On" if config.plugins.bisspro.backup_enable.value else "Off"), "backup_enable"),
            ("%s: %s" % (L("BACKUP_KEEP"), str(config.plugins.bisspro.backup_keep.value)), "backup_keep"),
            ("%s: %s" % (L("CONFIRM_DELETE_OPT"), "On" if config.plugins.bisspro.confirm_delete.value else "Off"), "confirm_delete"),
            ("%s: %s" % (L("LANGUAGE"), config.plugins.bisspro.language.value), "language"),
            ("%s: %s" % (L("DEBUG"), "On" if config.plugins.bisspro.debug.value else "Off"), "debug"),
            ("%s: %s" % (L("DRY_RUN"), "On" if config.plugins.bisspro.dry_run.value else "Off"), "dry_run"),
            (L("ABOUT"), "about"),
        ]
        self["list"].setList(items)

    def ok(self):
        sel = self["list"].getCurrent()
        if not sel:
            return
        key = sel[0][1]

        if key == "about":
            self.session.open(AboutScreen)
            return

        if key == "restart_mode":
            config.plugins.bisspro.restart_mode.value = "full" if config.plugins.bisspro.restart_mode.value == "smart" else "smart"
        elif key == "match_sid":
            config.plugins.bisspro.match_sid.value = not config.plugins.bisspro.match_sid.value
        elif key == "match_name":
            config.plugins.bisspro.match_name.value = not config.plugins.bisspro.match_name.value
        elif key == "ignore_hd":
            config.plugins.bisspro.ignore_hd.value = not config.plugins.bisspro.ignore_hd.value
        elif key == "normalize_name":
            config.plugins.bisspro.normalize_name.value = not config.plugins.bisspro.normalize_name.value
        elif key == "cache_time":
            order = ["0", "5", "10", "30", "60"]
            idx = order.index(config.plugins.bisspro.cache_time.value)
            config.plugins.bisspro.cache_time.value = order[(idx + 1) % len(order)]
        elif key == "backup_enable":
            config.plugins.bisspro.backup_enable.value = not config.plugins.bisspro.backup_enable.value
        elif key == "backup_keep":
            config.plugins.bisspro.backup_keep.value = min(50, config.plugins.bisspro.backup_keep.value + 1)
        elif key == "confirm_delete":
            config.plugins.bisspro.confirm_delete.value = not config.plugins.bisspro.confirm_delete.value
        elif key == "language":
            config.plugins.bisspro.language.value = "ar" if config.plugins.bisspro.language.value == "en" else "en"
            self.session.open(MessageBox, L("RESTART_GUI"), MessageBox.TYPE_INFO, 3)
        elif key == "debug":
            config.plugins.bisspro.debug.value = not config.plugins.bisspro.debug.value
        elif key == "dry_run":
            config.plugins.bisspro.dry_run.value = not config.plugins.bisspro.dry_run.value

        self.load()

class BISSPro(Screen):
    skin = """<screen position="center,center" size="1024,768" title="BissPro Manager">
                <widget name="menu" position="40,100" size="940,540" itemHeight="150" scrollbarMode="showOnDemand"/>
                <widget name="status" position="40,650" size="940,50" font="Regular;28" halign="center" valign="center" foregroundColor="#00ff00"/>
              </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [
            (L("ADD_KEY"), "add", "add.png"),
            (L("EDIT_KEY"), "edit", "edit.png"),
            (L("DELETE_KEY"), "delete", "delete.png"),
            (L("UPDATE_SOFTCAM"), "update", "update.png"),
            (L("AUTO_ADD"), "auto_add", "auto_add.png"),
            (L("SETTINGS"), "settings", "settings.png"),
        ]
        self.menu_list = [
            (
                a,
                [
                    MultiContentEntryPixmapAlphaTest(pos=(10, 10), size=(128, 128), png=LoadPixmap(ICON_PATH + i)),
                    MultiContentEntryText(pos=(160, 50), size=(760, 60), font=0, text=t)
                ]
            )
            for t, a, i in self.menu_items
        ]
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", 32))
        self["status"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {"ok": self.ok, "cancel": self.close, "up": self["menu"].up, "down": self["menu"].down}, -1)

    def ok(self):
        sel = self["menu"].getCurrent()
        service = self.session.nav.getCurrentService()
        if not sel or not service:
            return
        action, info = sel[0], service.info()
        sid, sname = "%08X" % info.getInfo(iServiceInformation.sSID), info.getName().replace(' ', '_')

        if action == "add":
            self.session.open(EasyBissInput, sid, "add", None, sname)
        elif action in ("edit", "delete"):
            self.session.openWithCallback(lambda l: self.handle(action, sid, l, sname), SelectKeyScreen, sid, lambda x: x)
        elif action == "update":
            self.start_bg(lambda: self.bg_update(BISS_FILE), L("UPDATING"))
        elif action == "auto_add":
            self.start_bg(lambda: self.bg_auto(service), L("SEARCHING"))
        elif action == "settings":
            self.session.open(SettingsScreen)

    def start_bg(self, target, msg):
        self["status"].setText(msg)
        Thread(target=target).start()

    def bg_update(self, dest):
        try:
            create_backup()
            urlretrieve(UPDATE_URL, "/tmp/sc.tmp")
            if os.path.exists("/tmp/sc.tmp"):
                shutil.copy("/tmp/sc.tmp", dest)
            if not config.plugins.bisspro.dry_run.value:
                restartSoftcam()
            self.done(True, L("SOFTCAM_UPDATED"))
        except:
            self.done(False, L("DOWNLOAD_FAILED"))

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
        if not line:
            return
        if action == "edit":
            self.session.open(EasyBissInput, sid, "edit", line, sname)
        else:
            if config.plugins.bisspro.confirm_delete.value:
                self.session.openWithCallback(lambda c: self.del_k(c, line), MessageBox, L("CONFIRM_DELETE"), MessageBox.TYPE_YESNO)
            else:
                self.del_k(True, line)

    def del_k(self, conf, line):
        if not conf:
            return
        create_backup()
        lines = []
        with open(BISS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        with open(BISS_FILE, "w", encoding="utf-8", errors="ignore") as f:
            done = False
            for l in lines:
                if not done and l.strip() == line.strip():
                    done = True
                    continue
                f.write(l)
        if not config.plugins.bisspro.dry_run.value:
            restartSoftcam()
        self.session.open(MessageBox, L("KEY_DELETED"), MessageBox.TYPE_INFO, 3)

# ================== تشغيل البلجن ==================

def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME, description="Pro BISS Keys Manager", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="plugin.png")]
