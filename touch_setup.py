# touch_setup.py — CYD (ESP32-2432S028R) hardware configuration
#
# MUST be named touch_setup.py: gui/core/colors.py does:
#   from touch_setup import SSD
#
# Pin map:
#   Display ILI9341  SPI1/HSPI  CLK=14  MOSI=13  MISO=12
#                               CS=15   DC=2     BL=21
#                               RST — not connected to any GPIO on the CYD
#   Touch   XPT2046  SPI2/VSPI  CLK=25  MOSI=32  MISO=39
#                               CS=33   IRQ=36

from machine import SPI, Pin, freq
import gc

freq(240_000_000)

# ── ILI9341 display (HSPI) ───────────────────────────────────────────────────
from drivers.ili93xx.ili9341 import ILI9341 as SSD

# RST is pulled to 3V3 via a resistor on the CYD and is not connected to an
# ESP32 GPIO.  The driver calls rst(0)/rst(1) unconditionally, so we pass a
# no-op callable; the SWRESET command (0x01) that follows does the real work.
class _NoPin:
    def __call__(self, v): pass

pcs = Pin(15, Pin.OUT, value=1)
pdc = Pin(2,  Pin.OUT, value=0)
spi = SPI(1, 40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))

gc.collect()
ssd = SSD(spi, cs=pcs, dc=pdc, rst=_NoPin(),
          height=240, width=320, usd=False, bgr=False)

Pin(21, Pin.OUT, value=1)   # backlight ON

# ── XPT2046 touch (VSPI) ─────────────────────────────────────────────────────
# The XPT2046 constructor signature is XPT2046(spi, cs_pin, ssd)
# ssd must be created first so the driver can read its dimensions.
from touch.xpt2046 import XPT2046

tspi = SPI(2, 2_500_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
tpad = XPT2046(tspi, Pin(33, Pin.OUT, value=1), ssd)
# Correct the default axis mapping: ABCTouch defaults to (ssd.height, ssd.width)
# which caps col at 240 instead of 320, making the right half unreachable.
# trans/rr/rc may need adjusting; run touch/setup.py to calibrate precisely.
# Axes on the CYD are transposed and both reflected vs the ILI9341 landscape frame:
#   rawX ≈ constant for left/right taps → rawX is the vertical (row) axis
#   rawY ≈ varies for left/right taps  → rawY is the horizontal (col) axis
#   Large rawY = left edge, small rawY = right edge  → rc=True (col reflect)
#   Large rawX = top edge, small rawX = bottom edge  → rr=True (row reflect)
tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)

# ── Register with GUI framework ───────────────────────────────────────────────
from gui.core.tgui import Display
Display(ssd, tpad)
