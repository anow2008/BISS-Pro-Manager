# BISS Pro Manager

## وصف البلجن
BISS Pro Manager هو بلجن احترافي لإدارة شفرات BISS / BISS-E على رسيفرات Enigma2 (VU+ / OpenATV 7.6).  
يدعم: إضافة، حذف، عرض الشفرات، استيراد من USB، النسخ الاحتياطي، تشفير AES، ودعم skin خارجي.

## الميزات
- ✅ إضافة / حذف / عرض شفرات BISS و BISS-E
- ✅ استيراد SoftCam.Key من USB
- ✅ نسخ احتياطي و استرجاع
- ✅ تشفير AES لمزيد من الأمان
- ✅ دعم skin.xml لفصل التصميم عن الكود
- ✅ Debug log لتتبع الأخطاء
- ✅ Auto SID + اسم القناة
- ✅ إعادة تشغيل Oscam مباشرة من البلجن
- ✅ ترجمة عربي + إنجليزي

---

## تركيب البلجن على الرسيفر

### 1️⃣ تنزيل البلجن من GitHub وتنصيبه تلقائيًا

انسخ السطر التالي في Terminal أو SSH على الرسيفر:

```bash
cd /usr/lib/enigma2/python/Plugins/Extensions/ && \
git clone https://github.com/anow2008/enigma2-plugin-extensions-bisspro.git && \
chmod -R 755 enigma2-plugin-extensions-bisspro && \
killall -9 enigma2 && enigma2 &
