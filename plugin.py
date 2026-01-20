# -*- coding: utf-8 -*-
# Biss Pro v1.0 – Secure Universal Enigma2 Plugin (Python2 / Python3)

from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
import os, shutil, re, time, threading

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

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

GITHUB_MIRRORS = [
    "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key",
    "https://raw.githubusercontent.com/MOHAMED19OS/SoftCam_Emu/refs/heads/main/SoftCam.Key"
]

MAX_BACKUPS = 3
LAST_UPDATE = "/tmp/bisspro_last"
INTERVAL_FILE = "/tmp/bisspro_interval"
FIXED_TIME_FILE = "/tmp/bisspro_fixed"

update_lock = threading.Lock()

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

def safeRead(path, default=0):
    try:
        return int(open(path).read())
    except:
        return default

def validateSoftcam(data):
    out = []
    for l in data.splitlines():
        l = l.strip()
        if l.startswith(("BISS", "P:", "T:")):
            out.append(l + "\n")
    return out

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        ensure()
        self.startAuto()

        self["menu"] = MenuList([
            "View Keys Count",
            "Add BISS from Channel",
            "Update Online",
            "Auto Update Interval",
            "Fixed Time Update",
            "Restart Softcam"
        ])

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            }, -1
        )

    def ok(self):
        i = self["menu"].getSelectionIndex()
        if i == 0: self.view()
        elif i == 1: self.fromService()
        elif i == 2: self.update(True)
        elif i == 3: self.interval()
        elif i == 4: self.fixed()
        elif i == 5: restartSoftcam()

    def view(self):
        with open(BISS_FILE) as f:
            biss = [l for l in f if l.startswith(("BISS", "P:", "T:"))]
        self.session.open(MessageBox,
            "Total Keys: %d" % len(biss),
            MessageBox.TYPE_INFO)

    def fromService(self):
        try:
            from enigma import iServiceInformation
            s = self.session.nav.getCurrentService()
            i = s.info()
            sid = i.getInfo(iServiceInformation.sSID)
            ts = i.getInfo(iServiceInformation.sTSID)
            on = i.getInfo(iServiceInformation.sONID)
        except:
            self.session.open(MessageBox, "No active service", MessageBox.TYPE_ERROR)
            return

        from Screens.InputBox import InputBox
        def cb(k):
            line = "BISS %04X:%04X:%04X:%s" % (sid, ts, on, k)
            backup()
            with open(BISS_FILE, "a") as f:
                f.write("\n" + line)
            restartSoftcam()
            self.session.open(MessageBox, "BISS Added", MessageBox.TYPE_INFO)

        self.session.open(InputBox,
            title="Enter HEX Key",
            text="",
            maxSize=32,
            type=InputBox.TYPE_TEXT,
            callback=cb)

    def update(self, manual=False):
        if not update_lock.acquire(False):
            return
        try:
            for u in GITHUB_MIRRORS:
                try:
                    d = urlopen(u, timeout=10).read()
                    if isinstance(d, bytes):
                        d = d.decode("utf-8", "ignore")
                    valid = validateSoftcam(d)
                    if not valid:
                        continue
                    backup()
                    with open(BISS_FILE, "w") as f:
                        f.writelines(valid)
                    self.cleanup()
                    restartSoftcam()
                    open(LAST_UPDATE, "w").write(str(int(time.time())))
                    if manual:
                        self.session.open(MessageBox, "Online Update Done", MessageBox.TYPE_INFO)
                    return
                except:
                    pass
            if manual:
                self.session.open(MessageBox, "Update Failed", MessageBox.TYPE_ERROR)
        finally:
            update_lock.release()

    def cleanup(self):
        with open(BISS_FILE) as f:
            lines = clean(f.readlines())
        with open(BISS_FILE, "w") as f:
            f.writelines(lines)

    # -------- Auto Update --------
    def startAuto(self):
        if os.path.exists(INTERVAL_FILE):
            threading.Thread(target=self.autoLoop, daemon=True).start()
        if os.path.exists(FIXED_TIME_FILE):
            threading.Thread(target=self.fixedLoop, daemon=True).start()

    def autoLoop(self):
        while True:
            last = safeRead(LAST_UPDATE, 0)
            interval = safeRead(INTERVAL_FILE, 0)
            if interval > 0 and time.time() - last > interval:
                self.update(False)
            time.sleep(300)

    def fixedLoop(self):
        while True:
            h = safeRead(FIXED_TIME_FILE, -1)
            if h >= 0 and time.localtime().tm_hour == h:
                self.update(False)
                time.sleep(3600)
            time.sleep(60)

    def interval(self):
        opts = [("3 Hours",10800),("6 Hours",21600),("12 Hours",43200),("Off",0)]
        self.session.openWithCallback(
            lambda c: open(INTERVAL_FILE,"w").write(str(c[1])) if c else None,
            ChoiceBox, title="Auto Update Interval", list=opts
        )

    def fixed(self):
        opts = [("%02d:00" % i, i) for i in range(24)]
        self.session.openWithCallback(
            lambda c: open(FIXED_TIME_FILE,"w").write(str(c[1])) if c else None,
            ChoiceBox, title="Fixed Update Time", list=opts
        )

# ---------------- ENTRY ----------------
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="BISS Pro Manager v1.0",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )]
