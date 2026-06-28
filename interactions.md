# Session interactions — 2026-06-27

## Request 1 — Chess clock for CYD

**User:** Write a chess clock for the Cheap Yellow Display (CYD) using
[micropython-touch](https://github.com/peterhinch/micropython-touch).

Two players, each with a button and a countdown gauge.  Player A taps their
button → their gauge starts counting down from 30 minutes.  If Player B's gauge
was running it stops.  Player B taps their button → B's gauge starts, A's
pauses.  One-second display resolution.

**Assistant created:** `hardware_setup.py` and `chess_clock.py`

### hardware_setup.py

Configures the ESP32-2432S028R (CYD) for micropython-touch:

| Peripheral | Bus | Pins |
|------------|-----|------|
| ILI9341 display | SPI1 / HSPI | CLK=14 MOSI=13 MISO=12 CS=15 DC=2 RST=0 BL=21 |
| XPT2046 touch | SPI2 / VSPI | CLK=25 MOSI=32 MISO=39 CS=33 IRQ=36 |

### chess_clock.py

Screen layout (320 × 240, landscape):

```
┌──────────┬─┬──────────┐
│ PLAYER A │R│ PLAYER B │  headers + RST button
│  MM:SS   │S│  MM:SS   │  large time labels
│ ══gauge══│T│ ══gauge══│  horizontal gauge bars
│          │ │          │
│  TAP A   │ │  TAP B   │  full-width tap buttons
└──────────┴─┴──────────┘
```

---

## Request 2 — Auto-start on reset + session log

**User:** Create `main.py` so the chess clock starts automatically on board
reset.  Record everything from this session in `interactions.md`.

**Assistant created:** `main.py` (one line: `import chess_clock`) and
`interactions.md`.  MicroPython executes `main.py` automatically after
`boot.py` on every power-on/reset.

---

## Bug 1 — Blank screen

**User:** The screen on the CYD is blank.

**Root cause:** `rst=Pin(0, Pin.OUT, value=1)` — GPIO 0 is the ESP32
boot-strapping pin.  Driving it as an output can hold the ILI9341 in
perpetual hardware reset.

**Fix:** Removed `rst=Pin(0,…)`.  On the CYD the ILI9341 RST pin is pulled
to 3V3 via a resistor and is not connected to any ESP32 GPIO; the driver
sends a software SWRESET (0x01) instead.

**Assistant also created:** `display_test.py` — a standalone diagnostic that
tests backlight, ILI9341 driver init, and raw SPI, printing a verdict at each
step.

---

## Bug 2 — ImportError: no module named 'drivers.ili9341'

**User output:**
```
ImportError: no module named 'drivers.ili9341'
```

**Root cause:** `mpremote mip install github:peterhinch/micropython-touch`
installs the GUI framework (`gui/`) but NOT the display drivers. The original
code also used wrong import paths guessed without checking the repo.

**Discovered (via GitHub API):**

| What | Actual path |
|------|-------------|
| ILI9341 driver | `drivers/ili93xx/ili9341.py` (not `drivers/ili9341/ili9341_16bit.py`) |
| XPT2046 driver | `touch/xpt2046.py` (not `drivers/xpt2046/touch.py`) |
| Setup file name | **Must be `touch_setup.py`** — `gui/core/colors.py` hardcodes `from touch_setup import SSD` |

**Additional bugs found in the original code:**

1. File named `hardware_setup.py` → must be `touch_setup.py`
2. `from drivers.ili9341.ili9341_16bit import ILI9341` → `from drivers.ili93xx.ili9341 import ILI9341`
3. `from drivers.xpt2046.touch import XPT2046` → `from touch.xpt2046 import XPT2046`
4. `XPT2046(tspi, cs, irq, w, h)` → real signature is `XPT2046(spi, cs_pin, ssd)` — needs the display object
5. `rst=None` crashes — driver calls `rst(0)` unconditionally → use `_NoPin()` no-op callable
6. `asyncio.run(Screen.main())` — `Screen.main()` doesn't exist; `Screen.change()` starts the event loop internally
7. `create_color(r, g, b)` → ILI9341 uses a 16-entry LUT; signature is `create_color(idx, r, g, b)`
8. `Writer(ssd, font)` → framework uses `CWriter(ssd, font, fgcolor, bgcolor)`

**mip package.json contents** (what was actually installed):
- `drivers/ili93xx/ili9341.py` — from micropython-nano-gui
- `drivers/boolpalette.py` — from micropython-nano-gui
- `gui/core/{tgui,writer,colors}.py`
- `gui/fonts/{arial10,font10}.py`
- `gui/widgets/{__init__,buttons,label}.py`
- `touch/{touch,xpt2046,check,setup}.py`

Missing fonts downloaded separately: `freesans20.py`, `arial35.py`

**Assistant created:** `touch_setup.py` (renamed and rewritten),
`install_all.sh` (downloads and deploys the complete file set).

---

## Bug 3 — Flicker and cannot click B

**User:** Click A starts the timer but there is flicker and cannot click B.

### Flicker

**Root cause:** `_draw_bars()` called `ssd.show()` explicitly. But
`Screen.auto_refresh()` is already running as an asyncio task and calls
`ssd.show()` on every cycle (~30 fps). Two concurrent callers on the SPI bus
caused visible tearing.

**Fix:** Removed all explicit `ssd.show()` calls from `chess_clock.py`.
Bars are written to the FrameBuffer; `auto_refresh()` flushes them.

### Cannot click B

**Root cause:** `ABCTouch.__init__` seeds with
`self.init(ssd.height, ssd.width, …)` = `(240, 320, …)`, capping the column
coordinate at 240 px.  The right 80 px of the screen (col 240–319) were
unreachable.

**Fix attempt 1:** `tpad.init(320, 240, 0, 0, 4095, 4095, False, False, False)`

Result: flicker gone, B still not clickable.

---

## Bug 4 — Touch axis investigation

**Assistant created:** `touch_debug.py` — prints raw XPT2046 ADC values and
two candidate col/row mappings (no-trans and trans) for each tap.

**User ran the debug script and tapped four screen areas:**

```
  rawX   rawY  |  col(A) row(A)  |  col(B) row(B)
               |       no-trans  |          trans
------------------------------------------------------------
  1970   3281  |     153    192  |     256    115   ← far LEFT
  1857    668  |     145     39  |      52    108   ← far RIGHT
  3487   2002  |     272    117  |     156    204   ← TOP centre
   747   1864  |      58    109  |     145     43   ← BOTTOM centre
```

**Analysis:**

- rawX for far-left (1970) and far-right (1857) are nearly identical →
  rawX is **not** the horizontal axis.
- rawY swings from 3281 (left) to 668 (right) → rawY is the horizontal axis.
- Large rawX = top, small rawX = bottom → rawX is vertical, reflected.
- Large rawY = left, small rawY = right → rawY is horizontal, reflected.

Correct mapping: `trans=True` (swap axes) + `rr=True` (reflect row) + `rc=True` (reflect col).

With `tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)`:

| Tap | rawX | rawY | col | row |
|-----|------|------|-----|-----|
| Far left | 1970 | 3281 | 64 | 125 |
| Far right | 1857 | 668 | 268 | 131 |
| Top | 3487 | 2002 | 164 | 36 |
| Bottom | 747 | 1864 | 174 | 196 |

All four quadrants correctly mapped. ✓

**Fix:** Changed `tpad.init` line in `touch_setup.py` to:
```python
tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)
```

---

## Final file list

| File | Purpose |
|------|---------|
| `touch_setup.py` | Hardware init (display + touch); **must** be this name |
| `chess_clock.py` | Chess clock application |
| `main.py` | Auto-start on boot (`import chess_clock`) |
| `display_test.py` | Standalone display diagnostic |
| `touch_debug.py` | Standalone touch diagnostic |
| `install_all.sh` | Download and deploy all framework files |
| `freesans20.py` | Font (20pt) — copy to `gui/fonts/` on device |
| `arial35.py` | Font (35pt) — copy to `gui/fonts/` on device |

## Deployment checklist

```bash
bash install_all.sh          # first time only

# After any code change:
mpremote cp touch_setup.py  :touch_setup.py
mpremote cp chess_clock.py  :chess_clock.py
mpremote run chess_clock.py  # test before committing to main.py

mpremote cp main.py :main.py
mpremote reset               # verify auto-start
```
