# -*- coding: utf-8 -*-

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.MessageBox import MessageBox
from enigma import iServiceInformation

from .core import add_or_edit_key, delete_key
from .online import update_softcam, auto_add_biss
from .settings import BissProSettings

PLUGIN_NAME = "BissPro Manager"

class BissPro(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)

        self.list = [
            ("Add / Edit BISS Key", "edit"),
            ("Delete BISS Key", "delete"),
            ("Auto Add from Internet", "auto"),
            ("Update SoftCam.Key", "update"),
            ("Settings", "settings"),
        ]

        self["menu"] = MenuList(self.list)
        self["status"] = Label("Ready")

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.ok, "cancel": self.close},
            -1
        )

    def ok(self):
        sel = self["menu"].getCurrent()[1]
        service = self.session.nav.getCurrentService()
        info = service and service.info()

        if sel in ("edit", "delete") and not info:
            self.session.open(MessageBox, "No active service", MessageBox.TYPE_ERROR)
            return

        sid = "%04X" % (info.getInfo(iServiceInformation.sSID) & 0xFFFF)
        name = info.getName().replace(" ", "_")

        if sel == "edit":
            add_or_edit_key(self.session, sid, name)

        elif sel == "delete":
            delete_key(self.session, sid)

        elif sel == "auto":
            auto_add_biss(self.session, sid)

        elif sel == "update":
            update_softcam(self.session)

        elif sel == "settings":
            self.session.open(BissProSettings)

def main(session, **kwargs):
    session.open(BissPro)

def Plugins(**kwargs):
    return PluginDescriptor(
        name=PLUGIN_NAME,
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )
