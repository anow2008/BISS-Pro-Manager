# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from enigma import iServiceInformation, eTimer
from threading import Thread
import os, time, shutil, re
from datetime import datetime

# ================= NETWORK =================
try:
    from urllib.request import urlopen, urlretrieve
except:
    from urllib2 import urlopen
    from urllib import urlretrieve

# ================= INFO =================
PLUGIN_NAME = "BissPro"
PLUGIN_VERSION = "1.2-py3"
PLUGIN_BUILD = "2026-01-27"

# ================= PATHS =================
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"
TMP_BISS = "/tmp/biss.txt"

UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/biss.txt"

# ================= CONFIG =================
from Components.config import (
    config, ConfigSubsection,
    ConfigYesNo, ConfigSelection, ConfigInteger
)

config.plugins.bisspro = ConfigSubsection()
config.plugins.bisspro.restart_mode = ConfigSelection(default="smart", choices=[("smart","Smart"),("full","Full")])
config.plugins.bisspro.match_sid = ConfigYesNo(default=True)
config.plugins.bisspro.match_name = ConfigYesNo(default=True)
config.plugins.bisspro.ignore_hd = ConfigYesNo(default=True)
config.plugins.bisspro.normalize_name = ConfigYesNo(default=True)
config.plugins.bisspro.cache_time = ConfigSelection(default="10", choices=[("0","Off"),("5","5"),("10","10"),("30","30"),("60","60")])
config.plugins.bisspro.backup_enable = ConfigYesNo(default=True)
config.plugins.bisspro.backup_keep = ConfigInteger(default=5, limits=(1,50))
config.plugins.bisspro.confirm_delete = ConfigYesNo(default=True)

# ================= HELPERS =================
def get_key_path():
    for p in (
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key",
        "/var/keys/SoftCam.Key"
    ):
        if os.path.exists(p):
            return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def normalize(t):
    return "".join(c for c in t.upper() if c.isalnum())

def clean_key(k):
    return re.sub(r"[^0-9A-F]", "", k.upper())

def create_backup():
    if not config.plugins.bisspro.backup_enable.value:
        return
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        cleanup_backups()

def cleanup_backups():
    base = os.path.dirname(BISS_FILE)
    name = os.path.basename(BISS_FILE)
    keep = config.plugins.bisspro.backup_keep.value
    lst = sorted([f for f in os.listdir(base) if f.startswith(name + ".bak_")])
    while len(lst) > keep:
        os.remove(os.path.join(base, lst.pop(0)))

def restartSoftcam():
    cams = ("oscam","ncam","gcam","revcam","vicard")
    if config.plugins.bisspro.restart_mode.value == "smart":
        for c in cams:
            if os.system("pidof %s >/dev/null 2>&1" % c) == 0:
                os.system("killall %s 2>/dev/null" % c)
                time.sleep(1)
                os.system("%s -b &" % c)
                return
        os.system("oscam -b &")
    else:
        for c in cams:
            os.system("killall %s 2>/dev/null" % c)
        time.sleep(2)
        os.system("oscam -b &")

def get_biss_data():
    try:
        cache = int(config.plugins.bisspro.cache_time.value)
        if cache > 0 and os.path.exists(TMP_BISS):
            if time.time() - os.path.getmtime(TMP_BISS) < cache * 60:
                return open(TMP_BISS, "r", errors="ignore").read().upper()
        data = urlopen(BISS_TXT_URL, timeout=10).read().decode("utf-8","ignore").upper()
        open(TMP_BISS, "w").write(data)
        return data
    except:
        return None

