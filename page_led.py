# -*- coding: utf-8 -*-
"""
LED page: one LED on pin 13 (led_firmware/led_firmware.ino).

Sends '1' (on) and '0' (off), the same as the phone app's LED/Lamp screen
(Lecture 8). '?' asks the Arduino what the LED is doing; it answers LED:1 / LED:0.

KEYBOARD
  SPACE   on / off
  1 / 0   on / off
"""

import tkinter as tk

from ui import (CARD, INPUT, TEXT, DIM, ACCENT, SAND, ROSE, FONT, FONT_B,
                blend, button, card, says_label, Page)


class LedPage(Page):
    key = "led"
    title = "LED"
    blurb = "Turn an LED on and off, like the phone LED/Lamp screen"
    sketch = "led_firmware.ino"
    keys_help = "Space  on / off     1  on     0  off"

    def __init__(self, app, parent):
        super().__init__(app, parent)
        self.on = False
        self.asked = False           # waiting for the answer to '?'

        c = card(self.frame, "LED  \u00B7  pin 13", fill=tk.BOTH, expand=True, pady=6)
        self.lamp = tk.Canvas(c, height=360, bg=CARD, highlightthickness=0)
        self.lamp.pack(fill=tk.X, pady=(6, 0))
        self.lamp.bind("<Configure>", lambda e: self.draw())
        self.lamp.bind("<Button-1>", lambda e: self.toggle())

        self.btn = button(c, "", command=self.toggle, font=(FONT_B, 12), pady=12)
        self.btn.pack(fill=tk.X, padx=120, pady=(10, 0))
        tk.Label(c, text="Sends 1 to turn on and 0 to turn off, like the phone LED/Lamp screen.",
                 fg=DIM, bg=CARD, font=(FONT, 9)).pack(pady=(10, 0))
        self.says = says_label(c)
        self.refresh()

    @staticmethod
    def draw_icon(c):
        c.create_oval(14, 6, 50, 42, fill=SAND, outline="")
        c.create_rectangle(24, 42, 40, 52, fill=DIM, outline="")
        c.create_line(24, 56, 40, 56, fill=DIM, width=3)

    # ------------------------------------------------------------
    def set(self, on):
        self.on = on
        self.app.write("1" if on else "0")
        self.app.log_msg(f"\u2192 LED {'ON' if on else 'OFF'}")
        self.refresh()

    def toggle(self):
        self.set(not self.on)

    def key_down(self, k):
        if k == "space":
            self.toggle()
        elif k == "1":
            self.set(True)
        elif k == "0":
            self.set(False)

    def refresh(self):
        self.btn.config(text=("Turn off" if self.on else "Turn on"),
                        bg=(SAND if self.on else INPUT), fg=("#1b1f26" if self.on else TEXT),
                        activebackground=(SAND if self.on else INPUT),
                        activeforeground=("#1b1f26" if self.on else TEXT))
        self.draw()

    def draw(self):
        c = self.lamp
        c.delete("all")
        W = c.winfo_width()
        W = W if W > 50 else 600
        cx, cy, r = W / 2, 150, 70

        if self.on:                                   # soft glow
            for k, t in ((2.1, 0.06), (1.7, 0.12), (1.35, 0.22)):
                c.create_oval(cx - r * k, cy - r * k, cx + r * k, cy + r * k,
                              fill=blend(CARD, SAND, t), outline="")
        bulb = "#f2e3bd" if self.on else INPUT
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=bulb,
                      outline=("" if self.on else DIM), width=2)
        # filament
        fil = blend(SAND, "#7a5a2a", 0.4) if self.on else DIM
        c.create_line(cx - 22, cy + 20, cx - 10, cy - 10, cx, cy + 8, cx + 10, cy - 10,
                      cx + 22, cy + 20, fill=fil, width=3, smooth=True)
        # base
        c.create_rectangle(cx - 30, cy + r - 8, cx + 30, cy + r + 30, fill=DIM, outline="")
        for k in range(3):
            y = cy + r + 2 + k * 9
            c.create_line(cx - 30, y, cx + 30, y, fill=CARD, width=2)
        c.create_text(cx, cy + r + 62, text=("ON" if self.on else "OFF"),
                      fill=(SAND if self.on else DIM), font=(FONT_B, 13))
        if not self.app.connected:
            c.create_text(cx, cy + r + 88, text="practice", fill=DIM, font=(FONT, 9))

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
        if self.app.connected:
            self.asked = True
            self.app.write("?")

    def on_line(self, line):
        if line not in ("LED:1", "LED:0"):
            return False
        lit = line == "LED:1"
        self.says.config(text=f"Arduino: LED is {'on' if lit else 'off'}",
                         fg=(ACCENT if lit == self.on or self.asked else ROSE))
        if self.asked:                                # take the Arduino's state when we asked
            self.asked = False
            self.on = lit
            self.refresh()
        return True
