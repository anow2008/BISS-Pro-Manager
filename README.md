# BissPro 🔑  
**Professional BISS Key Manager for Enigma2**

BissPro is an advanced Enigma2 plugin designed to manage BISS keys easily and safely.  
It supports manual and automatic key handling, online updates, backups, and multilingual UI.

---

## ✨ Features

- ➕ Add BISS keys manually
- ✏️ Edit existing keys
- 🗑 Delete keys with confirmation
- 🤖 Auto-Add BISS keys from online database (GitHub)
- 🔄 Update `SoftCam.Key` online
- ♻️ Smart or Full softcam restart
- 💾 Automatic backup before any modification
- ⚙️ Advanced settings menu
- 🌍 Multi-language support (English / Arabic)
- 🧪 Dry-Run mode (test without writing)
- 🚀 Cache system for faster auto search

---

## 📦 Supported Softcams

- OSCam
- NCam
- GCam
- RevCam
- ViCard

---

## 📁 Installation (Online – One Command)

```sh
wget -qO - https://raw.githubusercontent.com/anow2008/BissPro/main/install.sh | sh

---

⚙️ Settings Overview

Restart Mode (Smart / Full)

Match by SID

Match by Channel Name

Ignore HD / FHD / 4K

Normalize Channel Name

Cache Time

Backup Enable / Backup Keep

Confirm Delete

Language (EN / AR)

Debug Mode

Dry Run Mode

🧠 How Auto-Add Works

The plugin automatically:

Detects current channel SID and name

Compares with online BISS database

Matches by SID or Name + Frequency

Adds the key safely to SoftCam.Key

Restarts the active softcam

🌍 Language Support

English 🇬🇧

Arabic 🇪🇬

Language can be changed from Settings
(GUI restart may be required)

🛡 Backup System

Automatic backup before edit/add/delete

Configurable number of backups

Stored in the same directory as SoftCam.Key

⚠️ Disclaimer

This plugin is provided for educational and personal use only.
The author is not responsible for any misuse.

## Uninstall
wget -qO - https://raw.githubusercontent.com/anow2008/BissPro/main/uninstall.sh | sh

or

rm -rf /usr/lib/enigma2/python/Plugins/Extensions/BissPro && killall enigma2


👨‍💻 Author

anow2008

📅 Version Info

Version: 1.1

Build: 2026-01-27


