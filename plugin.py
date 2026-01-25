# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from enigma import iServiceInformation, gFont
from Tools.LoadPixmap import LoadPixmap
import os, time, shutil
from datetime import datetime
import re, unicodedata

from twisted.web.client import downloadPage

PLUGIN_NAME = "BissPro v1.1"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH = PLUGIN_PATH + "/icons/"

UPDATE_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
GITHUB_BISS_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

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
TMP_BISS_TXT = "/tmp/biss.txt"
TMP_UPDATE_FILE = "/tmp/SoftCam.Key"

# ===== Utilities =====
def create_backup():
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)

def restartSoftcam(session, force=False):
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]
    active_cam = None

    for cam in cams:
        if os.system("pgrep -x %s >/dev/null 2>&1" % cam) == 0:
            active_cam = cam
            break

    if not force and session:
        service = session.nav.getCurrentService()
        if service:
            caids = service.info().getInfoObject(iServiceInformation.sCAIDs)
            if not caids or 0x2600 not in caids:
                return

    for cam in cams:
        os.system("killall -9 %s 2>/dev/null" % cam)
    time.sleep(1)

    cam_to_run = active_cam if active_cam else "oscam"
    os.system("%s -b >/dev/null 2>&1 &" % cam_to_run)

def clean_text(text):
    return ''.join(c for c in text if not unicodedata.category(c).startswith(('So', 'Cs')))

def get_sid_for_channel(session, channel_name):
    service = session.nav.getCurrentService()
    if service:
        info = service.info()
        if channel_name.lower() in info.getName().lower() or channel_name == "":
            return "%08X" % info.getInfo(iServiceInformation.sSID)
    return "00000000"

def get_current_frequency(session):
    service = session.nav.getCurrentService()
    if service:
        return service.info().getInfo(iServiceInformation.sFrequency)

def extract_key(line):
    m = re.findall(r'[0-9A-Fa-f]{2}', line)
    return ''.join(m).upper() if len(m) == 8 else None

def parse_frequency(line):
    m = re.match(r'(\d+)', line)
    return int(m.group(1)) if m else None

# ===== Frequency tolerance =====
def freq_match(f1, f2, tolerance=3000):  # 3 MHz
    return abs(f1 - f2) <= tolerance

def parse_biss_block(session, lines):
    if len(lines) < 4:
        return
    channel_name = clean_text(lines[1])
    key = extract_key(lines[3])
    if not key:
        return
    freq = parse_frequency(lines[2])
    current_freq = get_current_frequency(session)
    if freq and current_freq and not freq_match(freq * 1000, current_freq):
        return
    sid = get_sid_for_channel(session, channel_name)
    return f"F {sid} 00000000 {key} ;{channel_name}"

def parse_biss_file(session, file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path) as f:
        lines = [l.strip() for l in f if l.strip()]
    out = []
    for i in range(0, len(lines), 4):
        r = parse_biss_block(session, lines[i:i+4])
        if r:
            out.append(r)
    return out

def save_biss_lines(session, lines):
    if not lines:
        return 0
    create_backup()
    existing = []
    if os.path.exists(BISS_FILE):
        with open(BISS_FILE) as f:
            existing = [l.strip() for l in f if l.strip()]
    added = 0
    for l in lines:
        if l not in existing:
            existing.append(l)
            added += 1
    if added:
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(existing) + "\n")
        restartSoftcam(session)
    return added

def delete_key(session, value):
    if not os.path.exists(BISS_FILE):
        return 0
    create_backup()
    with open(BISS_FILE) as f:
        lines = [l.strip() for l in f if l.strip()]
    new = []
    removed = 0
    for l in lines:
        if value in l:
            removed += 1
        else:
            new.append(l)
    if removed:
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(new) + "\n")
        restartSoftcam(session)
    return removed

def edit_key(session, sid=None, new_key=None):
    if not os.path.exists(BISS_FILE):
        return False
    create_backup()
    with open(BISS_FILE) as f:
        lines = [l.strip() for l in f if l.strip()]
    
    if not sid:
        sid = get_sid_for_channel(session, "")
    
    if not sid:
        return False

    for i, l in enumerate(lines):
        if sid in l:
            p = l.split()
            p[3] = new_key
            lines[i] = " ".join(p)
            with open(BISS_FILE, "w") as f:
                f.write("\n".join(lines) + "\n")
            restartSoftcam(session)
            return True
    return False

