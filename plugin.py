class HexInputScreen(Screen):
    def __init__(self, session):
        self.ui = AutoScale()
        Screen.__init__(self, session)
        # تصميم يعتمد على توزيع العناصر بشكل متناسق (Grid Look)
        self.skin = f"""
        <screen position="center,center" size="{self.ui.px(800)},{self.ui.px(600)}" title="BISS Key Input">
            <eLabel position="0,0" size="800,80" backgroundColor="#1a1a1a" zPosition="-1" />
            
            <widget name="keylabel" position="20,15" size="760,50" font="Regular;{self.ui.font(44)}" halign="center" valign="center" foregroundColor="#f0a30a" transparent="1"/>
            
            <widget name="hexlist" position="150,100" size="500,320" itemHeight="{self.ui.px(60)}" font="Regular;{self.ui.font(36)}" scrollbarMode="showNever" selectionPixmap="{ICON_PATH}selection.png" transparent="1"/>
            
            <eLabel position="40,440" size="720,2" backgroundColor="#444444" />
            
            <ePixmap pixmap="skin_default/buttons/red.png" position="40,470" size="30,30" alphatest="on" />
            <widget name="key_red" position="80,470" size="150,30" font="Regular;22" halign="left" transparent="1" />
            
            <ePixmap pixmap="skin_default/buttons/green.png" position="280,470" size="30,30" alphatest="on" />
            <widget name="key_green" position="320,470" size="150,30" font="Regular;22" halign="left" transparent="1" />
            
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="520,470" size="30,30" alphatest="on" />
            <widget name="key_yellow" position="560,470" size="150,30" font="Regular;22" halign="left" transparent="1" />
            
            <widget name="help" position="20,530" size="760,40" font="Regular;20" halign="center" foregroundColor="#888888" transparent="1"/>
        </screen>"""

        self.key = ""
        self["keylabel"] = Label("0000 0000 0000 0000")
        self["key_red"] = Label("Cancel")
        self["key_green"] = Label("Save")
        self["key_yellow"] = Label("Delete")
        self["help"] = Label("Navigation: Arrows | Select: OK | Direct: 0-9")
        
        # توزيع الحروف بشكل أسهل (أرقام أولاً ثم حروف)
        self.hex_chars = ["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"]
        self["hexlist"] = MenuList(self.hex_chars)
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "NumberActions"], {
            "ok": self.add,
            "cancel": lambda: self.close(None),
            "red": lambda: self.close(None),
            "green": self.save,
            "yellow": self.backspace,
            "0": lambda: self.keyNum("0"), "1": lambda: self.keyNum("1"), "2": lambda: self.keyNum("2"),
            "3": lambda: self.keyNum("3"), "4": lambda: self.keyNum("4"), "5": lambda: self.keyNum("5"),
            "6": lambda: self.keyNum("6"), "7": lambda: self.keyNum("7"), "8": lambda: self.keyNum("8"),
            "9": lambda: self.keyNum("9")
        }, -1)

    def update_label(self):
        # إضافة مسافات جمالية كل 4 رموز
        display = self.key + "_" * (16 - len(self.key))
        formatted = " ".join([display[i:i+4] for i in range(0, len(display), 4)])
        self["keylabel"].setText(formatted)

    def add(self):
        if len(self.key) < 16:
            self.key += self["hexlist"].getCurrent()
            self.update_label()

    def keyNum(self, num):
        if len(self.key) < 16:
            self.key += num
            self.update_label()

    def backspace(self):
        if self.key:
            self.key = self.key[:-1]
            self.update_label()

    def save(self):
        if len(self.key) == 16:
            self.close(self.key)
        else:
            self.session.open(MessageBox, "Please enter all 16 digits!", MessageBox.TYPE_ERROR)
