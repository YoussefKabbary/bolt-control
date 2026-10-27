# -*- coding: utf-8 -*-
"""
RGB page: any color on an RGB LED (rgb_firmware/rgb_firmware.ino).

Sends the color as a line "#RRGGBB" (e.g. #FF8000 = orange). While a slider is
dragged the page sends at most one color every SEND_GAP_MS. '?' asks the Arduino
for its color; it answers RGB:r,g,b.

KEYBOARD
  SPACE   off
"""

import tkinter as tk

from ui import (BG, CARD, INPUT, TEXT, MUTED, DIM, ACCENT, BLUE, ROSE, FONT, FONT_B,
                blend, button, card, says_label, Page)

SEND_GAP_MS = 40

PRESETS = [("Red", (255, 0, 0)), ("Orange", (255, 80, 0)), ("Yellow", (255, 190, 0)),
           ("Green", (0, 255, 0)), ("Cyan", (0, 255, 200)), ("Blue", (0, 0, 255)),
           ("Purple", (150, 0, 255)), ("Pink", (255, 0, 110)), ("White", (255, 255, 255))]


def hex_color(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


class ColorSlider:
    """0-255 slider drawn on a canvas: a soft gradient track and a round knob."""

    def __init__(self, parent, label, tint, on_change):
        self.value = 0
        self.tint = tint
        self.on_change = on_change
        row = tk.Frame(parent, bg=CARD); row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=label, fg=MUTED, bg=CARD, font=(FONT_B, 10), width=2).pack(side=tk.LEFT)
        self.c = tk.Canvas(row, height=26, bg=CARD, highlightthickness=0, cursor="hand2")
        self.c.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.lbl = tk.Label(row, text="0", fg=TEXT, bg=CARD, font=("Consolas", 10), width=4, anchor="e")
        self.lbl.pack(side=tk.LEFT)
        self.c.bind("<Configure>", lambda e: self.draw())
        self.c.bind("<Button-1>", self.drag)
        self.c.bind("<B1-Motion>", self.drag)
        self.c.bind("<ButtonRelease-1>", lambda e: self.on_change(final=True))

    def drag(self, e):
        w = max(self.c.winfo_width() - 24, 1)
        self.set(round(max(0, min(1, (e.x - 12) / w)) * 255))
        self.on_change()

    def set(self, v):
        self.value = int(v)
        self.lbl.config(text=str(self.value))
        self.draw()

    def draw(self):
        c = self.c
        c.delete("all")
        W = c.winfo_width()
        W = W if W > 30 else 300
        x0, x1, y = 12, W - 12, 13
        n = 48
        for i in range(n):
            a = x0 + (x1 - x0) * i / n
            b = x0 + (x1 - x0) * (i + 1) / n + 1
            c.create_rectangle(a, y - 4, b, y + 4, fill=blend(INPUT, self.tint, i / (n - 1)), outline="")
        kx = x0 + (x1 - x0) * self.value / 255
        c.create_oval(kx - 9, y - 9, kx + 9, y + 9, fill=TEXT, outline=CARD, width=2)


