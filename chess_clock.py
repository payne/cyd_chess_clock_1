# chess_clock.py
"""
Two-player chess clock for the CYD (320 × 240, landscape).

Rules
─────
  • Tap YOUR button  →  your countdown starts; opponent's pauses.
  • Tap RST          →  reset both clocks to 30:00.
  • When a clock hits 00:00 that player's half flashes red.

Layout (each half is 160 × 240 px)
────────────────────────────────────
  ┌──────────┬─┬──────────┐   row 0
  │ PLAYER A │R│ PLAYER B │   rows  0 – 22
  │  MM:SS   │S│  MM:SS   │   rows 22 – 96
  │ ══gauge══│T│ ══gauge══│   rows 96 – 132
  │          │ │          │
  │  TAP A   │ │  TAP B   │   rows 138 – 236
  └──────────┴─┴──────────┘   row 240
"""

import hardware_setup           # must be first — creates ssd/touch/Display
import asyncio
import time

from gui.core.tgui      import Screen, ssd
from gui.widgets.buttons import Button
from gui.widgets.label   import Label
from gui.core.writer     import Writer
from gui.core.colors     import *

import gui.fonts.freesans20 as _fnt_sm

# Use a large font for the clock digits if available; fall back to freesans20.
try:
    import gui.fonts.freesans40 as _fnt_lg
except ImportError:
    _fnt_lg = _fnt_sm


# ─── Layout constants ────────────────────────────────────────────────────────

W, H   = 320, 240
MID    = W // 2         # x of the centre divider
GAP    = 4              # inner margin

HDR_Y  = 2             # header label row
CLK_Y  = 24            # time label row
BAR_Y  = 98            # gauge bar top
BAR_H  = 32            # gauge bar height
BTN_Y  = 138           # tap-button top
BTN_H  = H - BTN_Y - GAP   # tap-button height  (~98 px)

TOTAL      = 30 * 60   # 30 minutes per player
WARN_SECS  = 5 * 60    # amber below 5 min
CRIT_SECS  = 1 * 60    # red below 1 min
TICK_MS    = 250        # display refresh interval

# Precompute tick sizes for the 5-minute guide marks on the gauge
TICK_INTERVALS = 6      # one tick per 5 minutes


# ─── Colour helpers ──────────────────────────────────────────────────────────

def _gauge_col(remaining: float) -> int:
    if   remaining > WARN_SECS: return create_color(  0, 200,  60)
    elif remaining > CRIT_SECS: return create_color(220, 160,   0)
    else:                       return create_color(220,  30,   0)

_GREY_BAR  = create_color( 40,  40,  40)
_GREEN_BTN = create_color(  0, 110,  45)
_RED_BTN   = create_color(150,   0,   0)
_RST_BTN   = create_color( 55,  55,  55)
_FLASH_RED = create_color(200,   0,   0)


# ─── Screen ─────────────────────────────────────────────────────────────────

