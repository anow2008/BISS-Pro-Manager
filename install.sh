#!/bin/sh
TARGET="/usr/lib/enigma2/python/Plugins/Extensions/BissPro"
cd /usr/lib/enigma2/python/Plugins/Extensions/ || exit 1
rm -rf BissPro
git clone https://github.com/anow2008/BissPro.git
chmod -R 755 BissPro
chmod 755 BissPro/plugin.py
killall enigma2