class RgbPage(Page):
    key = "rgb"
    title = "RGB"
    blurb = "Pick any color for an RGB LED, or mix your own"
    sketch = "rgb_firmware.ino"
    keys_help = "Drag the sliders or tap a color.     Space  off"

    def __init__(self, app, parent):
        super().__init__(app, parent)
        self.rgb = [0, 0, 0]
        self.sent = None             # last color sent to the Arduino
        self.timer = None            # throttle timer while dragging
        self.asked = False           # waiting for the answer to '?'

        top = card(self.frame, "COLOR  \u00B7  R pin 9  \u00B7  G pin 10  \u00B7  B pin 11", pady=6, fill=tk.X)
        self.preview = tk.Canvas(top, height=230, bg=CARD, highlightthickness=0)
        self.preview.pack(fill=tk.X)
        self.preview.bind("<Configure>", lambda e: self.draw())

        mix = card(self.frame, "MIX", fill=tk.BOTH, expand=True, pady=6)
        self.sliders = [ColorSlider(mix, "R", ROSE, self.slider_moved),
                        ColorSlider(mix, "G", "#8fc29a", self.slider_moved),
                        ColorSlider(mix, "B", BLUE, self.slider_moved)]

        pr = tk.Frame(mix, bg=CARD); pr.pack(fill=tk.X, pady=(12, 0))
        for name, rgb in PRESETS:
            self.swatch(pr, name, rgb).pack(side=tk.LEFT, padx=(0, 6))
        button(pr, "Off   Space", command=lambda: self.pick((0, 0, 0), "OFF"),
               fg=MUTED, padx=12, pady=6).pack(side=tk.RIGHT)
        self.says = says_label(mix)
        self.draw()

    @staticmethod
    def draw_icon(c):
        for (x, y), col in zip(((22, 22), (42, 22), (32, 40)), (ROSE, "#8fc29a", BLUE)):
            c.create_oval(x - 14, y - 14, x + 14, y + 14, fill=col, outline="")

    def swatch(self, parent, name, rgb):
        s = tk.Canvas(parent, width=34, height=34, bg=CARD, highlightthickness=0, cursor="hand2")
        s.create_oval(3, 3, 31, 31, fill=blend(hex_color(rgb), CARD, 0.15), outline="")
        s.bind("<Button-1>", lambda e: self.pick(rgb, name.upper()))
        return s

    # ------------------------------------------------------------
    def pick(self, rgb, name):
        self.set_rgb(rgb)
        self.app.log_msg(f"\u2192 {name}  {hex_color(rgb)}")

    def slider_moved(self, final=False):
        self.set_rgb([s.value for s in self.sliders], from_slider=True)
        if final:
            self.app.log_msg(f"\u2192 COLOR {hex_color(self.rgb)}")

    def set_rgb(self, rgb, from_slider=False, send=True):
        self.rgb = [int(v) for v in rgb]
        if not from_slider:
            for s, v in zip(self.sliders, self.rgb):
                s.set(v)
        self.draw()
        if send:
            self.schedule_send()

    def schedule_send(self):
        """Send now, then at most once every SEND_GAP_MS while the color keeps changing."""
        if self.timer is None:
            self.send_now()
            self.timer = self.app.root.after(SEND_GAP_MS, self._gap_over)

    def _gap_over(self):
        self.timer = None
        if tuple(self.rgb) != self.sent:
            self.schedule_send()

    def send_now(self):
        color = tuple(self.rgb)
        if color == self.sent:
            return
        self.sent = color
        self.app.write(hex_color(color) + "\n")

    def key_down(self, k):
        if k == "space":
            self.pick((0, 0, 0), "OFF")

    # ------------------------------------------------------------
    def draw(self):
        c = self.preview
        c.delete("all")
        W = c.winfo_width()
        W = W if W > 50 else 600
        cx, cy, r = W / 2, 92, 46
        off = sum(self.rgb) == 0
        col = hex_color(self.rgb)
        if not off:                                   # soft glow in the LED's color
            for k, t in ((1.9, 0.08), (1.55, 0.15), (1.25, 0.28)):
                c.create_oval(cx - r * k, cy - r * k, cx + r * k, cy + r * k,
                              fill=blend(CARD, col, t), outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=(INPUT if off else col),
                      outline=(DIM if off else ""), width=2)
        # four legs: the long one is the common leg
        for i, (dx, extra) in enumerate(((-18, 0), (-6, 18), (6, 0), (18, 0))):
            c.create_line(cx + dx, cy + r, cx + dx, cy + r + 34 + extra, fill=DIM, width=3)
        txt = "OFF" if off else f"{col}     R {self.rgb[0]}   G {self.rgb[1]}   B {self.rgb[2]}"
        c.create_text(cx, cy + r + 66, text=txt, fill=(DIM if off else TEXT), font=(FONT, 11))
        if not self.app.connected:
            c.create_text(W - 12, 12, text="practice", fill=DIM, font=(FONT, 9), anchor="ne")

    # ------------------------------------------------------------
    # PAGE HOOKS
    # ------------------------------------------------------------
    def on_show(self):
        self.ask()
        self.draw()

    def on_connect(self):
        self.ask()
        self.draw()

    def on_disconnect(self):
        self.says.config(text="Arduino: \u2013", fg=DIM)
        self.app.root.after(300, self.draw)

    def ask(self):
        self.sent = None
        if self.app.connected:
            self.asked = True
            self.app.write("?")

    def on_line(self, line):
        if not line.startswith("RGB:"):
            return False
        try:
            rgb = [max(0, min(255, int(v))) for v in line[4:].split(",")][:3]
        except ValueError:
            return False
        if len(rgb) != 3:
            return False
        self.says.config(text=f"Arduino: color {hex_color(rgb)}", fg=ACCENT)
        if self.asked:                                # take the Arduino's color when we asked
            self.asked = False
            self.sent = tuple(rgb)
            self.set_rgb(rgb, send=False)
        return True
