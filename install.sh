#!/bin/sh
# ==========================================
#  BissPro Online Installer (Install Only)
#  Author : anow2008
# ==========================================

PLUGIN="BissPro"
BASE_DIR="/usr/lib/enigma2/python/Plugins/Extensions"
TARGET="$BASE_DIR/$PLUGIN"
REPO="https://github.com/anow2008/BissPro.git"

# --- Detect Python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    PYTHON=python
fi

# --- Functions ---
stop_enigma2() {
    echo "⏹ Stopping Enigma2..."
    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop enigma2
    else
        init 4
    fi
    sleep 2
}

start_enigma2() {
    echo "▶ Starting Enigma2..."
    if command -v systemctl >/dev/null 2>&1; then
        systemctl start enigma2
    else
        init 3
    fi
}

stop_softcams() {
    echo "⏹ Stopping Softcams..."
    killall oscam ncam gcam cccam 2>/dev/null
}

restart_softcam() {
    echo "▶ Restarting Softcam..."
    [ -x /usr/bin/oscam ] && /usr/bin/oscam -b 2>/dev/null
}

install_plugin() {
    echo "================================="
    echo " Installing $PLUGIN"
    echo "================================="

    stop_enigma2
    stop_softcams

    rm -rf "$TARGET"
    mkdir -p "$BASE_DIR" || exit 1
    cd "$BASE_DIR" || exit 1

    # --- Ensure git exists ---
    if ! command -v git >/dev/null 2>&1; then
        echo "📦 Installing git..."
        opkg update && opkg install git || {
            echo "❌ Git install failed"
            start_enigma2
            exit 1
        }
    fi

    echo "⬇ Downloading from GitHub..."
    git clone "$REPO" "$PLUGIN" || {
        echo "❌ Git clone failed"
        start_enigma2
        exit 1
    }

    # --- Permissions & cleanup ---
    chmod -R 755 "$TARGET"
    find "$TARGET" -name "*.pyc" -delete

    # --- Python syntax check ---
    if $PYTHON -m py_compile "$TARGET/plugin.py" 2>/dev/null; then
        echo "✔ plugin.py OK"
    else
        echo "⚠ plugin.py check failed"
    fi

    if [ -f "$TARGET/lang.py" ]; then
        $PYTHON -m py_compile "$TARGET/lang.py" 2>/dev/null && echo "✔ lang.py OK"
    fi

    sync
    start_enigma2
    sleep 5
    restart_softcam

    echo "================================="
    echo " ✅ $PLUGIN Installed Successfully"
    echo "================================="
}

# --- Auto Install (No Menu) ---
install_plugin
exit 0
