# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont
from Tools.LoadPixmap import LoadPixmap
import os, time, shutil
from datetime import datetime
import re, unicodedata

try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

PLUGIN_NAME = "BissPro v1.0"
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

# ===== Utilities =====
def create_backup():
    if os.path.exists(BISS_FILE):
        b = BISS_FILE + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(BISS_FILE, b)
        return b
    return None

def restartSoftcam(session, force=False):
    """
    Restart Softcam only if current channel is encrypted (BISS) or force=True
    """
    cams = ["oscam", "ncam", "gcam", "revcam", "vicard"]
    active_cam = None
    
    for cam in cams:
        if os.system("pgrep -x %s >/dev/null 2>&1" % cam) == 0:
            active_cam = cam
            break

    if not force:
        service = session.nav.getCurrentService()
        if service:
            info = service.info()
            caids = info.getInfoObject(iServiceInformation.sCAIDs)
            if not caids or 0x2600 not in caids:  # BISS check
                return False

    for cam in cams:
        os.system("killall -9 %s 2>/dev/null" % cam)
    time.sleep(1)

    cam_to_run = active_cam if active_cam else "oscam"
    path = "/usr/bin/" + cam_to_run
    os.system("%s -b >/dev/null 2>&1 &" % (path if os.path.exists(path) else cam_to_run))
    time.sleep(1)
    return True

def clean_text(text):
    return ''.join(c for c in text if not unicodedata.category(c).startswith(('So', 'Cs')))

def get_sid_for_channel(session, channel_name):
    nav = session.nav
    service = nav.getCurrentService()
    if service:
        info = service.info()
        name = info.getName()
        if channel_name.lower() in name.lower() or channel_name == "":
            return "%08X" % info.getInfo(iServiceInformation.sSID)
    return "00000000"

def get_current_frequency(session):
    service = session.nav.getCurrentService()
    if not service:
        return None
    info = service.info()
    freq = info.getInfo(iServiceInformation.sFrequency)
    return freq

def extract_key(line):
    m = re.findall(r'[0-9A-Fa-f]{2}', line)
    if m and len(m) == 8:
        return ''.join(m).upper()
    return None

def parse_frequency(line):
    match = re.match(r'(\d+)', line)
    if match:
        return int(match.group(1))
    return None

def parse_biss_block(session, lines):
    if len(lines) < 4:
        return None
    channel_name = clean_text(lines[1])
    key = extract_key(lines[3])
    if not key:
        return None
    freq = parse_frequency(lines[2])
    current_freq = get_current_frequency(session)
    if freq and current_freq and freq != current_freq:
        return None
    sid = get_sid_for_channel(session, channel_name)
    return f"F {sid} 00000000 {key} ;{channel_name}"

def parse_biss_file(session, file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    results = []
    for i in range(0, len(lines), 4):
        block = lines[i:i+4]
        line = parse_biss_block(session, block)
        if line:
            results.append(line)
    return results

# ===== Save / Edit / Delete Keys =====
def save_biss_lines(session, lines):
    if not lines:
        return 0
    create_backup()
    existing = []
    if os.path.exists(BISS_FILE):
        with open(BISS_FILE, "r") as f:
            existing = [l.strip() for l in f if l.strip()]
    added = 0
    for l in lines:
        if l not in existing:
            existing.append(l)
            added += 1
    if added > 0:
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(existing) + "\n")
        restartSoftcam(session)
    return added

def delete_key(session, sid=None, channel_name=None):
    if not os.path.exists(BISS_FILE):
        return 0
    create_backup()
    with open(BISS_FILE, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    new_lines = []
    removed = 0
    for line in lines:
        if sid and sid in line:
            removed += 1
            continue
        if channel_name and f";{channel_name}" in line:
            removed += 1
            continue
        new_lines.append(line)
    if removed > 0:
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(new_lines) + "\n")
        restartSoftcam(session)
    return removed

