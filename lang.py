# -*- coding: utf-8 -*-

def _(key, lang="en"):
    LANG = {

        # ================= English =================
        "en": {
            # Main Menu
            "ADD_KEY": "Add Key",
            "EDIT_KEY": "Edit Key",
            "DELETE_KEY": "Delete Key",
            "UPDATE_SOFTCAM": "Update SoftCam",
            "AUTO_ADD": "Auto Add",
            "SETTINGS": "Settings",

            # Status / Messages
            "KEY_SAVED": "Key Saved!",
            "KEY_DELETED": "Deleted Successfully",
            "KEY_EXISTS": "Key already exists",
            "NO_KEY_FOUND": "No Key found in Database",
            "SUCCESS_ADD": "Success: Key Added!",
            "SOFTCAM_UPDATED": "SoftCam.Key Updated!",
            "DOWNLOAD_FAILED": "Download Failed",
            "SEARCHING": "Searching GitHub...",
            "UPDATING": "Updating SoftCam...",
            "ERROR": "Error",

            # Confirmations
            "CONFIRM_DELETE": "Delete this key?",
            "RESTART_GUI": "Restart GUI to apply language?",

            # Settings
            "RESTART_MODE": "Restart Mode",
            "MATCH_SID": "Match by SID",
            "MATCH_NAME": "Match by Name",
            "IGNORE_HD": "Ignore HD/FHD/4K",
            "NORMALIZE_NAME": "Normalize Name",
            "CACHE_TIME": "Cache Time",
            "BACKUP_ENABLE": "Backup Enable",
            "BACKUP_KEEP": "Backup Keep",
            "CONFIRM_DELETE_OPT": "Confirm Delete",
            "LANGUAGE": "Language",
            "DEBUG": "Debug Log",
            "DRY_RUN": "Dry Run",

            # Misc
            "ABOUT": "About",
            "NO_KEYS_FOR_SID": "No keys found for this SID",
        },

        # ================= Arabic =================
        "ar": {
            # Main Menu
            "ADD_KEY": "إضافة مفتاح",
            "EDIT_KEY": "تعديل مفتاح",
            "DELETE_KEY": "حذف مفتاح",
            "UPDATE_SOFTCAM": "تحديث السوفتكام",
            "AUTO_ADD": "إضافة تلقائية",
            "SETTINGS": "الإعدادات",

            # Status / Messages
            "KEY_SAVED": "تم حفظ المفتاح",
            "KEY_DELETED": "تم الحذف بنجاح",
            "KEY_EXISTS": "المفتاح موجود بالفعل",
            "NO_KEY_FOUND": "لم يتم العثور على مفتاح",
            "SUCCESS_ADD": "تمت إضافة المفتاح بنجاح",
            "SOFTCAM_UPDATED": "تم تحديث ملف السوفتكام",
            "DOWNLOAD_FAILED": "فشل التحميل",
            "SEARCHING": "جاري البحث على GitHub...",
            "UPDATING": "جاري تحديث السوفتكام...",
            "ERROR": "حدث خطأ",

            # Confirmations
            "CONFIRM_DELETE": "هل تريد حذف هذا المفتاح؟",
            "RESTART_GUI": "أعد تشغيل الواجهة لتفعيل اللغة",

            # Settings
            "RESTART_MODE": "وضع إعادة التشغيل",
            "MATCH_SID": "مطابقة بالـ SID",
            "MATCH_NAME": "مطابقة بالاسم",
            "IGNORE_HD": "تجاهل HD / FHD / 4K",
            "NORMALIZE_NAME": "توحيد اسم القناة",
            "CACHE_TIME": "مدة الكاش",
            "BACKUP_ENABLE": "تفعيل النسخ الاحتياطي",
            "BACKUP_KEEP": "عدد النسخ الاحتياطية",
            "CONFIRM_DELETE_OPT": "تأكيد الحذف",
            "LANGUAGE": "اللغة",
            "DEBUG": "وضع التصحيح",
            "DRY_RUN": "وضع التجربة",

            # Misc
            "ABOUT": "حول البلجن",
            "NO_KEYS_FOR_SID": "لا توجد مفاتيح لهذا الـ SID",
        }
    }

    return LANG.get(lang, LANG["en"]).get(key, key)
