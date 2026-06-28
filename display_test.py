# display_test.py
"""
Standalone CYD display diagnostic — no GUI framework required.

Run with:  mpremote run display_test.py

Works through three layers and prints a verdict at each step:
  1. Backlight         – GPIO 21
  2. SPI + ILI9341 driver (from micropython-touch)
  3. Raw SPI fallback  – sends ILI9341 init commands by hand if driver missing

After each colour fill the REPL shows what the screen should look like.
If nothing appears, the wiring or SPI bus is the problem.
If colours are swapped (red shows as blue), set bgr=True in hardware_setup.py.
"""

import time
from machine import SPI, Pin, freq

freq(240_000_000)
print("\n=== CYD display_test ===")

# ── 1. Backlight ──────────────────────────────────────────────────────────────
Pin(21, Pin.OUT, value=1)
print("[1] Backlight ON  (GPIO 21 HIGH) — screen should glow white/grey")
time.sleep_ms(500)

# ── 2. Try the micropython-touch ILI9341 driver ───────────────────────────────
_spi = SPI(1, baudrate=40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
_dc  = Pin(2,  Pin.OUT, value=0)
_cs  = Pin(15, Pin.OUT, value=1)

driver_ok = False
try:
    from drivers.ili9341.ili9341_16bit import ILI9341 as SSD
    ssd = SSD(_spi, dc=_dc, cs=_cs, rst=None, height=240, width=320)
    driver_ok = True
    print("[2] ILI9341 driver imported OK")
except ImportError as e:
    print(f"[2] Driver import FAILED: {e}")
    print("    Install with: mpremote mip install github:peterhinch/micropython-touch")
    print("    Falling back to raw SPI init …")
except Exception as e:
    print(f"[2] Driver init FAILED: {e}")

# ── 3. Raw SPI fallback ───────────────────────────────────────────────────────
if not driver_ok:
    print("[3] Sending raw ILI9341 init sequence …")

    def _cmd(c):
        _dc.value(0); _cs.value(0); _spi.write(bytes([c])); _cs.value(1)

    def _dat(*d):
        _dc.value(1); _cs.value(0); _spi.write(bytes(d)); _cs.value(1)

    _cmd(0x01); time.sleep_ms(150)   # software reset
    _cmd(0x11); time.sleep_ms(120)   # sleep out
    _cmd(0x3A); _dat(0x55)           # pixel format: 16 bpp
    _cmd(0x36); _dat(0x48)           # MADCTL: landscape, RGB order
    _cmd(0x29); time.sleep_ms(25)    # display on

    # Fill entire screen via column/row address set + memory write
    def _fill(color565, w=320, h=240):
        hi, lo = color565 >> 8, color565 & 0xFF
        _cmd(0x2A); _dat(0,0, (w-1)>>8, (w-1)&0xFF)   # column
        _cmd(0x2B); _dat(0,0, (h-1)>>8, (h-1)&0xFF)   # row
        _cmd(0x2C)                                      # memory write
        row = bytes([hi, lo] * w)
        _dc.value(1); _cs.value(0)
        for _ in range(h):
            _spi.write(row)
        _cs.value(1)

    print("[3] Raw init done — filling screen RED")
    _fill(0xF800); time.sleep(2)
    print("    Filling GREEN")
    _fill(0x07E0); time.sleep(2)
    print("    Filling BLUE")
    _fill(0x001F); time.sleep(2)
    print("[3] Done.  If nothing appeared, check SPI wiring.")
    print("    If red/blue were swapped, change MADCTL byte 0x48 → 0x08")

# ── 4. Driver-based colour test ───────────────────────────────────────────────
if driver_ok:
    print("[4] Filling RED  (0xF800) …")
    ssd.fill(0xF800); ssd.show(); time.sleep(2)

    print("    Filling GREEN (0x07E0) …")
    ssd.fill(0x07E0); ssd.show(); time.sleep(2)

    print("    Filling BLUE  (0x001F) …")
    ssd.fill(0x001F); ssd.show(); time.sleep(2)

    print("    Filling WHITE (0xFFFF) …")
    ssd.fill(0xFFFF); ssd.show(); time.sleep(1)

    print("[4] Driver colour test done.")
    print("    Screen is now WHITE.")
    print("    If colours were wrong, set bgr=True in hardware_setup.py.")

print("\n=== display_test complete ===")
