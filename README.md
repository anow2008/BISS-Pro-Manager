BISS Pro 
## تركيب البلجن على الرسيفر


✅ أمر واحد تثبيت بـ wget
wget -qO- https://raw.githubusercontent.com/anow2008/BissPor/main/install.sh | sh


### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/BissPor.git && \
chmod -R 755 BissPor && \
killall -9 enigma2 && enigma2 &