# ================= MANUAL INPUT =================
class EasyBissInput(Screen):
    skin = """
    <screen position="center,center" size="820,300" title="Manual BISS Entry">
        <widget name="key" position="110,80" size="600,80"
            font="Console;48" halign="center" valign="center"/>
        <widget name="hint" position="110,170" size="600,40"
            font="Regular;22" halign="center"/>
    </screen>"""

    def __init__(self, session, sid, sname):
        Screen.__init__(self, session)
        self.sid = sid
        self.sname = sname
        self.pos = 0
        self.key = list("0000000000000000")
        self.hexchars = list("0123456789ABCDEF")

        self["key"] = Label("")
        self["hint"] = Label("0-9 Numbers | ↑↓ A-F | ←→ Move | OK Save")

        self["actions"] = ActionMap(
            ["DirectionActions","NumberActions","OkCancelActions"],
            {"left":self.left,"right":self.right,"up":self.up,
             "down":self.down,"ok":self.save,"cancel":self.close}, -1)

        for i in range(10):
            self["actions"].actions[str(i)] = self.make_num(str(i))

        self.refresh()

    def make_num(self, n):
        return lambda: self.set_num(n)

    def refresh(self):
        txt = ""
        for i,c in enumerate(self.key):
            txt += "[%s]"%c if i==self.pos else " %s "%c
        self["key"].setText(txt)

    def left(self):
        self.pos=(self.pos-1)%16; self.refresh()
    def right(self):
        self.pos=(self.pos+1)%16; self.refresh()
    def up(self):
        i=self.hexchars.index(self.key[self.pos])
        self.key[self.pos]=self.hexchars[(i+1)%16]; self.refresh()
    def down(self):
        i=self.hexchars.index(self.key[self.pos])
        self.key[self.pos]=self.hexchars[(i-1)%16]; self.refresh()
    def set_num(self,n):
        self.key[self.pos]=n; self.right()

    def save(self):
        line="F %s 00000000 %s ;%s"%(self.sid,"".join(self.key),self.sname)
        create_backup()
        open(BISS_FILE,"a").write(line+"\n")
        restartSoftcam()
        self.session.open(MessageBox,"BISS Key Saved",MessageBox.TYPE_INFO,3)
        self.close()

# ================= AUTO ADD =================
def auto_add(service):
    try:
        info = service.info()
        sid = info.getInfo(iServiceInformation.sSID)
        if sid in (-1,None):
            return False,"SID Error"

        sid_hex="%08X"%sid
        name=normalize(info.getName())
        trans=info.getInfoObject(iServiceInformation.sTransponderData)
        freq=str(trans.get("frequency",""))[:5] if trans else ""

        data=get_biss_data()
        if not data:
            return False,"Download Error"

        lines=[l.strip() for l in data.splitlines() if l.strip()]
        for i in range(0,len(lines)-3,4):
            bname=normalize(lines[i+1])
            bf=lines[i+2].split()[0]
            key=clean_key(lines[i+3])
            if sid_hex in lines[i+3] or (bname==name and bf==freq):
                create_backup()
                open(BISS_FILE,"a").write(
                    "F %s 00000000 %s ;%s\n"%(sid_hex,key,name))
                restartSoftcam()
                return True,"Key Added"
        return False,"No Key Found"
    except Exception as e:
        return False,str(e)

# ================= MAIN SCREEN =================
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="900,600" title="BissPro Manager">
        <widget name="menu" position="50,80" size="800,420"/>
        <widget name="status" position="50,520" size="800,40" halign="center"/>
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["menu"] = MenuList([
            ("ADD BISS MANUAL","add"),
            ("AUTO ADD BISS","auto"),
            ("UPDATE SOFTCAM","update"),
        ])
        self["status"] = Label("")
        self["actions"] = ActionMap(
            ["OkCancelActions","DirectionActions"],
            {"ok":self.ok,"cancel":self.close,
             "up":self["menu"].up,"down":self["menu"].down}, -1)

    def ok(self):
        sel=self["menu"].getCurrent()
        if not sel: return
        service=self.session.nav.getCurrentService()
        if sel[1]=="add":
            info=service.info()
            sid="%08X"%info.getInfo(iServiceInformation.sSID)
            name=info.getName().replace(" ","_")
            self.session.open(EasyBissInput,sid,name)
        elif sel[1]=="auto":
            self.run_bg(lambda: auto_add(service),"Searching...")
        elif sel[1]=="update":
            self.run_bg(self.update_sc,"Updating...")

    def run_bg(self, func, msg):
        self["status"].setText(msg)
        self._func=func
        Thread(target=self._worker).start()

    def _worker(self):
        self._res=self._func()
        eTimer.singleShot(0,self.show_res)

    def show_res(self):
        ok,msg=self._res
        self["status"].setText("")
        self.session.open(MessageBox,msg,
            MessageBox.TYPE_INFO if ok else MessageBox.TYPE_ERROR,3)

    def update_sc(self):
        try:
            create_backup()
            urlretrieve(UPDATE_URL,"/tmp/sc.tmp")
            shutil.copy("/tmp/sc.tmp",BISS_FILE)
            restartSoftcam()
            return True,"Softcam Updated"
        except:
            return False,"Update Failed"

# ================= PLUGIN =================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="Professional BISS Manager (Python3)",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )]
