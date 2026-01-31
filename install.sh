#!/bin/sh
# ==========================================
#  BissPro Online Installer (No Git)
#  Author : anow2008
# ==========================================

PLUGIN="BissPro"
BASE_DIR="/usr/lib/enigma2/python/Plugins/Extensions"
TARGET="$BASE_DIR/$PLUGIN"
ZIP_URL="https://github.com/anow2008/BissPro/archive/refs/heads/main.tar.gz"
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
    stop_enigma2

    mkdir -p "$BASE_DIR"
    cd /tmp || exit 1
    rm -rf BissPro* main.tar.gz

    echo "⬇ Downloading plugin..." | tee -a $LOG
    if ! wget -O main.tar.gz "$ZIP_URL" >> $LOG 2>&1; then
        echo "❌ Download failed" | tee -a $LOG
        start_enigma2
        exit 1
    fi

    echo "📦 Extracting..." | tee -a $LOG
    tar -xzf main.tar.gz || {
        echo "❌ Extract failed" | tee -a $LOG
        start_enigma2
        exit 1
    }

    rm -rf "$TARGET"
    mv BissPro-main "$TARGET"

    chmod -R 755 "$TARGET"
    find "$TARGET" -name "*.pyc" -delete

    if [ -f "$TARGET/plugin.py" ]; then
        $PYTHON -m py_compile "$TARGET/plugin.py" 2>/dev/null
    else
        echo "❌ plugin.py missing" | tee -a $LOG
    fi

    sync
    start_enigma2

    echo "================================="
    echo " ✅ BissPro Installed Successfully"
    echo " 📄 Log: $LOG"
    echo "================================="
}

install_plugin
exit 0
