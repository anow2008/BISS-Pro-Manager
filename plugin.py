from Plugins.Plugin import PluginDescriptor
from .ui import BissEditorScreen

def main(session, **kwargs):
    session.open(BissEditorScreen)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="BISS Editor",
            description="Manual BISS Key Editor",
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            fnc=main
        )
    ]
