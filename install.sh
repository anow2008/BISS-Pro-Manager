#!/bin/sh
TARGET="/usr/lib/enigma2/python/Plugins/Extensions/BissPor"
cd /usr/lib/enigma2/python/Plugins/Extensions/ || exit 1
rm -rf BissPor
git clone https://github.com/anow2008/BissPor.git
chmod -R 755 BissPor
chmod 755 BissPor/plugin.py
killall enigma2
