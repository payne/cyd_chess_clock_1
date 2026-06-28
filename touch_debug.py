# touch_debug.py  —  raw XPT2046 diagnostic, no GUI framework needed.
#
# Run:  mpremote run touch_debug.py
#
# Tap screen areas in order:
#   1. Far LEFT centre
#   2. Far RIGHT centre
#   3. TOP centre
#   4. BOTTOM centre
#
# Output shows raw ADC values and two candidate col/row mappings.
# Share the output so the correct tpad.init() can be determined.

from machine import SPI, Pin, freq
import time

freq(240_000_000)

_spi = SPI(2, 2_500_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
_cs  = Pin(33, Pin.OUT, value=1)

def _raw(chan):
    buf = bytearray([0x83 | (chan << 4), 0, 0])
    r   = bytearray(3)
    _cs(0)
    _spi.write_readinto(buf, r)
    _cs(1)
    return (int.from_bytes(r, "big") >> 3) & 0xFFF

W, H = 320, 240

print("Tap the screen — raw values and two candidate mappings are printed.")
print(f"{'rawX':>6} {'rawY':>6}  |  {'col(A)':>6} {'row(A)':>6}  |  {'col(B)':>6} {'row(B)':>6}")
print(f"{'':>6} {'':>6}  |  {'no-trans':>13}  |  {'trans':>13}")
print("-" * 60)

prev = False
while True:
    z = _raw(3)
    touched = z > 200
    if touched and not prev:
        rx = _raw(5)
        ry = _raw(1)
        # Mapping A: no transposition (raw_X → col)
        col_a = rx * W // 4095
        row_a = ry * H // 4095
        # Mapping B: transposed (raw_Y → col)
        col_b = ry * W // 4095
        row_b = rx * H // 4095
        print(f"{rx:>6} {ry:>6}  |  {col_a:>6} {row_a:>6}  |  {col_b:>6} {row_b:>6}")
    prev = touched
    time.sleep_ms(50)
