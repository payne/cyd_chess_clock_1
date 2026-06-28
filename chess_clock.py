# chess_clock.py — Two-player chess clock for CYD (320×240)
#
# Tap YOUR button to start your countdown; the other player's pauses.
# Tap RST to reset both clocks to 30:00.
# When a clock hits 00:00 that half flashes red.

import touch_setup          # Must be first — creates ssd/tpad/Display
import asyncio
import time

from gui.core.tgui      import Screen, ssd
from gui.widgets.buttons import Button
from gui.widgets.label   import Label
from gui.core.writer     import CWriter
from gui.core.colors     import *   # BLACK=0 GREEN=1 RED=2 … WHITE=15

import gui.fonts.freesans20 as font_sm
try:
    import gui.fonts.arial35 as font_lg
except ImportError:
    font_lg = font_sm   # fall back if large font not installed

# One free LUT slot for the amber warning colour (indices 12-14 are user slots)
AMBER = create_color(12, 220, 160, 0)

# ── Layout ───────────────────────────────────────────────────────────────────
TOTAL = 30 * 60        # seconds per player
W, H  = 320, 240
MID   = W // 2
GAP   = 4

BAR_Y, BAR_H = 98, 32
BTN_Y  = BAR_Y + BAR_H + 8
BTN_H  = H - BTN_Y - GAP


def _gauge_col(remaining):
    if   remaining > 5 * 60: return GREEN
    elif remaining > 60:     return AMBER
    else:                    return RED


# ── Screen ───────────────────────────────────────────────────────────────────
class ChessClock(Screen):

    def __init__(self):
        super().__init__()
        self._secs   = [float(TOTAL), float(TOTAL)]
        self._active = None   # None | 0 (A) | 1 (B)
        self._done   = False
        self._t_ref  = None

        wri_sm = CWriter(ssd, font_sm, WHITE, BLACK)
        wri_lg = CWriter(ssd, font_lg, WHITE, BLACK)

        # ── Static headers ────────────────────────────────────────────────────
        Label(wri_sm, GAP,       GAP, 'PLAYER A')
        Label(wri_sm, GAP, MID + GAP, 'PLAYER B')

        # ── Time labels (initialised with width; text set in after_open) ──────
        lbl_w = MID - 2 * GAP
        self._lbl = [
            Label(wri_lg, 26,       GAP, lbl_w, justify=Label.CENTRE),
            Label(wri_lg, 26, MID + GAP, lbl_w, justify=Label.CENTRE),
        ]

        # ── Tap buttons ───────────────────────────────────────────────────────
        btn_w = MID - GAP
        Button(wri_sm, BTN_Y,       GAP, height=BTN_H, width=btn_w,
               text='TAP A', bgcolor=DARKGREEN, callback=self._tap, args=(0,))
        Button(wri_sm, BTN_Y, MID + GAP, height=BTN_H, width=btn_w,
               text='TAP B', bgcolor=LIGHTRED,  callback=self._tap, args=(1,))

        # ── Reset button centred at top ───────────────────────────────────────
        Button(wri_sm, 0, MID - 22, height=20, width=44,
               text='RST', bgcolor=GREY, callback=self._reset)

    # ── Startup ───────────────────────────────────────────────────────────────

    def after_open(self):
        self._show_time()
        self._draw_bars()
        asyncio.create_task(self._run())

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(s):
        s = max(0, int(s))
        return f'{s // 60:02d}:{s % 60:02d}'

    def _show_time(self):
        for i in range(2):
            self._lbl[i].value(self._fmt(self._secs[i]))

    def _draw_divider(self):
        ssd.fill_rect(MID, 0, 2, H, WHITE)

    def _draw_bars(self):
        bw = MID - 2 * GAP
        for i, x in enumerate((GAP, MID + GAP)):
            rem  = self._secs[i]
            fill = int(bw * max(0.0, rem / TOTAL))
            ssd.fill_rect(x, BAR_Y, bw, BAR_H, GREY)
            if fill:
                ssd.fill_rect(x, BAR_Y, fill, BAR_H, _gauge_col(rem))
            # Hairline tick marks at 5-minute intervals
            for t in range(1, 6):
                ssd.fill_rect(x + int(bw * t / 6), BAR_Y, 1, BAR_H, BLACK)
        self._draw_divider()
        ssd.show()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _tap(self, _btn, player):
        if self._done or self._active == player:
            return
        self._active = player
        self._t_ref  = time.ticks_ms()

    def _reset(self, _btn):
        self._secs   = [float(TOTAL), float(TOTAL)]
        self._active = None
        self._done   = False
        self._t_ref  = None
        self._show_time()
        self._draw_bars()

    # ── Timer loop ────────────────────────────────────────────────────────────

    async def _run(self):
        while True:
            await asyncio.sleep_ms(250)
            if self._active is None or self._done:
                continue
            now = time.ticks_ms()
            dt  = time.ticks_diff(now, self._t_ref) / 1000.0
            self._t_ref = now
            p = self._active
            self._secs[p] = max(0.0, self._secs[p] - dt)
            self._show_time()
            self._draw_bars()
            if self._secs[p] <= 0:
                self._done = True
                await self._timeout_flash(p)

    async def _timeout_flash(self, loser):
        x = GAP if loser == 0 else MID + GAP
        w = MID - GAP
        for _ in range(6):
            ssd.fill_rect(x, 0, w, H, RED)
            ssd.show()
            await asyncio.sleep_ms(350)
            ssd.fill_rect(x, 0, w, H, BLACK)
            ssd.show()
            await asyncio.sleep_ms(350)
        self._show_time()
        self._draw_bars()


# Screen.change starts the asyncio event loop internally
Screen.change(ChessClock)
