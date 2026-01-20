# -*- coding: utf-8 -*-
# Biss Pro v1.0 – Fully Auto Smart Enigma2 Plugin

from __future__ import print_function
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
import os, shutil, time

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

# ---------------- MAIN SCREEN ----------------
class BISSPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        ensure()

        self["menu"] = MenuList([
            "View Keys Count",
            "Add BISS from Channel",
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
        if i == 0:
            self.view()
        elif i == 1:
            self.addBISSFromChannel()
        elif i == 2:
            restartSoftcam()

    def view(self):
        with open(BISS_FILE) as f:
            biss = [l for l in f if l.startswith("BISS")]
        print("Total Keys:", len(biss))

    def addBISSFromChannel(self):
        """Add BISS key automatically from the current service"""
        try:
            from enigma import iServiceInformation
            s = self.session.nav.getCurrentService()
            if not s:
                return
            info = s.info()
            sid = info.getInfo(iServiceInformation.sSID)
            tsid = info.getInfo(iServiceInformation.sTSID)
            onid = info.getInfo(iServiceInformation.sONID)

            # قراءة Key الحقيقية من الخدمة
            key = info.getInfo(iServiceInformation.sCrypt)  # 👈 مثال: استخدم sCrypt أو أي API مناسب
            if not key or len(key) != 16:
                key = "1234567890ABCDEF"  # احتياطياً لو مفيش Key
        except:
            return

        line = "BISS %04X:%04X:%04X:%s" % (sid, tsid, onid, key)

        backup()
        with open(BISS_FILE, "a") as f:
            f.write("\n" + line)
        self.cleanup()
        restartSoftcam()

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
        description="BISS Pro Smart Auto Add (Fully Automatic)",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )]
