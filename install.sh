#!/bin/sh
cd /usr/lib/enigma2/python/Plugins/Extensions/ || exit 1
rm -rf BissPor
git clone https://github.com/anow2008/BissPor.git
chmod -R 755 BissPor
killall -9 enigma2