# ===== ASYNC fetch =====
def fetch_biss_txt(cb, eb):
    d = downloadPage(GITHUB_BISS_URL.encode("utf-8"), TMP_BISS_TXT)
    d.addCallback(lambda _: cb())
    d.addErrback(lambda e: eb())

def auto_add_keys_live(session, done):
    def ok():
        added = save_biss_lines(session, parse_biss_file(session, TMP_BISS_TXT))
        done(added, f"{added} key(s) added!" if added else "No keys matched!")
    fetch_biss_txt(ok, lambda: done(0, "Download failed!"))

def update_softcam_key(cb, eb):
    d = downloadPage(UPDATE_URL.encode("utf-8"), TMP_UPDATE_FILE)
    def on_success(_):
        create_backup()
        shutil.copy(TMP_UPDATE_FILE, BISS_FILE)
        restartSoftcam(None, force=True)
        cb("Update successful!")
    def on_error(err):
        eb("Update failed!")
    d.addCallback(on_success)
    d.addErrback(on_error)

# ===== Screens =====
from Components.Input import Input

class PasteBissScreen(Screen):
    # واجهة إدخال المفتاح يدوياً - أبعاد مرنة
    skin = """
    <screen position="center,center" size="900,400" title="Paste BISS Data" backgroundColor="#101010">
        <widget name="input" position="20,20" size="860,300" font="Regular;26" foregroundColor="#ffffff" backgroundColor="#202020" scrollbarMode="showOnDemand"/>
        <eLabel text="Press OK to Save, Cancel to Exit" position="20,340" size="860,40" font="Regular;22" halign="center" foregroundColor="#aaaaaa" transparent="1" />
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self["input"] = Input("", False)
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.process,
            "cancel": self.close
        }, -1)

    def process(self):
        p = "/tmp/biss_paste.txt"
        with open(p, "w") as f:
            f.write(self["input"].getText())
        added = save_biss_lines(self.session, parse_biss_file(self.session, p))
        self.session.open(MessageBox, f"{added} key(s) added!", MessageBox.TYPE_INFO, 3)
        self.close()

class BISSPro(Screen):
    # الواجهة الرئيسية بتصميم FHD عصري
    skin = """
    <screen name="BISSPro" position="center,center" size="1000,650" title="BissPro Professional v1.1" backgroundColor="#151515">
        <eLabel position="0,0" size="1000,80" backgroundColor="#0055ff" zPosition="-1" />
        <eLabel text="BISS PRO MANAGER" position="120,15" size="800,50" font="Regular;35" foregroundColor="#ffffff" transparent="1" halign="left" />
        
        <widget name="menu" position="30,100" size="940,480" 
                itemHeight="90" 
                scrollbarMode="showOnDemand" 
                selectionColor="#333333" 
                transparent="1" />

        <eLabel position="0,590" size="1000,60" backgroundColor="#222222" zPosition="-1" />
        <eLabel text="Select an option and press OK" position="30,605" size="940,30" font="Regular;20" foregroundColor="#cccccc" transparent="1" halign="center" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)

        items = [
            ("Add Key (Manual Paste)", "add", ICON_PATH + "add.png"),
            ("Edit Current Key", "edit", ICON_PATH + "edit.png"),
            ("Delete Key (SID/Name)", "delete", ICON_PATH + "delete.png"),
            ("Auto Grab Key (Live)", "auto", ICON_PATH + "auto.png"),
            ("Update SoftCam.Key File", "update", ICON_PATH + "update.png")
        ]

        self.list = []
        for text, action, icon in items:
            pix = LoadPixmap(icon) if os.path.exists(icon) else None
            # MultiContentEntryText بتنسيق أفضل للأيقونة والنص
            res = [action]
            res.append(MultiContentEntryText(pos=(110, 25), size=(800, 50), font=0, text=text, flags=0, color=0xffffff))
            if pix:
                # وضع الأيقونة في المنتصف رأسياً بجانب النص
                res.append((pix, 25, 15, 60, 60)) 
            self.list.append(res)

        self["menu"] = MenuList(self.list)
        # ضبط الخط ليناسب الأبعاد الجديدة
        self["menu"].l.setFont(0, gFont("Regular", 30))
        self["menu"].l.setItemHeight(90)

        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.ok,
            "cancel": self.close
        }, -1)

# ===== Plugin =====
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="Professional BISS Manager v1.1 (Add/Edit/Delete Keys + Auto Update)",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )]
