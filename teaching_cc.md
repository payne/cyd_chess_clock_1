# Implementing a GUI application on the CYD with micropython-touch

A programmer's reference for building touch GUI apps on the
**ESP32-2432S028R** ("Cheap Yellow Display") without an AI assistant.

---

## 1. Hardware overview

The CYD is an ESP32 devboard with an integrated 2.8″ 320×240 ILI9341 display
and XPT2046 resistive touchscreen.

### Pin map

| Signal | GPIO | Notes |
|--------|------|-------|
| Display CLK | 14 | HSPI / SPI1 |
| Display MOSI | 13 | |
| Display MISO | 12 | |
| Display CS | 15 | |
| Display DC | 2 | data/command select |
| Display RST | — | **not wired to any GPIO**; pulled to 3V3 via resistor |
| Backlight | 21 | HIGH = on |
| Touch CLK | 25 | VSPI / SPI2 — **separate bus from display** |
| Touch MOSI | 32 | |
| Touch MISO | 39 | input-only pin |
| Touch CS | 33 | |
| Touch IRQ | 36 | input-only; driver polls without interrupt |
| RGB LED R/G/B | 4/16/17 | active LOW |
| LDR | 34 | input-only |

**Critical:** GPIO 0 is the ESP32 boot-strapping pin. Never use it as a GPIO
output — it will interfere with boot and can hold the display in hardware reset.

---

## 2. Framework overview

