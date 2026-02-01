# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from enigma import iServiceInformation, gFont, eTimer, getDesktop
from Tools.LoadPixmap import LoadPixmap
from threading import Thread, Lock
from urllib.request import urlopen, urlretrieve, Request
import os, re, shutil, base64

PLUGIN_NAME="BissPro"
PLUGIN_VERSION="1.0"
PLUGIN_PATH="/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
ICON_PATH=PLUGIN_PATH+"/icons/"
PLUGIN_ICON=ICON_PATH+"plugin.png"
UPDATE_URL="https://raw.githubusercontent.com/anow2008/softcam.key/main/softcam.key"
BISS_TXT_URL="https://raw.githubusercontent.com/anow2008/softcam.key/refs/heads/main/biss.txt"
lock=Lock()

class AutoScale:
    BASE_W=1920.0;BASE_H=1080.0
    def __init__(self):
        d=getDesktop(0).size();self.w=d.width();self.h=d.height();self.scale=min(self.w/self.BASE_W,self.h/self.BASE_H)
    def px(self,v): return int(v*self.scale)
    def font(self,v): return int(max(18,v*self.scale))

def get_key_path():
    paths=["/etc/tuxbox/config/oscam/SoftCam.Key","/etc/tuxbox/config/SoftCam.Key","/usr/keys/SoftCam.Key"]
    for p in paths:
        if os.path.exists(p): return p
    return "/etc/tuxbox/config/SoftCam.Key"
BISS_FILE=get_key_path()

def ensure_biss_file():
    try:
        os.makedirs(os.path.dirname(BISS_FILE),exist_ok=True)
        if not os.path.exists(BISS_FILE): open(BISS_FILE,"w").close()
        return os.access(BISS_FILE,os.W_OK)
    except: return False

def get_cam_webif_data():
    confs=["/etc/tuxbox/config/oscam/oscam.conf","/etc/tuxbox/config/ncam/ncam.conf","/etc/tuxbox/config/oscam.conf","/etc/tuxbox/config/ncam.conf"]
    for path in confs:
        if not os.path.exists(path): continue
        try: content=open(path,"r",errors="ignore").read()
        except: continue
        m=re.search(r'\[webif\](.*?)(?=\n\[|$)',content,re.S|re.I)
        if not m: continue
        section=m.group(1)
        port=re.search(r'httpport\s*=\s*(\d+)',section,re.I)
        user=re.search(r'httpuser\s*=\s*(.*)',section,re.I)
        pwd=re.search(r'httppwd\s*=\s*(.*)',section,re.I)
        return {"port":port.group(1).strip() if port else None,"user":user.group(1).strip() if user else "","pass":pwd.group(1).strip() if pwd else ""}
    return None

def reload_cam_keys():
    cfg=get_cam_webif_data()
    if cfg and cfg["port"]:
        try:
            url=f"http://127.0.0.1:{cfg['port']}/entitlements.html?action=reload"
            req=Request(url)
            user=cfg["user"] if isinstance(cfg["user"],str) else ""
            pwd=cfg["pass"] if isinstance(cfg["pass"],str) else ""
            if user or pwd:
                auth=base64.b64encode(f"{user}:{pwd}".encode()).decode()
                req.add_header("Authorization",f"Basic {auth}")
            with urlopen(req,timeout=3) as r:
                if r.status==200: return True
        except: pass
    for cam in ("oscam","ncam"): os.system(f"killall -HUP {cam} >/dev/null 2>&1")
    return True

def extract_biss_key_from_block(block):
    raw=re.sub(r'[^0-9A-Fa-f]','',block[3])
    return raw[:16].upper() if len(raw)>=16 else None

def write_biss_key(sid,key,name):
    if not ensure_biss_file(): return False
    key=key[:16].upper()
    with lock:
        lines=[]
        if os.path.exists(BISS_FILE): lines=open(BISS_FILE).readlines()
        new=[];found=False
        for l in lines:
            if l.strip().startswith("F") and sid in l: new.append(f"F {sid} 00000000 {key} ;{name}\n");found=True
            else: new.append(l)
        if not found: new.append(f"F {sid} 00000000 {key} ;{name}\n")
        open(BISS_FILE,"w").writelines(new)
    return True

class HexInputScreen(Screen):
    def __init__(self,session):
        self.ui=AutoScale()
        size_w=self.ui.px(700);size_h=self.ui.px(500)
        Screen.__init__(self,session)
        self.skin=f"""
        <screen position="center,center" size="{size_w},{size_h}" title="Enter BISS Key">
            <widget name="keylabel" position="{self.ui.px(50)},{self.ui.px(30)}" size="{self.ui.px(600)},{self.ui.px(50)}" font="Regular;{self.ui.font(32)}" halign="center"/>
            <widget name="hexlist" position="{self.ui.px(150)},{self.ui.px(100)}" size="{self.ui.px(400)},{self.ui.px(260)}" itemHeight="{self.ui.px(50)}"/>
            <widget name="help" position="{self.ui.px(50)},{self.ui.px(380)}" size="{self.ui.px(600)},{self.ui.px(80)}" font="Regular;{self.ui.font(22)}" halign="center"/>
        </screen>"""
        self.hexchars=["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"]
        self.key=""
        self["keylabel"]=Label();self["help"]=Label("OK=Add 0-9=Direct Input Yellow=Clear Green=Save Red=Exit")
        self["hexlist"]=MenuList(self.hexchars)
        self["actions"]=ActionMap(["OkCancelActions","ColorActions","NumberActions"],{
            "ok":self.add_char,"green":self.save,"yellow":self.backspace,"red":self.cancel,"cancel":self.cancel,
            "0":self.keyNumberGlobal,"1":self.keyNumberGlobal,"2":self.keyNumberGlobal,"3":self.keyNumberGlobal,
            "4":self.keyNumberGlobal,"5":self.keyNumberGlobal,"6":self.keyNumberGlobal,"7":self.keyNumberGlobal,
            "8":self.keyNumberGlobal,"9":self.keyNumberGlobal},-1)
        self.update_label()
    def update_label(self):
        self["keylabel"].setText("Key: "+self.key+"_"*(16-len(self.key)))
    def add_char(self):
        if len(self.key)<16: self.key+=self["hexlist"].getCurrent();self.update_label()
    def keyNumberGlobal(self,number):
        if len(self.key)<16: self.key+=str(number);self.update_label()
        return True
    def backspace(self): self.key=self.key[:-1];self.update_label()
    def save(self): 
        if len(self.key)==16: self.close(self.key)
    def cancel(self): self.close(None)

