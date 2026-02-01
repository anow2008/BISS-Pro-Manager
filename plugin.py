# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigInteger, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from enigma import iServiceInformation, gFont, eTimer, getDesktop
from Tools.LoadPixmap import LoadPixmap

from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve
import os, time, shutil, re
from datetime import datetime

# ================== Plugin Info ==================
PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.5"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"
TMP_BISS = "/tmp/biss.txt"

# هذا هو السطر المسؤول عن جلب أيقونة البلجن للقائمة الخارجية
PLUGIN_ICON = PLUGIN_PATH + "/plugin.png"

lock = Lock()

# ================== Translations ==================
LANG = {
    "en": {
        "title": "BissPro Manager", "auto": "Auto Add BISS", "update": "Update SoftCam.Key",
        "settings": "Settings", "save": "Press OK to save", "success": "Success", "fail": "Failed",
        "no_key": "No key found"
    },
    "ar": {
        "title": "BissPro مدير الشفرات", "auto": "إضافة شفرة القناة الحالية", "update": "تحديث ملف SoftCam",
        "settings": "الإعدادات", "save": "اضغط OK للحفظ", "success": "تم بنجاح", "fail": "فشل",
        "no_key": "لا توجد شفرة"
    }
}

def _(text):
    l = config.plugins.bisspro.language.value
    return LANG.get(l, LANG["en"]).get(text, text)

# ================== Auto Scale ==================
class AutoScale:
    BASE_W = 1920.0
    BASE_H = 1080.0
    def __init__(self):
        d = getDesktop(0).size()
        self.w = d.width()
        self.h = d.height()
        self.scale = min(self.w / self.BASE_W, self.h / self.BASE_H)
    def px(self, v): return int(v * self.scale)
    def font(self, v): return int(max(18, v * self.scale))

# ================== Config ==================
config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.language = ConfigSelection(default="ar", choices=[("en","English"),("ar","Arabic")])
config.plugins.bisspro.restart_mode = ConfigSelection(default="smart", choices=[("smart","Smart Restart"),("full","Full Restart")])
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1,50))
config.plugins.bisspro.dry_run = ConfigYesNo(default=False)

# ================== Utils ==================
def get_key_path():
    paths = ["/etc/tuxbox/config/oscam/SoftCam.Key", "/etc/tuxbox/config/SoftCam.Key", "/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

# ================== Main Screen ==================
class BISSPro(Screen):
    def __init__(self,session):
        self.ui = AutoScale()
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="{_('title')}">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(600)}" itemHeight="{self.ui.px(120)}"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}" size="{self.ui.px(1060)},{self.ui.px(50)}" font="Regular;{self.ui.font(28)}" halign="center"/>
        </screen>"""
        Screen.__init__(self,session)
        
        self.update_menu()
        self["status"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions","DirectionActions"], {"ok":self.ok,"cancel":self.close,"up":self["menu"].up,"down":self["menu"].down},-1)
        self.timer = eTimer()
        self.timer.callback.append(self.show_result)

    def update_menu(self):
        items = [
            (_("auto"), "add", ICON_PATH + "add.png"),
            (_("update"), "upd", ICON_PATH + "update.png"),
            (_("settings"), "set", ICON_PATH + "settings.png")
        ]
        
        self.menu_list = []
        for t, a, p in items:
            self.menu_list.append((a, [
                MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10), self.ui.px(10)), size=(self.ui.px(100), self.ui.px(100)), png=LoadPixmap(p)),
                MultiContentEntryText(pos=(self.ui.px(130), self.ui.px(30)), size=(self.ui.px(800), self.ui.px(60)), font=0, text=t)
            ]))
            
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    def ok(self):
        action = self["menu"].getCurrent()[0]
        if action == "set": self.session.openWithCallback(self.update_menu, BissProSettings)
        elif action == "add":
            service = self.session.nav.getCurrentService()
            if service: Thread(target=self.do_add, args=(service,)).start()
        elif action == "upd": Thread(target=self.do_upd).start()

    def do_add(self, s):
        try:
            info = s.info()
            sid = "%08X"%info.getInfo(iServiceInformation.sSID)
            raw = urlopen(BISS_TXT_URL,timeout=10).read().decode("utf-8","replace").upper()
            found = False
            for line in raw.splitlines():
                if sid in line:
                    key = re.sub(r'[^0-9A-F]', '', line.split()[-1])
                    if len(key) == 16:
                        with lock:
                            with open(BISS_FILE, "a+") as f:
                                f.write(f"\nF {sid} 00000000 {key} ;{info.getName()}\n")
                        found = True; break
            self.res = (True, _("success")) if found else (False, _("no_key"))
        except: self.res = (False, _("fail"))
        self.timer.start(100,True)

    def do_upd(self):
        try:
            urlretrieve(UPDATE_URL, "/tmp/S.Key")
            shutil.copy("/tmp/S.Key", BISS_FILE)
            self.res = (True, _("success"))
        except: self.res = (False, _("fail"))
        self.timer.start(100,True)

    def show_result(self):
        self.session.open(MessageBox, self.res[1], MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR, 3)

class BissProSettings(Screen, ConfigListScreen):
    def __init__(self, session):
        self.ui = AutoScale()
        self.skin = f"""<screen position="center,center" size="{self.ui.px(800)},{self.ui.px(450)}" title="{_('settings')}">
            <widget name="config" position="10,10" size="780,350"/>
        </screen>"""
        Screen.__init__(self, session)
        self.list = [
            getConfigListEntry("اللغة / Language", config.plugins.bisspro.language),
            getConfigListEntry("Restart Mode", config.plugins.bisspro.restart_mode),
            getConfigListEntry("Backups", config.plugins.bisspro.backup_keep)
        ]
        ConfigListScreen.__init__(self, self.list, session=session)
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.save, "cancel": self.close}, -1)
    def save(self):
        for x in self.list: x[1].save()
        self.close()

# ================== Entry Points ==================
def main(session,**kwargs): 
    session.open(BISSPro)

def Plugins(**kwargs):
    # تم إضافة 'icon' و 'fnc' و 'where' بشكل صحيح ليقرأ النظام أيقونة البلجن
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="BissPro Manager " + PLUGIN_VERSION,
            icon="plugin.png", # اسم ملف الصورة داخل فولدر البلجن
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        )
    ]
