# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import (
    MultiContentEntryPixmapAlphaTest,
    MultiContentEntryText
)
from enigma import (
    iServiceInformation,
    gFont,
    eTimer,
    getDesktop
)
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve, Request
import os, re, shutil, subprocess, base64

# ==============================
# Plugin Constants
# ==============================
PLUGIN_NAME    = "BissPro"
PLUGIN_VERSION = "1.1"
PLUGIN_PATH    = "/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH      = PLUGIN_PATH + "/icons/"
PLUGIN_ICON    = ICON_PATH + "plugin.png"

UPDATE_URL   = "https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL = "https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"

lock = Lock()

# ==============================
# Auto Scale
# ==============================
class AutoScale:
    BASE_W = 1920.0
    BASE_H = 1080.0

    def __init__(self):
        d = getDesktop(0).size()
        self.w = d.width()
        self.h = d.height()
        self.scale = min(self.w / self.BASE_W, self.h / self.BASE_H)

    def px(self, v):
        return int(v * self.scale)

    def font(self, v):
        return int(max(18, v * self.scale))

# ==============================
# SoftCam.Key Path
# ==============================
def get_key_path():
    paths = [
        "/etc/tuxbox/config/oscam/SoftCam.Key",
        "/etc/tuxbox/config/SoftCam.Key",
        "/usr/keys/SoftCam.Key"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "/etc/tuxbox/config/SoftCam.Key"

BISS_FILE = get_key_path()

def ensure_biss_file():
    try:
        os.makedirs(os.path.dirname(BISS_FILE), exist_ok=True)
        if not os.path.exists(BISS_FILE):
            open(BISS_FILE, "w").close()
        return os.access(BISS_FILE, os.W_OK)
    except:
        return False

# ==============================
# WebIf Reload (OSCam / NCam)
# ==============================
def get_cam_webif_data():
    confs = [
        "/etc/tuxbox/config/oscam/oscam.conf",
        "/etc/tuxbox/config/ncam/ncam.conf",
        "/etc/tuxbox/config/oscam.conf",
        "/etc/tuxbox/config/ncam.conf",
    ]

    for path in confs:
        if not os.path.exists(path):
            continue

        try:
            content = open(path, "r", errors="ignore").read()
        except:
            continue

        m = re.search(r'\[webif\](.*?)(?=\n\[|$)', content, re.S | re.I)
        if not m:
            continue

        section = m.group(1)

        port = re.search(r'httpport\s*=\s*(\d+)', section, re.I)
        user = re.search(r'httpuser\s*=\s*(.*)', section, re.I)
        pwd  = re.search(r'httppwd\s*=\s*(.*)', section, re.I)

        return {
            "port": port.group(1).strip() if port else None,
            "user": user.group(1).strip() if user else "",
            "pass": pwd.group(1).strip() if pwd else ""
        }
    return None

def reload_cam_keys():
    cfg = get_cam_webif_data()

    if cfg and cfg["port"]:
        try:
            url = f"http://127.0.0.1:{cfg['port']}/entitlements.html?action=reload"
            req = Request(url)

            user = cfg["user"] if isinstance(cfg["user"], str) else ""
            pwd  = cfg["pass"] if isinstance(cfg["pass"], str) else ""

            if user or pwd:
                auth = f"{user}:{pwd}"
                auth64 = base64.b64encode(auth.encode()).decode()
                req.add_header("Authorization", f"Basic {auth64}")

            with urlopen(req, timeout=3) as r:
                if r.status == 200:
                    print("[BissPro] Reload via WebIf OK")
                    return True
        except Exception as e:
            print("[BissPro] WebIf reload failed:", e)

    for cam in ("oscam", "ncam"):
        os.system(f"killall -HUP {cam} >/dev/null 2>&1")

    print("[BissPro] Reload via killall fallback")
    return True

# ==============================
# BISS Utils
# ==============================
def extract_biss_key_from_block(block):
    raw = re.sub(r'[^0-9A-Fa-f]', '', block[3])
    return raw[:16].upper() if len(raw) >= 16 else None

def write_biss_key(sid, key, name):
    if not ensure_biss_file():
        return False

    key = key[:16].upper()

    with lock:
        lines = []
        if os.path.exists(BISS_FILE):
            lines = open(BISS_FILE).readlines()

        new = []
        found = False
        for l in lines:
            if l.strip().startswith("F") and sid in l:
                new.append(f"F {sid} 00000000 {key} ;{name}\n")
                found = True
            else:
                new.append(l)

        if not found:
            new.append(f"F {sid} 00000000 {key} ;{name}\n")

        open(BISS_FILE, "w").writelines(new)

    return True

# ==============================
# Main Screen
# ==============================
class BISSPro(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        self.skin = f"""
        <screen position="center,center"
            size="{self.ui.px(1100)},{self.ui.px(750)}"
            title="BissPro Manager">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}"
                size="{self.ui.px(1060)},{self.ui.px(600)}"
                itemHeight="{self.ui.px(120)}"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}"
                size="{self.ui.px(1060)},{self.ui.px(50)}"
                font="Regular;{self.ui.font(28)}"
                halign="center"/>
        </screen>"""
        Screen.__init__(self, session)

        self["status"] = Label("")
        self.build_menu()

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "NumberActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
                "up": self["menu"].up,
                "down": self["menu"].down
            }, -1
        )

        self.timer = eTimer()
        self.timer.callback.append(self.show_result)

    def build_menu(self):
        items = [
            ("Add BISS Manually", "add", ICON_PATH + "add.png"),
            ("Update SoftCam.Key", "upd", ICON_PATH + "update.png"),
            ("Auto Add BISS", "auto", ICON_PATH + "autoadd.png")
        ]

        lst = []
        for t, a, p in items:
            lst.append((a, [
                MultiContentEntryPixmapAlphaTest(
                    pos=(self.ui.px(10), self.ui.px(10)),
                    size=(self.ui.px(100), self.ui.px(100)),
                    png=LoadPixmap(p)
                ),
                MultiContentEntryText(
                    pos=(self.ui.px(130), self.ui.px(30)),
                    size=(self.ui.px(800), self.ui.px(60)),
                    font=0,
                    text=t
                )
            ]))

        self["menu"] = MenuList(lst)
        self["menu"].l.setFont(0, gFont("Regular", self.ui.font(32)))

    def update_status(self, txt):
        self["status"].setText(txt)

    # ==============================
    # Menu Actions
    # ==============================
    def ok(self):
        action = self["menu"].getCurrent()[0]
        service = self.session.nav.getCurrentService()

        if action == "add" and service:
            self.start_manual(service)
        elif action == "upd":
            Thread(target=self.do_update).start()
        elif action == "auto" and service:
            Thread(target=self.do_auto, args=(service,)).start()

    # ==============================
    # Manual Add
    # ==============================
    def start_manual(self, service):
        self.input_key = ""
        self.service = service
        self.update_status("Key: " + "_" * 16)
        self.ask_hex()

    def ask_hex(self):
        if len(self.input_key) >= 16:
            self.save_manual()
            return
        self.session.openWithCallback(
            self.hex_selected,
            ChoiceBox,
            title="Select Hex",
            list=["A","B","C","D","E","F"]
        )

    def hex_selected(self, res):
        if res:
            self.input_key += res
            self.update_status("Key: " + self.input_key + "_"*(16-len(self.input_key)))
            self.ask_hex()

    def keyNumberGlobal(self, n):
        if hasattr(self, "input_key") and len(self.input_key) < 16:
            self.input_key += str(n)
            self.update_status("Key: " + self.input_key + "_"*(16-len(self.input_key)))
            if len(self.input_key) == 16:
                self.save_manual()
        return True

    def save_manual(self):
        info = self.service.info()
        sid  = "%08X" % info.getInfo(iServiceInformation.sSID)
        name = info.getName()

        ok = write_biss_key(sid, self.input_key, name)
        if ok:
            Thread(target=reload_cam_keys).start()
            self.res = (True, "BISS key added")
        else:
            self.res = (False, "Write failed")

        self.timer.start(100, True)

    # ==============================
    # Update SoftCam.Key
    # ==============================
    def do_update(self):
        try:
            self.update_status("Updating SoftCam.Key...")
            urlretrieve(UPDATE_URL, "/tmp/SoftCam.Key")
            shutil.copy("/tmp/SoftCam.Key", BISS_FILE)
            Thread(target=reload_cam_keys).start()
            self.res = (True, "SoftCam.Key updated")
        except:
            self.res = (False, "Update failed")
        self.timer.start(100, True)

    # ==============================
    # Auto Add
    # ==============================
    def do_auto(self, service):
        try:
            self.update_status("Searching BISS key...")
            info = service.info()
            sid  = "%08X" % info.getInfo(iServiceInformation.sSID)
            name = info.getName()

            raw = urlopen(BISS_TXT_URL, timeout=10).read().decode("utf-8","ignore")
            lines = raw.splitlines()

            for i in range(0, len(lines), 4):
                block = lines[i:i+4]
                key = extract_biss_key_from_block(block)
                if key and write_biss_key(sid, key, name):
                    Thread(target=reload_cam_keys).start()
                    self.res = (True, "BISS key added automatically")
                    self.timer.start(100, True)
                    return

            self.res = (False, "No key found")
        except:
            self.res = (False, "Auto add failed")

        self.timer.start(100, True)

    def show_result(self):
        self.session.open(
            MessageBox,
            self.res[1],
            MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR,
            5
        )
        self.update_status("")

# ==============================
# Plugin Entry
# ==============================
def main(session, **kwargs):
    session.open(BISSPro)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="BissPro Manager",
            icon=PLUGIN_ICON,
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=main
        )
    ]