class BISSPro(Screen):
    def __init__(self,session):
        self.ui=AutoScale()
        self.skin=f"""
        <screen position="center,center" size="{self.ui.px(1100)},{self.ui.px(750)}" title="BissPro Manager">
            <widget name="menu" position="{self.ui.px(20)},{self.ui.px(20)}" size="{self.ui.px(1060)},{self.ui.px(600)}" itemHeight="{self.ui.px(120)}"/>
            <widget name="status" position="{self.ui.px(20)},{self.ui.px(650)}" size="{self.ui.px(1060)},{self.ui.px(50)}" font="Regular;{self.ui.font(28)}" halign="center"/>
        </screen>"""
        Screen.__init__(self,session)
        self["status"]=Label();self.build_menu()
        self["actions"]=ActionMap(["OkCancelActions","DirectionActions"],{"ok":self.ok,"cancel":self.close,"up":self["menu"].up,"down":self["menu"].down},-1)
        self.timer=eTimer();self.timer.callback.append(self.show_result)

    def build_menu(self):
        items=[("Add BISS Manually","add",ICON_PATH+"add.png"),("Update SoftCam.Key","upd",ICON_PATH+"update.png"),("Auto Add BISS","auto",ICON_PATH+"autoadd.png")]
        lst=[]
        for t,a,p in items:
            lst.append((a,[MultiContentEntryPixmapAlphaTest(pos=(self.ui.px(10),self.ui.px(10)),size=(self.ui.px(100),self.ui.px(100)),png=LoadPixmap(p)),
                          MultiContentEntryText(pos=(self.ui.px(130),self.ui.px(30)),size=(self.ui.px(800),self.ui.px(60)),font=0,text=t)]))
        self["menu"]=MenuList(lst)
        self["menu"].l.setFont(0,gFont("Regular",self.ui.font(32)))
    def update_status(self,txt): self["status"].setText(txt)
    def ok(self):
        action=self["menu"].getCurrent()[0];service=self.session.nav.getCurrentService()
        if action=="add" and service:self.start_manual(service)
        elif action=="upd":Thread(target=self.do_update).start()
        elif action=="auto" and service:Thread(target=self.do_auto,args=(service,)).start()
    def start_manual(self,service): self.service=service;self.session.openWithCallback(self.manual_done,HexInputScreen)
    def manual_done(self,key):
        if not key: return
        info=self.service.info();sid="%08X"%info.getInfo(iServiceInformation.sSID);name=info.getName()
        if write_biss_key(sid,key,name): Thread(target=reload_cam_keys).start();self.res=(True,"BISS key added")
        else:self.res=(False,"Write failed")
        self.timer.start(100,True)
    def do_update(self):
        try:
            self.update_status("Updating SoftCam.Key...");urlretrieve(UPDATE_URL,"/tmp/SoftCam.Key");shutil.copy("/tmp/SoftCam.Key",BISS_FILE)
            Thread(target=reload_cam_keys).start();self.res=(True,"SoftCam.Key updated")
        except: self.res=(False,"Update failed")
        self.timer.start(100,True)
    def do_auto(self,service):
        try:
            self.update_status("Searching BISS key...");info=service.info();sid="%08X"%info.getInfo(iServiceInformation.sSID);name=info.getName()
            raw=urlopen(BISS_TXT_URL,timeout=10).read().decode("utf-8","ignore");lines=raw.splitlines();found=False
            for i in range(0,len(lines),4):
                block=lines[i:i+4];key=extract_biss_key_from_block(block)
                if key and write_biss_key(sid,key,name):Thread(target=reload_cam_keys).start();self.res=(True,"BISS key added automatically");found=True;break
            if not found:self.res=(False,"No key found. Make sure you are on the encrypted channel.")
        except: self.res=(False,"Auto add failed")
        self.timer.start(100,True)
    def show_result(self):
        self.session.open(MessageBox,self.res[1],MessageBox.TYPE_INFO if self.res[0] else MessageBox.TYPE_ERROR,5);self.update_status("")

def main(session,**kwargs): session.open(BISSPro)
def Plugins(**kwargs): return [PluginDescriptor(name=PLUGIN_NAME,description="BissPro Manager",icon=PLUGIN_ICON,where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main)]
