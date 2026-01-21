#!/bin/sh

PLUGIN="BissPro"
BASE_DIR="/usr/lib/enigma2/python/Plugins/Extensions"
TARGET="$BASE_DIR/$PLUGIN"
REPO="https://github.com/anow2008/BissPro.git"
SHORTCUT_PATH="/usr/bin/bisspro"

# --- Detect Python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    PYTHON=python
fi

# --- Functions ---
stop_enigma2() {
    echo "Stopping Enigma2..."
    init 4
    sleep 2
}

start_enigma2() {
    echo "Starting Enigma2..."
    init 3
}

stop_softcams() {
    echo "Stopping Softcams..."
    killall -9 oscam ncam gcam cccam 2>/dev/null
}

restart_softcams() {
    echo "Restarting Softcams..."
    [ -x /usr/bin/oscam ] && /usr/bin/oscam -b 2>/dev/null
    [ -x /usr/bin/ncam ] && /usr/bin/ncam -b 2>/dev/null
}

install_plugin() {
    echo "▶ Installing $PLUGIN..."

    stop_enigma2
    stop_softcams

    rm -rf "$TARGET"
    cd "$BASE_DIR" || {
        echo "❌ Failed to access $BASE_DIR"
        start_enigma2
        exit 1
    }

    # --- Ensure git exists ---
    if ! command -v git >/dev/null 2>&1; then
        echo "Installing git..."
        opkg update && opkg install git || {
            echo "❌ Failed to install git. Please install git manually."
            start_enigma2
            exit 1
        }
    fi

    echo "Downloading from GitHub..."
    git clone "$REPO" "$PLUGIN" || {
        echo "❌ Git clone failed. Check your network."
        start_enigma2
        exit 1
    }

    # --- Set permissions & clean pyc ---
    chmod -R 755 "$TARGET"
    find "$TARGET" -name "*.pyc" -delete

    # --- Python syntax check ---
    if $PYTHON -m py_compile "$TARGET/plugin.py" 2>/dev/null; then
        echo "✔ Python syntax OK"
    else
        echo "⚠ Python check skipped or failed (check manually)"
    fi

    # --- Create shortcut safely ---
    SCRIPT_PATH="$(readlink -f "$0")"
    if [ -f "$SCRIPT_PATH" ]; then
        cp "$SCRIPT_PATH" "$SHORTCUT_PATH" 2>/dev/null
        chmod 755 "$SHORTCUT_PATH" 2>/dev/null
    fi

    sync
    start_enigma2
    sleep 5
    restart_softcams

    echo "=========================================="
    echo " ✅ $PLUGIN Installed Successfully"
    echo "=========================================="
}

uninstall_plugin() {
    echo "▶ Uninstalling $PLUGIN..."

    stop_enigma2
    stop_softcams

    rm -rf "$TARGET"
    rm -f "$SHORTCUT_PATH"

    sync
    start_enigma2
    echo "🗑 $PLUGIN Removed Successfully"
}

# --- Main Menu ---
clear
echo "==============================="
echo "    BissPro Plugin Manager"
echo "==============================="
echo "1) Install / Update"
echo "2) Uninstall"
echo "3) Exit"
echo "==============================="
printf "Please enter your choice [1-3]: "
read -r OPT

case "$OPT" in
    1) install_plugin ;;
    2) uninstall_plugin ;;
    3) echo "Exiting..."; exit 0 ;;
    *) echo "Invalid option. Please run the script again."; exit 1 ;;
esac
