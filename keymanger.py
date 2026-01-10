from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Input import Input
from enigma import eServiceCenter

from .keymanager import save_biss_key

class BissEditorScreen(Screen):
    skin = """
    <screen name="BissEditor" position="center,center" size="600,200" title="BISS Editor">
        <widget name="info" position="20,20" size="560,40" font="Regular;22"/>
        <widget name="input" position="20,80" size="560,40" font="Regular;24"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)

        self["info"] = Label("ادخل كود BISS (16 HEX)")
        self["input"] = Input(text="", maxSize=16, type=Input.TEXT)

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {
                "ok": self.saveKey,
                "cancel": self.close
            },
            -1
        )

    def saveKey(self):
        service = self.session.nav.getCurrentlyPlayingServiceReference()
        sid = service.toString().split(":")[3]
        key = self["input"].getText().upper()

        save_biss_key(sid, key)
        self["info"].setText("تم حفظ الكود بنجاح")
