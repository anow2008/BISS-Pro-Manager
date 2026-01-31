#!/bin/sh
# ==========================================
#  BissPro Online Installer (Improved)
#  Author : anow2008
# ==========================================

PLUGIN="BissPro"
BASE_DIR="/usr/lib/enigma2/python/Plugins/Extensions"
TARGET="$BASE_DIR/$PLUGIN"
REPO="https://github.com/anow2008/BissPro.git"
LOG="/tmp/bisspro_install.log"

echo "🔧 BissPro Installer Started" | tee $LOG

# --- Detect Python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    PYTHON=python
fi

stop_enigma2() {
    echo "⏹ Stopping Enigma2..." | tee -a $LOG
    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop enigma2
    else
        init 4
    fi
    sleep 2
}

start_enigma2() {
    echo "▶ Starting Enigma2..." | tee -a $LOG
    if command -v systemctl >/dev/null 2>&1; then
        systemctl start enigma2
    else
        init 3
    fi
}

install_plugin() {
    echo "=================================" | tee -a $LOG
    echo " Installing $PLUGIN" | tee -a $LOG
    echo "=================================" | tee -a $LOG

    # --- Ensure git exists ---
    if ! command -v git >/dev/null 2>&1; then
        echo "📦 Installing git..." | tee -a $LOG
        opkg update && opkg install git || {
            echo "❌ Git install failed" | tee -a $LOG
            exit 1
        }
    fi

    stop_enigma2

    rm -rf "$TARGET"
    mkdir -p "$BASE_DIR" || exit 1
    cd "$BASE_DIR" || exit 1

    echo "⬇ Downloading from GitHub..." | tee -a $LOG
    if ! git clone "$REPO" "$PLUGIN" >> $LOG 2>&1; then
        echo "❌ Git clone failed" | tee -a $LOG
        start_enigma2
        exit 1
    fi

    # --- Verify install ---
    if [ ! -f "$TARGET/plugin.py" ]; then
        echo "❌ plugin.py not found! Install failed" | tee -a $LOG
        start_enigma2
        exit 1
    fi

    chmod -R 755 "$TARGET"
    find "$TARGET" -name "*.pyc" -delete

    $PYTHON -m py_compile "$TARGET/plugin.py" 2>/dev/null && \
        echo "✔ plugin.py OK" | tee -a $LOG

    sync
    start_enigma2

    echo "=================================" | tee -a $LOG
    echo " ✅ $PLUGIN Installed Successfully" | tee -a $LOG
    echo " 📄 Log: $LOG"
    echo "================================="
}

install_plugin
exit 0
