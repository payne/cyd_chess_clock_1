#!/usr/bin/env bash
# install_all.sh — download every required file and copy it to the CYD.
# Run from ~/cc with the board connected via USB.
set -e

TOUCH="peterhinch/micropython-touch"
NANO="peterhinch/micropython-nano-gui"
API="https://api.github.com/repos"
PKG="/tmp/cyd_pkg"

# Download one file from GitHub via the contents API (works where raw URLs 404)
fetch() {          # fetch <repo> <repo-path> <local-dest>
    local repo=$1 path=$2 dest=$3
    mkdir -p "$(dirname "$dest")"
    curl -s "$API/$repo/contents/$path" \
        | python3 -c "import sys,json,base64; open('$dest','wb').write(base64.b64decode(json.load(sys.stdin)['content']))"
    echo "  $dest"
}

echo "=== Downloading files ==="
rm -rf "$PKG" && mkdir -p "$PKG"

# Display driver (from micropython-nano-gui)
fetch $NANO drivers/ili93xx/ili9341.py    $PKG/drivers/ili93xx/ili9341.py
fetch $NANO drivers/boolpalette.py        $PKG/drivers/boolpalette.py

# GUI core
fetch $TOUCH gui/core/tgui.py            $PKG/gui/core/tgui.py
fetch $TOUCH gui/core/writer.py          $PKG/gui/core/writer.py
fetch $TOUCH gui/core/colors.py          $PKG/gui/core/colors.py

# Fonts
fetch $TOUCH gui/fonts/arial10.py        $PKG/gui/fonts/arial10.py
fetch $TOUCH gui/fonts/font10.py         $PKG/gui/fonts/font10.py
fetch $TOUCH gui/fonts/freesans20.py     $PKG/gui/fonts/freesans20.py
fetch $TOUCH gui/fonts/arial35.py        $PKG/gui/fonts/arial35.py

# Widgets
fetch $TOUCH gui/widgets/__init__.py     $PKG/gui/widgets/__init__.py
fetch $TOUCH gui/widgets/buttons.py      $PKG/gui/widgets/buttons.py
fetch $TOUCH gui/widgets/label.py        $PKG/gui/widgets/label.py

# Touch drivers
fetch $TOUCH touch/touch.py              $PKG/touch/touch.py
fetch $TOUCH touch/xpt2046.py            $PKG/touch/xpt2046.py

echo ""
echo "=== Creating directories on device ==="
mpremote exec "
import os
dirs = [
    'drivers', 'drivers/ili93xx',
    'gui', 'gui/core', 'gui/fonts', 'gui/widgets',
    'touch',
]
for d in dirs:
    try:    os.mkdir(d)
    except: pass
print('dirs OK')
"

echo ""
echo "=== Copying files to device ==="
mpremote cp $PKG/drivers/boolpalette.py        :drivers/boolpalette.py
mpremote cp $PKG/drivers/ili93xx/ili9341.py    :drivers/ili93xx/ili9341.py

mpremote cp $PKG/gui/core/tgui.py             :gui/core/tgui.py
mpremote cp $PKG/gui/core/writer.py           :gui/core/writer.py
mpremote cp $PKG/gui/core/colors.py           :gui/core/colors.py

mpremote cp $PKG/gui/fonts/arial10.py         :gui/fonts/arial10.py
mpremote cp $PKG/gui/fonts/font10.py          :gui/fonts/font10.py
mpremote cp $PKG/gui/fonts/freesans20.py      :gui/fonts/freesans20.py
mpremote cp $PKG/gui/fonts/arial35.py         :gui/fonts/arial35.py

mpremote cp $PKG/gui/widgets/__init__.py       :gui/widgets/__init__.py
mpremote cp $PKG/gui/widgets/buttons.py        :gui/widgets/buttons.py
mpremote cp $PKG/gui/widgets/label.py          :gui/widgets/label.py

mpremote cp $PKG/touch/touch.py               :touch/touch.py
mpremote cp $PKG/touch/xpt2046.py             :touch/xpt2046.py

# App files
mpremote cp touch_setup.py  :touch_setup.py
mpremote cp chess_clock.py  :chess_clock.py
mpremote cp main.py         :main.py

echo ""
echo "=== Done — running chess_clock.py ==="
mpremote run chess_clock.py
