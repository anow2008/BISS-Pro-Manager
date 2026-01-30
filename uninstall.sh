#!/bin/sh
# ==========================================
#  BissPro Uninstaller
#  Author : anow2008
# ==========================================

PLUGIN="BissPro"
TARGET="/usr/lib/enigma2/python/Plugins/Extensions/$PLUGIN"

stop_enigma2() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop enigma2
    else
        init 4
    fi
    sleep 2
}

start_enigma2() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl start enigma2
    else
        init 3
    fi
}

stop_softcams() {
    killall oscam ncam gcam cccam 2>/dev/null
}

echo "================================="
echo " Removing BissPro Plugin"
echo "================================="

stop_enigma2
stop_softcams

rm -rf "$TARGET"

sync
start_enigma2

echo "================================="
echo " ✅ BissPro Removed Successfully"
echo "================================="

exit 0
