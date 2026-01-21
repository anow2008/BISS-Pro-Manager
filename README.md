BISS Pro 
## تركيب البلجن على الرسيفر


✅ أمر واحد تثبيت 
wget -qO- https://raw.githubusercontent.com/anow2008/BissPro/main/install.sh | sh

امر الحذف للبلجن 

init 4
killall oscam ncam 2>/dev/null
rm -rf /usr/lib/enigma2/python/Plugins/Extensions/BissPro
rm -rf /var/keys/SoftCam.Key.bak /media/usb/SoftCam.Key
init 3




### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/BissPro.git && \
chmod -R 755 BissPro && \
killall -9 enigma2 && enigma2 &

