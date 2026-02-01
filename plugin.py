# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from Components.config import (
    config, ConfigSubsection,
    ConfigYesNo, ConfigSelection, ConfigInteger
)
from enigma import iServiceInformation, gFont, eTimer
from Tools.LoadPixmap import LoadPixmap

from threading import Thread
from urllib.request import urlopen, urlretrieve

import os, time, shutil, re
from datetime import datetime

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

# ================== Paths ==================
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"

UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

TMP_BISS = "/tmp/biss.txt"

# ================== Config ==================
config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.restart_mode = ConfigSelection(
    default="smart",
    choices=[("smart", "Smart Restart (Active CAM only)"),
             ("full", "Full Restart (All CAMs)")]
)
config.plugins.bisspro.match_sid = ConfigYesNo(default=True)
config.plugins.bisspro.match_name = ConfigYesNo(default=True)
config.plugins.bisspro.ignore_hd = ConfigYesNo(default=True)
config.plugins.bisspro.normalize_name = ConfigYesNo(default=True)
config.plugins.bisspro.cache_time = ConfigSelection(
    default="10",
    choices=[("0", "Disable Cache"),
             ("5", "5 Minutes"),
             ("10", "10 Minutes"),
             ("30", "30 Minutes"),
             ("60", "60 Minutes")]
)
config.plugins.bisspro.backup_enable = ConfigYesNo(default=True)
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1, 50))
config.plugins.bisspro.confirm_delete = ConfigYesNo(default=True)
config.plugins.bisspro.language = ConfigSelection(
    default="en",
    choices=[("en", "English"), ("ar", "Arabic")]
)
config.plugins.bisspro.debug = ConfigYesNo(default=False)
config.plugins.bisspro.dry_run = ConfigYesNo(default=False)

# ================== Lang ==================
from .lang import _

def L(key):
    return _(key, config.plugins.bisspro.language.value)

# ================== Utils ==================
def get_key_path():
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
    if not config.plugins.bisspro.backup_enable.value:
        return
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        cleanup_backups()

def cleanup_backups():
    keep = config.plugins.bisspro.backup_keep.value
    base = os.path.dirname(BISS_FILE)
    name = os.path.basename(BISS_FILE)
    backups = sorted(f for f in os.listdir(base) if f.startswith(name + ".bak_"))
    while len(backups) > keep:
        os.remove(os.path.join(base, backups.pop(0)))

def restartSoftcam():
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]
    if config.plugins.bisspro.restart_mode.value == "smart":
        active = next((c for c in cams if os.system(f"pidof {c} >/dev/null") == 0), "oscam")
        os.system(f"killall {active} 2>/dev/null")
        time.sleep(1)
        os.system(f"{active} -b &")
    else:
        for c in cams:
            os.system(f"killall {c} 2>/dev/null")
        time.sleep(2)
        os.system("oscam -b &")

def clean_biss_key(key):
    return re.sub(r'[^0-9A-F]', '', key.upper())

def normalize(text):
    return ''.join(c for c in text.upper() if c.isalnum())

def get_biss_data():
    cache_time = int(config.plugins.bisspro.cache_time.value)
    if cache_time > 0 and os.path.exists(TMP_BISS):
        if time.time() - os.path.getmtime(TMP_BISS) < cache_time * 60:
            return open(TMP_BISS, encoding="utf-8", errors="ignore").read()
    try:
        data = urlopen(BISS_TXT_URL, timeout=10).read().decode("utf-8", "ignore").upper()
        open(TMP_BISS, "w", encoding="utf-8").write(data)
        return data
    except:
        return None

# ================== Auto Add ==================
def import_biss_from_github(service):
    try:
        info = service.info()
        sid = "%08X" % info.getInfo(iServiceInformation.sSID)
        name = normalize(info.getName())

        data = get_biss_data()
        if not data:
            return False, L("ERROR")

        for line in data.splitlines():
            if sid in line:
                key = clean_biss_key(line)
                if len(key) == 16:
                    create_backup()
                    with open(BISS_FILE, "a", encoding="utf-8") as f:
                        f.write(f"F {sid} 00000000 {key} ;{name}\n")
                    if not config.plugins.bisspro.dry_run.value:
                        restartSoftcam()
                    return True, L("SUCCESS_ADD")
        return False, L("NO_KEY")
    except Exception as e:
        return False, str(e)

# ================== Main Screen ==================
class BISSPro(Screen):
    skin = """<screen position="center,center" size="1024,768" title="BissPro Manager">
        <widget name="menu" position="40,100" size="940,540" itemHeight="150"/>
        <widget name="status" position="40,650" size="940,50" font="Regular;28" halign="center"/>
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
            (a, [
                MultiContentEntryPixmapAlphaTest(
                    pos=(10, 10), size=(128, 128),
                    png=LoadPixmap(ICON_PATH + i)
                ),
                MultiContentEntryText(
                    pos=(160, 50), size=(760, 60),
                    font=0, text=t
                )
            ])
            for t, a, i in self.menu_items
        ]

        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", 32))
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

        self._timer = eTimer()
        self._timer.callback.append(self.show_res)

    def start_bg(self, target, msg):
        self["status"].setText(msg)
        Thread(target=target).start()

    def done(self, ok, msg):
        self.res = (ok, msg)
        self._timer.start(100, True)

    def show_res(self):
        self["status"].setText("")
        self.session.open(
            MessageBox,
            self.res[1],
            MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR,
            3
        )

    def ok(self):
        sel = self["menu"].getCurrent()
        if not sel:
            return
        service = self.session.nav.getCurrentService()
        action = sel[0]

        if action == "auto_add" and service:
            self.start_bg(lambda: self.done(*import_biss_from_github(service)), L("SEARCHING"))
        elif action == "update":
            self.start_bg(self.bg_update, L("UPDATING"))

    def bg_update(self):
        try:
            create_backup()
            urlretrieve(UPDATE_URL, "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            if not config.plugins.bisspro.dry_run.value:
                restartSoftcam()
            self.done(True, L("SOFTCAM_UPDATED"))
        except:
            self.done(False, L("DOWNLOAD_FAILED"))

# ================== Plugin ==================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="Pro BISS Keys Manager (Py3)",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main,
            icon="plugin.png"
        )
    ]
