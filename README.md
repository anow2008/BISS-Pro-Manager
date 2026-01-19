BISS Pro 
## تركيب البلجن على الرسيفر


✅ أمر واحد تثبيت 
wget -qO- https://raw.githubusercontent.com/anow2008/BissPor/main/install.sh | sh

امر الحذف للبلجن 
PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/BissPor"; BACKUP_FILE="/var/keys/SoftCam.Key.bak"; USB_FILE="/media/usb/SoftCam.Key"; echo "This will remove BissPor plugin and related files"; read -p "Are you sure? [y/N]: " c; if [ "$c" = "y" ] || [ "$c" = "Y" ]; then killall oscam ncam enigma2 2>/dev/null; rm -rf "$PLUGIN_DIR"; [ -f "$BACKUP_FILE" ] && rm -f "$BACKUP_FILE"; [ -f "$USB_FILE" ] && rm -f "$USB_FILE"; echo "BissPor plugin removed successfully"; enigma2 &; else echo "Cancelled"; fi

### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/BissPor.git && \
chmod -R 755 BissPor && \
killall -9 enigma2 && enigma2 &

