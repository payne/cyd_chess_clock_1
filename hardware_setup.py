# hardware_setup.py
"""
CYD (ESP32-2432S028R) hardware configuration for micropython-touch.

Install micropython-touch first:
  mpremote mip install github:peterhinch/micropython-touch

Copy this file and chess_clock.py to the device root, then:
  mpremote run chess_clock.py

Pin mapping (most common CYD variant):
  Display ILI9341  SPI1/HSPI  CLK=14  MOSI=13  MISO=12
                              CS=15   DC=2     RST=0    BL=21
  Touch   XPT2046  SPI2/VSPI  CLK=25  MOSI=32  MISO=39
                              CS=33   IRQ=36

If colours look wrong (red/blue swapped) set bgr=True in the SSD constructor.
Run the calibration utility once and paste the result into touch.set_cal().
"""
from machine import SPI, Pin, freq

freq(240_000_000)   # 240 MHz for snappy UI response

# ── ILI9341 display (HSPI) ───────────────────────────────────────────────────
from drivers.ili9341.ili9341_16bit import ILI9341 as SSD

_dspi = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
ssd   = SSD(_dspi,
            dc=Pin(2,  Pin.OUT, value=0),
            cs=Pin(15, Pin.OUT, value=1),
            rst=Pin(0, Pin.OUT, value=1),
            height=240, width=320,
            usd=False,   # set True if display is mounted upside-down
            bgr=False)   # set True if red and blue are swapped

Pin(21, Pin.OUT, value=1)   # backlight ON

# ── XPT2046 touch (VSPI) ─────────────────────────────────────────────────────
from drivers.xpt2046.touch import XPT2046

_tspi = SPI(2, baudrate=2_000_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
touch = XPT2046(_tspi,
                cs=Pin(33, Pin.OUT, value=1),
                irq=Pin(36, Pin.IN),
                width=320, height=240)
# Paste calibration values after running the calibration utility, e.g.:
#   touch.set_cal(xmin, ymin, xmax, ymax)

# ── Register with the GUI framework ──────────────────────────────────────────
from gui.core.tgui import Display
Display(ssd, touch)
