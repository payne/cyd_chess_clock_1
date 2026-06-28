# Session interactions — 2026-06-27

## Request 1 — Chess clock for CYD

**User:** Write a chess clock for the Cheap Yellow Display (CYD) using
[micropython-touch](https://github.com/peterhinch/micropython-touch).

Two players, each with a button and a countdown gauge.  Player A taps their
button → their gauge starts counting down from 30 minutes.  If Player B's gauge
was running it stops.  Player B taps their button → B's gauge starts, A's
pauses.  One-second display resolution.

---

**Assistant created:** `hardware_setup.py` and `chess_clock.py`

### hardware_setup.py

Configures the ESP32-2432S028R (CYD) for micropython-touch:

| Peripheral | Bus | Pins |
|------------|-----|------|
| ILI9341 display | SPI1 / HSPI | CLK=14 MOSI=13 MISO=12 CS=15 DC=2 RST=0 BL=21 |
| XPT2046 touch | SPI2 / VSPI | CLK=25 MOSI=32 MISO=39 CS=33 IRQ=36 |

- Runs ESP32 at 240 MHz.
- Turns backlight on via GPIO 21.
- Registers `ssd` and `touch` with `gui.core.tgui.Display`.
- Notes on `bgr=True` (colour swap) and `touch.set_cal(...)` (calibration).

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

**State machine:**
- `_active = None` → neither clock running (initial / after reset)
- Tap TAP A → `_active = 0`; A counts down, B pauses
- Tap TAP B → `_active = 1`; B counts down, A pauses
- Tap RST → both clocks reset to 30:00, `_active = None`
- Clock hits 00:00 → `_done = True`; loser's half flashes red × 6

**Gauge bar:**
- Drawn directly to `ssd` FrameBuffer via `fill_rect`.
- Colour: green > 5 min, amber > 1 min, red ≤ 1 min.
- Six hairline tick marks at 5-minute intervals.
- Single `ssd.show()` per tick (labels drawn first, then bars) to avoid flicker.

**Timing:** async task wakes every 250 ms; uses `time.ticks_diff` for
sub-second accuracy so the displayed seconds are correct even under load.

**Font fallback:** tries `gui.fonts.freesans40`; falls back to `freesans20`.

---

## Request 2 — Auto-start on reset + session log

**User:** Create `main.py` so the chess clock starts automatically on board
reset.  Record everything from this session in `interactions.md`.

---

**Assistant created:** `main.py` and this file.

### main.py

```python
import chess_clock
```

MicroPython executes `main.py` automatically after `boot.py` on every
power-on / reset.  Importing `chess_clock` triggers its module-level code,
which calls `hardware_setup` and then `asyncio.run(Screen.main())`.

---

## Deployment checklist

```bash
# 1. Install the framework
mpremote mip install github:peterhinch/micropython-touch

# 2. Copy all four files
mpremote cp hardware_setup.py chess_clock.py main.py :

# 3. Verify auto-start
mpremote reset
```

**First-boot tasks:**
- If red/blue are swapped → set `bgr=True` in `hardware_setup.py`.
- Run the micropython-touch calibration utility and add `touch.set_cal(...)`
  in `hardware_setup.py`.
- For larger clock digits, generate a font:
  `python3 font_to_py.py -x FreeSans.ttf 40 freesans40.py`
  then copy it to `gui/fonts/` on the device.
