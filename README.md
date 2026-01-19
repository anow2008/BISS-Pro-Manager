BISS Pro 
## تركيب البلجن على الرسيفر


✅ أمر واحد تثبيت 
wget -qO- https://raw.githubusercontent.com/anow2008/BissPor/main/install.sh | sh

امر الحذف للبلجن 

killall oscam ncam enigma2 2>/dev/null; rm -rf /usr/lib/enigma2/python/Plugins/Extensions/BissPor /var/keys/SoftCam.Key.bak /media/usb/SoftCam.Key; enigma2 &



### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/BissPor.git && \
chmod -R 755 BissPor && \
killall -9 enigma2 && enigma2 &

