#!/usr/bin/env bash
# install_drivers.sh
# Fetches the ILI9341 display driver (from micropython-nano-gui) and the
# XPT2046 touch driver (from micropython-touch) and installs them onto the
# device at the paths expected by hardware_setup.py.
#
# Usage:  bash install_drivers.sh

set -e

ILI_URL="https://raw.githubusercontent.com/peterhinch/micropython-nano-gui/master/drivers/ili9341/ili9341_16bit.py"
XPT_URL="https://raw.githubusercontent.com/peterhinch/micropython-touch/master/drivers/xpt2046/touch.py"

echo "=== Step 1: create driver directories on device ==="
mpremote exec "
import os
for d in ('drivers','drivers/ili9341','drivers/xpt2046'):
    try:    os.mkdir(d)
    except: pass
for f in ('drivers/__init__.py','drivers/ili9341/__init__.py','drivers/xpt2046/__init__.py'):
    open(f,'w').close()
print('dirs OK')
"

echo "=== Step 2: download drivers ==="
curl -fsSL -o /tmp/ili9341_16bit.py "$ILI_URL"
echo "  ili9341_16bit.py  OK"
curl -fsSL -o /tmp/xpt2046_touch.py "$XPT_URL"
echo "  xpt2046/touch.py  OK"

echo "=== Step 3: copy to device ==="
mpremote cp /tmp/ili9341_16bit.py  :drivers/ili9341/ili9341_16bit.py
mpremote cp /tmp/xpt2046_touch.py  :drivers/xpt2046/touch.py

echo ""
echo "=== Done — run the clock with: ==="
echo "    mpremote run chess_clock.py"