[micropython-touch](https://github.com/peterhinch/micropython-touch) by Peter
Hinch is an async, touch-first GUI framework for MicroPython. Key facts:

- Built on top of **micropython-nano-gui** display drivers.
- Uses `asyncio` for the event loop; all user tasks must be `async`.
- Renders widgets into a FrameBuffer, then flushes to the display via
  `ssd.show()` in a background `auto_refresh` task.  **Never call
  `ssd.show()` yourself** — doing so causes tearing/flicker.
- Colors are 4-bit LUT indices (0–15), not RGB565 values.

### Install

```bash
mpremote mip install github:peterhinch/micropython-touch
```

This installs `gui/` and `touch/` trees plus `drivers/ili93xx/` and
`drivers/boolpalette.py`.  It does **not** install large fonts.

---

## 3. The mandatory `touch_setup.py`

The framework's `gui/core/colors.py` unconditionally imports:

```python
from touch_setup import SSD
```

Your hardware-init file **must** be named `touch_setup.py`.  It must define
`SSD` (the display driver class, not an instance) as a module-level name.

### Minimal `touch_setup.py` for the CYD

```python
from machine import SPI, Pin, freq
import gc

freq(240_000_000)

# ── Display ──────────────────────────────────────────────────────────────────
from drivers.ili93xx.ili9341 import ILI9341 as SSD

class _NoPin:
    """RST is not wired on the CYD; this no-op satisfies the driver."""
    def __call__(self, v): pass

spi = SPI(1, 40_000_000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
gc.collect()                          # free RAM before allocating framebuffer
ssd = SSD(spi,
          cs=Pin(15, Pin.OUT, value=1),
          dc=Pin(2,  Pin.OUT, value=0),
          rst=_NoPin(),
          height=240, width=320,
          usd=False,    # True = upside-down
          bgr=False)    # True = swap red and blue

Pin(21, Pin.OUT, value=1)             # backlight ON

# ── Touch ─────────────────────────────────────────────────────────────────────
from touch.xpt2046 import XPT2046

tspi = SPI(2, 2_500_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
tpad = XPT2046(tspi, Pin(33, Pin.OUT, value=1), ssd)  # ssd required

# Axis calibration for CYD in landscape mode (derived empirically):
tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)

# ── Register with framework ───────────────────────────────────────────────────
from gui.core.tgui import Display
Display(ssd, tpad)
```

### ILI9341 constructor signature

```python
ILI9341(spi, cs, dc, rst, height=240, width=320,
        usd=False, init_spi=False, mod=None, bgr=False)
```

`rst` must be callable (e.g. a `Pin` or the `_NoPin` stub above).
It is called as `rst(0)` and `rst(1)` — passing `None` crashes.

### XPT2046 constructor signature

```python
XPT2046(spi, cspin, ssd, *, alen=10)
```

The `ssd` argument is required — the driver reads `ssd.height` and
`ssd.width` to initialise its coordinate mapping.

---

## 4. Touch calibration

The XPT2046 reports 12-bit ADC values (0–4095) for two channels:
- **Channel 5** — one physical electrode direction (call it rawX)
- **Channel 1** — the other electrode direction (call it rawY)

These do **not** necessarily align with the display's column/row axes.
`tpad.init()` maps them:

```python
tpad.init(xpix, ypix, xmin, ymin, xmax, ymax, trans, rr, rc)
```

| Parameter | Meaning |
|-----------|---------|
| `xpix` | pixel span of the rawX axis before transposition |
| `ypix` | pixel span of the rawY axis before transposition |
| `xmin/xmax` | raw ADC values at the two rawX extremes |
| `ymin/ymax` | raw ADC values at the two rawY extremes |
| `trans` | swap the x and y axes |
| `rr` | reflect the row axis (flip top/bottom) |
| `rc` | reflect the col axis (flip left/right) |

Internally:
```
xpx = (rawX - xmin) * xpix / (xmax - xmin)
ypx = (rawY - ymin) * ypix / (ymax - ymin)
col = (xpix - xpx) if rr else xpx
row = (ypix - ypx) if rc else ypx
if trans: col, row = row, col
```

### How to find the right parameters

Create a diagnostic script that reads raw values while you tap four screen
corners:

```python
from machine import SPI, Pin, freq
import time
freq(240_000_000)

spi = SPI(2, 2_500_000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
cs  = Pin(33, Pin.OUT, value=1)

def raw(chan):
    buf = bytearray([0x83 | (chan << 4), 0, 0])
    r   = bytearray(3)
    cs(0); spi.write_readinto(buf, r); cs(1)
    return (int.from_bytes(r, "big") >> 3) & 0xFFF

prev = False
while True:
    z = raw(3)
    if z > 200 and not prev:
        print(f"rawX={raw(5)}  rawY={raw(1)}")
    prev = z > 200
    time.sleep_ms(50)
```

Tap far-left, far-right, top, bottom and record the values. Then determine:
- Which raw axis changes with left-right movement → that's the col source
- Whether `trans` is needed to swap them
- Whether `rr`/`rc` are needed to fix reflection

For the CYD in landscape mode with `usd=False`:
`tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)` is correct.

---

## 5. Application structure

### Entry point

```python
import touch_setup          # MUST be first
from gui.core.tgui import Screen, ssd
# ... import widgets, fonts, colors ...

class MyScreen(Screen):
    def __init__(self):
        super().__init__()
        # create widgets here

    def after_open(self):
        # called once after the screen is first displayed
        asyncio.create_task(self.my_task())

    async def my_task(self):
        while True:
            await asyncio.sleep_ms(250)
            # update state

Screen.change(MyScreen)     # starts the asyncio event loop internally
```

`Screen.change()` instantiates the class and runs `asyncio` — there is no
separate `asyncio.run()` call needed.

### Screen lifecycle

1. `Screen.__init__` — create all widgets; they register themselves.
2. Framework renders widgets to FrameBuffer.
3. `Screen.after_open()` — called once; start async tasks here.
4. `auto_refresh` task runs continuously: redraws stale widgets → `ssd.show()`.
5. Touch events are detected by the framework and dispatched to widgets.

---

## 6. Colors

The ILI9341 driver uses a **4-bit GS4_HMSB FrameBuffer** — 16 colors
defined by a lookup table (LUT).  Drawing operations take a LUT index (0–15),
not an RGB565 value.

Pre-defined constants (from `gui/core/colors.py`):

| Index | Name | RGB |
|-------|------|-----|
| 0 | BLACK | 0,0,0 |
| 1 | GREEN | 0,255,0 |
| 2 | RED | 255,0,0 |
| 3 | LIGHTRED | 140,0,0 |
| 4 | BLUE | 0,0,255 |
| 5 | YELLOW | 255,255,0 |
| 6 | GREY | 100,100,100 |
| 7 | MAGENTA | 255,0,255 |
| 8 | CYAN | 0,255,255 |
| 9 | LIGHTGREEN | 0,100,0 |
| 10 | DARKGREEN | 0,80,0 |
| 11 | DARKBLUE | 0,0,90 |
| 12–14 | *(free for user)* | |
| 15 | WHITE | 255,255,255 |

Define custom colors using the three free slots:

```python
from gui.core.colors import *
AMBER = create_color(12, 220, 160, 0)   # index, r, g, b
```

`create_color(idx, r, g, b)` writes the RGB into the LUT at position `idx`
and returns `idx`.  Only 16 colors can be active at once.

---

## 7. Widgets

All widgets take a `CWriter` as their first argument.

### CWriter

```python
from gui.core.writer import CWriter
wri = CWriter(ssd, font, fgcolor, bgcolor)
```

The `fgcolor` and `bgcolor` are LUT indices.  Individual widgets can override
these with their own `fgcolor=` / `bgcolor=` keyword arguments.

### Fonts

Fonts ship as Python modules in `gui/fonts/`.  Installed by default:
`arial10`, `font10`.  Others available in the repo: `freesans20`, `arial35`,
`arial_50`, `font14`, etc.

```python
import gui.fonts.freesans20 as font_sm
import gui.fonts.arial35    as font_lg
wri = CWriter(ssd, font_lg, WHITE, BLACK)
```

To use a custom font, convert a TTF with `font_to_py.py` (bundled in the repo):
```bash
python3 font_to_py.py -x FreeSans.ttf 40 freesans40.py
```

### Label

```python
from gui.widgets.label import Label

# Static text — width derived from string
lbl = Label(wri, row, col, 'Hello')

# Pre-allocated width (pass int), text set later
lbl = Label(wri, row, col, 150, justify=Label.CENTRE)
lbl.value('30:00')          # update text; widget redraws itself
```

Justify options: `Label.LEFT` (0), `Label.CENTRE` (1), `Label.RIGHT` (2).

### Button

```python
from gui.widgets.buttons import Button

def my_cb(btn, arg):
    print('pressed', arg)

Button(wri, row, col,
       height=80, width=150,
       text='TAP',
       fgcolor=WHITE, bgcolor=DARKGREEN,
       callback=my_cb, args=('player_a',))
```

The callback receives the Button instance as the first argument, then any
values from `args`.

---

## 8. Direct framebuffer drawing

For shapes not covered by widgets (e.g. progress bars), draw directly to `ssd`
using standard MicroPython `FrameBuffer` methods:

```python
ssd.fill_rect(x, y, width, height, color)   # filled rectangle
ssd.line(x0, y0, x1, y1, color)             # line
ssd.pixel(x, y, color)                      # single pixel
```

Colors are LUT indices (0–15), the same as with widgets.

**Do not call `ssd.show()` after drawing.** The `auto_refresh` task flushes
the FrameBuffer to the display on every cycle.  Calling `ssd.show()` yourself
adds a second SPI transfer and causes visible tearing.

Position custom drawing so it does not overlap widget bounding boxes.
`Screen.show()` only redraws *stale* widgets; if a widget redraws over your
custom graphics, those pixels will be lost until your next direct draw.

---

## 9. Async tasks

```python
class MyScreen(Screen):
    def after_open(self):
        asyncio.create_task(self._ticker())

    async def _ticker(self):
        import time
        ref = time.ticks_ms()
        while True:
            await asyncio.sleep_ms(250)
            now = time.ticks_ms()
            dt  = time.ticks_diff(now, ref) / 1000.0
            ref = now
            # update state, redraw widgets / bars
```

- Use `time.ticks_ms()` and `time.ticks_diff()` for elapsed time — they
  handle the 32-bit millisecond counter rollover correctly.
- The framework's `auto_refresh` and touch-polling tasks also run in the same
  event loop; keep your tasks non-blocking (short synchronous sections,
  `await` regularly).

---

## 10. Common pitfalls

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| File named `hardware_setup.py` | `ImportError` in `colors.py` | Must be `touch_setup.py` |
| `rst=None` in ILI9341 | `TypeError` (driver calls `rst(0)`) | Use a no-op `_NoPin()` callable |
| `rst=Pin(0,…)` | Display held in reset; blank screen | GPIO 0 is boot pin; use `_NoPin()` |
| `XPT2046(spi, cs, irq, w, h)` | `TypeError` | Real signature: `XPT2046(spi, cs, ssd)` |
| `create_color(r, g, b)` | Wrong LUT slot | Real signature: `create_color(idx, r, g, b)` |
| Calling `ssd.show()` manually | Tearing / flicker | Remove it; `auto_refresh` owns `ssd.show()` |
| Default `tpad.init` on CYD | Right half of screen unreachable | `tpad.init(240, 320, 0, 0, 4095, 4095, True, True, True)` |
| `asyncio.run(Screen.main())` | `AttributeError` | `Screen.change(MyScreen)` is sufficient |
| Using `Writer` instead of `CWriter` | May render without correct colors | Use `CWriter(ssd, font, fg, bg)` |

---

## 11. Deployment workflow

```bash
# First-time setup
mpremote mip install github:peterhinch/micropython-touch
mpremote cp freesans20.py :gui/fonts/freesans20.py
mpremote cp arial35.py    :gui/fonts/arial35.py

# Deploy app files
mpremote cp touch_setup.py :touch_setup.py
mpremote cp chess_clock.py :chess_clock.py
mpremote cp main.py        :main.py

# Test without reset
mpremote run chess_clock.py

# Verify auto-start
mpremote reset
```

`main.py` is executed automatically by MicroPython after `boot.py` on every
power-on or reset.  Its only job is `import chess_clock`, which pulls in
`touch_setup` and ends with `Screen.change(ChessClock)`.

---

## 12. Touch calibration utility

The framework ships a calibration utility at `touch/setup.py`.  Run it once
to display on-screen targets and compute exact `tpad.init()` values:

```bash
mpremote run touch/setup.py
```

Paste the printed `tpad.init(…)` line into your `touch_setup.py`.