def edit_key(session, sid, new_key):
    if not os.path.exists(BISS_FILE):
        return False
    create_backup()
    updated = False
    with open(BISS_FILE, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    for i, line in enumerate(lines):
        if sid in line:
            parts = line.split()
            if len(parts) >= 4:
                parts[3] = new_key
                lines[i] = " ".join(parts)
                updated = True
                break
    if updated:
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        restartSoftcam(session)
    return updated

# ===== Fetch / Update =====
def fetch_biss_txt():
    try:
        urlretrieve(GITHUB_BISS_URL, TMP_BISS_TXT)
        return os.path.exists(TMP_BISS_TXT)
    except:
        return False

def fetch_update_softcam():
    try:
        urlretrieve(UPDATE_URL, "/tmp/SoftCam.Key")
        if os.path.exists("/tmp/SoftCam.Key"):
            create_backup()
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            # force restart
            restartSoftcam(session=None, force=True)
            return True
    except:
        return False
    return False

def auto_add_keys(session, file_path):
    lines = parse_biss_file(session, file_path)
    return save_biss_lines(session, lines)

def auto_add_keys_live(session):
    """
    Fetch biss.txt, parse keys, add intelligently:
    - Only restart Softcam if current channel needs updated key (BISS)
    """
    if not fetch_biss_txt():
        return 0, "Failed to fetch biss.txt!"
    lines = parse_biss_file(session, TMP_BISS_TXT)
    if not lines:
        return 0, "No keys matched current channel!"
    existing = []
    if os.path.exists(BISS_FILE):
        with open(BISS_FILE, "r") as f:
            existing = [l.strip() for l in f if l.strip()]
    added = 0
    need_restart = False
    for l in lines:
        if l not in existing:
            current_sid = get_sid_for_channel(session, "")
            if current_sid in l:
                need_restart = True
            existing.append(l)
            added += 1
    if added > 0:
        create_backup()
        with open(BISS_FILE, "w") as f:
            f.write("\n".join(existing) + "\n")
    if need_restart:
        restartSoftcam(session)
    return added, f"{added} key(s) added successfully!" if added else "No keys matched current channel!"

# ===== Screens =====
class PasteBissScreen(Screen):
    skin = """
    <screen position="center,center" size="820,300" title="Paste BISS Data">
        <widget name="input" position="20,20" size="780,260" font="Regular;24" />
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        from Components.Input import Input
        self["input"] = Input("", False)
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.process,
            "cancel": self.close
        }, -1)
    def process(self):
        data = self["input"].getText()
        tmp_path = "/tmp/biss_paste.txt"
        with open(tmp_path, "w") as f:
            f.write(data)
        added = auto_add_keys(self.session, tmp_path)
        if added > 0:
            self.session.open(MessageBox, f"{added} keys added successfully!", MessageBox.TYPE_INFO, 3)
        else:
            self.session.open(MessageBox, "No keys matched current channel!", MessageBox.TYPE_INFO, 3)
        self.close()

# ===== Main Menu =====
class BISSPro(Screen):
    skin = """
    <screen position="center,center" size="1024,768" title="BissPro v1.0">
        <widget name="menu" position="40,100" size="940,540" itemHeight="120" scrollbarMode="showOnDemand"/>
    </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.menu_items = [
            ("Add Key", "add", "add.png"),
            ("Edit Key", "edit", "edit.png"),
            ("Delete Key", "delete", "delete.png"),
            ("Update SoftCam", "update", "update.png"),
            ("Auto Add Key (Live)", "auto", "auto.png"),
        ]
        self.menu_list = []
        for t, a, i in self.menu_items:
            pix = LoadPixmap(ICON_PATH + i)
            self.menu_list.append(
                (a, [
                    MultiContentEntryPixmapAlphaTest(pos=(10,10), size=(128,128), png=pix),
                    MultiContentEntryText(pos=(160,50), size=(760,60), font=0, text=t)
                ])
            )
        self["menu"] = MenuList(self.menu_list)
        self["menu"].l.setFont(0, gFont("Regular", 32))
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.ok,
            "cancel": self.close,
            "up": self["menu"].up,
            "down": self["menu"].down
        }, -1)
    def ok(self):
        sel = self["menu"].getCurrent()
        if not sel:
            return
        action = sel[0]
        if action == "add":
            self.session.open(PasteBissScreen)
        elif action == "edit":
            from Components.Input import Input
            class EditKeyScreen(Screen):
                skin = """
                <screen position="center,center" size="820,300" title="Edit Key">
                    <widget name="sid" position="20,50" size="780,50" font="Regular;24" />
                    <widget name="key" position="20,120" size="780,50" font="Regular;24" />
                </screen>
                """
                def __init__(self, session):
                    Screen.__init__(self, session)
                    self["sid"] = Input("", False)
                    self["key"] = Input("", False)
                    self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.process, "cancel": self.close}, -1)
                def process(self):
                    sid = self["sid"].getText().strip()
                    new_key = self["key"].getText().strip().upper()
                    if edit_key(self.session, sid, new_key):
                        self.session.open(MessageBox, "Key updated successfully!", MessageBox.TYPE_INFO, 3)
                    else:
                        self.session.open(MessageBox, "Key not found!", MessageBox.TYPE_ERROR, 3)
                    self.close()
            self.session.open(EditKeyScreen)
        elif action == "delete":
            from Components.Input import Input
            class DeleteKeyScreen(Screen):
                skin = """
                <screen position="center,center" size="820,300" title="Delete Key">
                    <widget name="input" position="20,50" size="780,50" font="Regular;24" />
                </screen>
                """
                def __init__(self, session):
                    Screen.__init__(self, session)
                    self["input"] = Input("", False)
                    self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.process, "cancel": self.close}, -1)
                def process(self):
                    value = self["input"].getText().strip()
                    removed = delete_key(self.session, sid=value) or delete_key(self.session, channel_name=value)
                    if removed > 0:
                        self.session.open(MessageBox, f"{removed} key(s) deleted!", MessageBox.TYPE_INFO, 3)
                    else:
                        self.session.open(MessageBox, "Key not found!", MessageBox.TYPE_ERROR, 3)
                    self.close()
            self.session.open(DeleteKeyScreen)
        elif action == "update":
            if fetch_update_softcam():
                self.session.open(MessageBox, "SoftCam updated successfully!", MessageBox.TYPE_INFO, 3)
            else:
                self.session.open(MessageBox, "Update failed!", MessageBox.TYPE_ERROR, 3)
        elif action == "auto":
            added, msg = auto_add_keys_live(self.session)
            self.session.open(MessageBox, msg, MessageBox.TYPE_INFO if added else MessageBox.TYPE_INFO, 3)

# ===== Plugin =====
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name=PLUGIN_NAME,
        description="Professional BISS Manager v1.0 (Add/Edit/Delete Keys)",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main,
        icon="plugin.png"
    )]
