# BISS Pro Manager

## وصف البلجن
BISS Pro Manager 
## تركيب البلجن على الرسيفر

### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/BissPor.git && \
chmod -R 755 enigma2-plugin-extensions-bisspro && \
killall -9 enigma2 && enigma2 &
