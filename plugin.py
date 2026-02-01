# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigInteger
from Components.ConfigList import ConfigListScreen
from enigma import iServiceInformation, gFont, eTimer, getDesktop
from Tools.LoadPixmap import LoadPixmap

from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve
import os, time, shutil, re, logging
from datetime import datetime

# ================== Plugin Info ==================
PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.2"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"
UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"
TMP_BISS = "/tmp/biss.txt"

logger = logging.getLogger("BissPro")
logger.setLevel(logging.DEBUG)
lock = Lock()

# ================== Auto Scale ==================
class AutoScale:
    BASE_W = 1920.0
    BASE_H = 1080.0
    def __init__(self):
        d = getDesktop(0).size()
        self.w = d.width()
        self.h = d.height()
        self.scale = min(self.w / self.BASE_W, self.h / self.BASE_H)
        self.scale = min(self.scale, 1.3)
    def px(self, v):
        return int(v * self.scale)
    def font(self, v):
        return int(max(18, v * self.scale))

# ================== Config ==================
config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.restart_mode = ConfigSelection(default="smart", choices=[("smart","Smart Restart"),("full","Full Restart")])
config.plugins.bisspro.match_sid = ConfigYesNo(default=True)
config.plugins.bisspro.match_name = ConfigYesNo(default=True)
config.plugins.bisspro.ignore_hd = ConfigYesNo(default=True)
config.plugins.bisspro.normalize_name = ConfigYesNo(default=True)
config.plugins.bisspro.cache_time = ConfigSelection(default="10", choices=[("0","Disable"),("5","5 Min"),("10","10 Min"),("30","30 Min")])
config.plugins.bisspro.backup_enable = ConfigYesNo(default=True)
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1,50))
config.plugins.bisspro.confirm_delete = ConfigYesNo(default=True)
config.plugins.bisspro.dry_run = ConfigYesNo(default=False)
config.plugins.bisspro.debug = ConfigYesNo(default=False)
config.plugins.bisspro.language = ConfigSelection(default="en", choices=[("en","English"),("ar","Arabic")])

# ================== Utils ==================
def get_key_path():
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/usr/keys/softcam.key",
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
    if config.plugins.bisspro.restart_mode.value=="smart":
        for c in cams:
            if os.system(f"pidof {c} >/dev/null")==0:
                os.system(f"killall {c}")
                time.sleep(1)
                os.system(f"{c} -b &")
                return
    for c in cams:
        os.system(f"killall {c} 2>/dev/null")
    time.sleep(2)
    os.system("oscam -b &")

def clean_key(key):
    return re.sub(r'[^0-9A-F]', '', key.upper())

def normalize(text):
    return ''.join(c for c in text.upper() if c.isalnum())

def get_biss_data(retries=2):
    cache_time = int(config.plugins.bisspro.cache_time.value)
    if cache_time>0 and os.path.exists(TMP_BISS):
        if time.time()-os.path.getmtime(TMP_BISS) < cache_time*60:
            with open(TMP_BISS,"r",encoding="utf-8",errors="ignore") as f:
                return f.read()
    for attempt in range(retries):
        try:
            raw = urlopen(BISS_TXT_URL,timeout=10).read()
            data = raw.decode("utf-8","replace").upper()
            with open(TMP_BISS,"w",encoding="utf-8") as f:
                f.write(data)
            return data
        except Exception as e:
            if config.plugins.bisspro.debug.value:
                logger.debug(f"Attempt {attempt+1} failed: {e}")
            time.sleep(1)
    return None

def import_biss(service):
    try:
        info = service.info()
        sid = "%08X"%info.getInfo(iServiceInformation.sSID)
        name = normalize(info.getName())
        data = get_biss_data()
        if not data: return False,"Download failed"
        for line in data.splitlines():
            parts = line.strip().split()
            if len(parts)>=4 and sid==parts[1]:
                key_raw = parts[3]
                key = clean_key(key_raw)
                if len(key)==16:
                    create_backup()
                    with lock:
                        with open(BISS_FILE,"a",encoding="utf-8") as f:
                            f.write(f"F {sid} 00000000 {key} ;{name}\n")
                    if not config.plugins.bisspro.dry_run.value:
                        restartSoftcam()
                    return True,"Key added successfully"
        return False,"No key found"
    except Exception as e:
        return False,str(e)