class ChessClock(Screen):

    def __init__(self):
        super().__init__()
        self._secs   = [float(TOTAL), float(TOTAL)]  # [player-A, player-B]
        self._active = None    # None | 0 (A) | 1 (B)
        self._done   = False
        self._t_ref  = None    # ticks_ms when the active slice started

        wri_sm = Writer(ssd, _fnt_sm)
        wri_lg = Writer(ssd, _fnt_lg)

        lbl_w = MID - 2 * GAP          # time-label and gauge width
        btn_w = MID - GAP              # tap-button width

        # Headers
        Label(wri_sm, HDR_Y,       GAP,       text='PLAYER A', fgcolor=WHITE, bgcolor=BLACK)
        Label(wri_sm, HDR_Y, MID + GAP,       text='PLAYER B', fgcolor=WHITE, bgcolor=BLACK)

        # Time labels (large digits)
        self._lbl = [
            Label(wri_lg, CLK_Y,       GAP, width=lbl_w,
                  justify=Label.CENTRE, fgcolor=WHITE, bgcolor=BLACK),
            Label(wri_lg, CLK_Y, MID + GAP, width=lbl_w,
                  justify=Label.CENTRE, fgcolor=WHITE, bgcolor=BLACK),
        ]

        # Tap buttons
        Button(wri_sm, BTN_Y,       GAP, height=BTN_H, width=btn_w,
               text='TAP A', fgcolor=WHITE, bgcolor=_GREEN_BTN,
               callback=self._tap, args=(0,))
        Button(wri_sm, BTN_Y, MID + GAP, height=BTN_H, width=btn_w,
               text='TAP B', fgcolor=WHITE, bgcolor=_RED_BTN,
               callback=self._tap, args=(1,))

        # Reset button — centred at the top
        Button(wri_sm, HDR_Y, MID - 22, height=20, width=44,
               text='RST', fgcolor=WHITE, bgcolor=_RST_BTN,
               callback=self._reset)

        self._paint_labels()

    # ── startup ──────────────────────────────────────────────────────────────

    def after_open(self):
        self._paint_bars()                      # draw gauge bars on first show
        asyncio.create_task(self._run())

    # ── formatting ───────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(secs: float) -> str:
        s = max(0, int(secs))
        return f'{s // 60:02d}:{s % 60:02d}'

    # ── display helpers ───────────────────────────────────────────────────────

    def _paint_labels(self):
        """Update both time labels (draws to framebuffer; no show() yet)."""
        for i in range(2):
            self._lbl[i].value(self._fmt(self._secs[i]))

    def _paint_bars(self):
        """Repaint both gauge bars plus the centre divider, then show()."""
        bar_w = MID - 2 * GAP

        for player, x_off in enumerate((GAP, MID + GAP)):
            rem    = self._secs[player]
            filled = int(bar_w * max(0.0, rem / TOTAL))

            # Background track
            ssd.fill_rect(x_off, BAR_Y, bar_w, BAR_H, _GREY_BAR)

            # Filled portion
            if filled > 0:
                ssd.fill_rect(x_off, BAR_Y, filled, BAR_H, _gauge_col(rem))

            # Guide marks at every 5-minute interval (thin black hairlines)
            for tick in range(1, TICK_INTERVALS):
                tx = x_off + int(bar_w * tick / TICK_INTERVALS)
                ssd.fill_rect(tx, BAR_Y, 1, BAR_H, BLACK)

        # Centre divider (2 px wide so it's clearly visible)
        ssd.fill_rect(MID, 0, 2, H, WHITE)

        ssd.show()

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _tap(self, _btn, player: int):
        if self._done or self._active == player:
            return
        self._active = player
        self._t_ref  = time.ticks_ms()

    def _reset(self, _btn):
        self._secs   = [float(TOTAL), float(TOTAL)]
        self._active = None
        self._done   = False
        self._t_ref  = None
        self._paint_labels()
        self._paint_bars()

    # ── async main loop ───────────────────────────────────────────────────────

    async def _run(self):
        """Decrement the active clock every TICK_MS ms and refresh."""
        while True:
            await asyncio.sleep_ms(TICK_MS)

            if self._active is None or self._done:
                continue

            now          = time.ticks_ms()
            dt           = time.ticks_diff(now, self._t_ref) / 1000.0
            self._t_ref  = now

            p = self._active
            self._secs[p] = max(0.0, self._secs[p] - dt)

            self._paint_labels()
            self._paint_bars()

            if self._secs[p] <= 0:
                self._done = True
                await self._timeout_flash(p)

    async def _timeout_flash(self, loser: int):
        """Flash the loser's half red six times, then restore the display."""
        x = GAP if loser == 0 else MID + GAP
        w = MID - GAP
        for _ in range(6):
            ssd.fill_rect(x, 0, w, H, _FLASH_RED)
            ssd.show()
            await asyncio.sleep_ms(350)
            ssd.fill_rect(x, 0, w, H, BLACK)
            ssd.show()
            await asyncio.sleep_ms(350)
        # Leave the frozen 00:00 on screen
        self._paint_labels()
        self._paint_bars()


# ─── Entry point ─────────────────────────────────────────────────────────────

Screen.change(ChessClock)
asyncio.run(Screen.main())