# ================== Main Screen ==================
class BISSPro(Screen):
    def __init__(self,session):
        self.ui = AutoScale()
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1920)},{self.ui.px(1080)}" title="BissPro Manager">
            <widget name="menu" position="{self.ui.px(40)},{self.ui.px(100)}" size="{self.ui.px(1840)},{self.ui.px(760)}" itemHeight="{self.ui.px(150)}"/>
            <widget name="status" position="{self.ui.px(40)},{self.ui.px(900)}" size="{self.ui.px(1840)},{self.ui.px(60)}" font="Regular;{self.ui.font(32)}" halign="center"/>
        </screen>
        """
        Screen.__init__(self,session)

        self.menu_items=[
            ("Auto Add BISS","auto_add","add.png"),
            ("Update SoftCam","update","update.png"),
            ("Settings","settings","settings.png")
        ]

        self.menu_list=[(a,[
            MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10),self.ui.px(10)),size=(self.ui.px(128),self.ui.px(128)),png=LoadPixmap(ICON_PATH+i)),
            MultiContentEntryText(pos=(self.ui.px(160),self.ui.px(50)),size=(self.ui.px(760),self.ui.px(60)),font=0,text=t)
        ]) for t,a,i in self.menu_items]

        self["menu"]=MenuList(self.menu_list)
        self["menu"].l.setFont(0,gFont("Regular",self.ui.font(32)))
        self["status"]=Label("")
        self["actions"]=ActionMap(["OkCancelActions","DirectionActions"],{"ok":self.ok,"cancel":self.close,"up":self["menu"].up,"down":self["menu"].down},-1)
        self.timer=eTimer()
        self.timer.callback.append(self.show_result)

    def ok(self):
        sel=self["menu"].getCurrent()
        if not sel: return
        action=sel[0]
        service=self.session.nav.getCurrentService()
        if action=="auto_add" and service:
            Thread(target=self.bg_auto,args=(service,)).start()
        elif action=="update":
            Thread(target=self.bg_update).start()
        elif action=="settings":
            self.session.open(BissProSettings)

    def bg_auto(self,service):
        ok,msg=import_biss(service)
        self.result=(ok,msg)
        self.timer.start(100,True)

    def bg_update(self):
        try:
            create_backup()
            urlretrieve(UPDATE_URL,"/tmp/SoftCam.Key")
            with lock:
                shutil.copy("/tmp/SoftCam.Key",BISS_FILE)
            restartSoftcam()
            self.result=(True,"SoftCam updated")
        except Exception as e:
            self.result=(False,f"Update failed: {e}")
        self.timer.start(100,True)

    def show_result(self):
        self.session.open(MessageBox,self.result[1],MessageBox.TYPE_INFO if self.result[0] else MessageBox.TYPE_ERROR,3)

# ================== Settings Screen ==================
class BissProSettings(Screen, ConfigListScreen):
    def __init__(self, session):
        self.ui = AutoScale()
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(1024)},{self.ui.px(768)}" title="BissPro Settings">
            <widget name="config" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(984)},{self.ui.px(600)}" scrollbarMode="showOnDemand"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(630)}" size="{self.ui.px(984)},{self.ui.px(60)}" font="Regular;{self.ui.font(28)}" halign="center"/>
        </screen>
        """
        Screen.__init__(self, session)

        self.list = [
            config.plugins.bisspro.restart_mode,
            config.plugins.bisspro.match_sid,
            config.plugins.bisspro.match_name,
            config.plugins.bisspro.ignore_hd,
            config.plugins.bisspro.normalize_name,
            config.plugins.bisspro.cache_time,
            config.plugins.bisspro.backup_enable,
            config.plugins.bisspro.backup_keep,
            config.plugins.bisspro.confirm_delete,
            config.plugins.bisspro.dry_run,
            config.plugins.bisspro.debug,
            config.plugins.bisspro.language
        ]
        ConfigListScreen.__init__(self, self.list, session=session, on_change=self.on_changed)

        self["status"] = Label("")
        self["actions"] = ActionMap(
            ["OkCancelActions","ColorActions","DirectionActions"],
            {
                "ok": self.save_settings,
                "cancel": self.close,
                "red": self.reset_defaults,
                "up": self["config"].up,
                "down": self["config"].down
            },
            -1
        )

    def on_changed(self):
        self["status"].setText("Settings changed, press OK to save")

    def save_settings(self):
        for entry in self.list:
            entry.save()
        self["status"].setText("Settings saved!")
        self.close()

    def reset_defaults(self):
        for entry in self.list:
            entry.setValue(entry.default)
        self["status"].setText("Defaults restored")

# ================== Plugin Entry ==================
def main(session,**kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(name=PLUGIN_NAME,description="BissPro Auto-Scale Manager",where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main)]
