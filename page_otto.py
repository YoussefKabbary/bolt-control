# -*- coding: utf-8 -*-
"""
OTTO page: walk Otto (otto_firmware/otto_firmware.ino).

Sends F / B / L / R while an arrow is held and S when it is let go, the same
letters as the phone Car Controller. The drawing walks with the same 5 moves as
the firmware (and the lecture blocks), so the servo dials show what each pin does.

KEYBOARD
  W A S D  or arrows   walk (hold)
  SPACE                stop
  0-9                  speed
"""

import tkinter as tk
import math

from ui import (BG, CARD, INPUT, TEXT, MUTED, DIM, ACCENT, BLUE, SAND, ROSE, FLOOR,
                FONT, FONT_B, blend, button, section_title, says_label, Page)

# one step = 5 moves (group, from, to), same tables as the firmware
STEP_FWD = [("feet", 90, 60), ("legs", 105, 70), ("feet", 60, 120), ("legs", 70, 105), ("feet", 120, 90)]
STEP_BACK = [("feet", 90, 120), ("legs", 105, 70), ("feet", 120, 60), ("legs", 70, 105), ("feet", 60, 90)]
# which servo pins each walk moves: (feet, legs)
PINS = {"F": ((5, 11), (6, 9)), "B": ((5, 11), (6, 9)), "L": ((5,), (6,)), "R": ((11,), (9,))}
TICK_MS = [20, 18, 16, 14, 12, 10, 9, 8, 7, 6]
START_LEVEL = 5
NAMES = {"F": "forward", "B": "back", "L": "left", "R": "right", "S": "standing"}

KEYS = {"w": "F", "up": "F", "s": "B", "down": "B", "a": "L", "left": "L", "d": "R", "right": "R"}
PAD = [[None, ("\u25B2", "F"), None],
       [("\u25C0", "L"), ("\u25A0", "S"), ("\u25B6", "R")],
       [None, ("\u25BC", "B"), None]]


class OttoSim:
    """The firmware's walk engine, run on the PC to draw Otto."""

    def __init__(self):
        self.servo = {5: 90, 11: 90, 6: 90, 9: 90}
        self.walk = "S"
        self.want = "S"
        self.level = START_LEVEL
        self.clock = 0.0

    def start_step(self, c):
        self.walk = c
        self.step = STEP_BACK if c == "B" else STEP_FWD
        self.move = 0
        self.angle = self.step[0][1]

    def tick(self):
        """One degree, like one pass of the firmware loop."""
        if self.walk == "S":
            if self.want != "S":
                self.start_step(self.want)
            return
        group, a, b = self.step[self.move]
        self.angle += 1 if b > a else -1
        feet, legs = PINS[self.walk]
        for p in (feet if group == "feet" else legs):
            self.servo[p] = self.angle
        if self.angle == b:
            self.move += 1
            if self.move < 5:
                self.angle = self.step[self.move][1]
            elif self.want == "S":
                self.walk = "S"
                self.servo = {5: 90, 11: 90, 6: 90, 9: 90}
            else:
                self.start_step(self.want)

    def run(self, ms):
        self.clock += ms
        t = TICK_MS[self.level]
        while self.clock >= t:
            self.clock -= t
            self.tick()


class OttoPage(Page):
    key = "otto"
    title = "Otto"
    blurb = "Walk Otto forward, back, left and right with the arrows"
    sketch = "otto_firmware.ino"
    keys_help = "W A S D / arrows  walk (hold)     Space  stop\n0-9  speed"

    def __init__(self, app, parent):
        super().__init__(app, parent)
        self.sim = OttoSim()
        self.held = []               # held arrow keys, newest last
        self.pad_dir = None
        self.dir = "S"
        self.level = START_LEVEL
        self.t = 0.0

        scene_card = tk.Frame(self.frame, bg=CARD)
        scene_card.pack(fill=tk.X, pady=6)
        self.scene = tk.Canvas(scene_card, height=300, bg=FLOOR, highlightthickness=0)
        self.scene.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.caption = tk.Label(scene_card, text="", fg=TEXT, bg=CARD, font=(FONT, 11))
        self.caption.pack(anchor="w", padx=12, pady=8)

        row = tk.Frame(self.frame, bg=BG)
        row.pack(fill=tk.BOTH, expand=True)

        pad_card = tk.Frame(row, bg=CARD)
        pad_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), pady=6)
        section_title(pad_card, "WALK  \u00B7  hold to move")
        grid = tk.Frame(pad_card, bg=CARD)
        grid.pack(padx=16, pady=(0, 14))
        self.pad_btns = {}
        for r, line in enumerate(PAD):
            for c, cell in enumerate(line):
                if cell is None:
                    tk.Frame(grid, bg=CARD, width=70, height=10).grid(row=r, column=c)
                    continue
                label, letter = cell
                stop = letter == "S"
                b = button(grid, label, font=(FONT, 16), width=4,
                           activebackground=(ROSE if stop else ACCENT), activeforeground=BG)
                b.grid(row=r, column=c, padx=3, pady=3, ipady=8)
                b.bind("<ButtonPress-1>", lambda e, d=letter: self.pad_press(d))
                b.bind("<ButtonRelease-1>", lambda e: self.pad_release())
                self.pad_btns[letter] = b

        ex_card = tk.Frame(row, bg=CARD)
        ex_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        section_title(ex_card, "SPEED")
        ex = tk.Frame(ex_card, bg=CARD)
        ex.pack(fill=tk.X, padx=16, pady=(0, 14))
        sp = tk.Frame(ex, bg=CARD); sp.pack(fill=tk.X)
        self.speed_btns = []
        for i in range(10):
            b = button(sp, str(i), command=lambda v=i: self.set_level(v),
                       font=(FONT, 9), padx=0, pady=4)
            b.grid(row=0, column=i, sticky="ew", padx=1)
            sp.columnconfigure(i, weight=1, uniform="speed")
            self.speed_btns.append(b)
        self.speed_lbl = tk.Label(ex, text="", fg=DIM, bg=CARD, font=(FONT, 9))
        self.speed_lbl.pack(anchor="w", pady=(6, 0))
        tk.Label(ex, text="Otto finishes the step he is on, then stands\n"
                          "or turns. One step takes about 2 seconds.",
                 fg=DIM, bg=CARD, font=(FONT, 9), justify=tk.LEFT).pack(anchor="w", pady=(10, 0))
        self.says = says_label(ex)
        self.refresh_buttons()

    @staticmethod
    def draw_icon(c):
        c.create_rectangle(16, 6, 48, 30, fill=SAND, outline="")
        c.create_oval(20, 12, 30, 22, fill=INPUT, outline="")
        c.create_oval(34, 12, 44, 22, fill=INPUT, outline="")
        c.create_rectangle(20, 30, 44, 42, fill=blend(SAND, BG, 0.25), outline="")
        c.create_rectangle(22, 42, 28, 52, fill=DIM, outline="")
        c.create_rectangle(36, 42, 42, 52, fill=DIM, outline="")
        c.create_rectangle(16, 52, 30, 58, fill=ACCENT, outline="")
        c.create_rectangle(34, 52, 48, 58, fill=ACCENT, outline="")

    # ------------------------------------------------------------
    # INPUT
    # ------------------------------------------------------------
    def pad_press(self, letter):
        self.pad_dir = letter
        self.update_walk()

    def pad_release(self):
        self.pad_dir = None
        self.update_walk()

    def key_down(self, k):
        if k in KEYS:
            self.held.append(KEYS[k])
            self.update_walk()
        elif k == "space":
            self.held.clear()
            self.pad_dir = None
            self.update_walk()
        elif len(k) == 1 and k.isdigit():
            self.set_level(int(k))

    def key_up(self, k):
        if k in KEYS and KEYS[k] in self.held:
            self.held.remove(KEYS[k])
            self.update_walk()

    def release_all(self):
        self.held.clear()
        self.pad_dir = None
        self.update_walk()

    def update_walk(self):
        d = self.pad_dir or (self.held[-1] if self.held else "S")
        if d == self.dir:
            return
        self.dir = d
        self.sim.want = d
        self.app.write(d + "\n")
        self.app.log_msg(f"\u2192 OTTO {NAMES[d].upper() if d != 'S' else 'STOP'}")
        self.refresh_buttons()

    def set_level(self, lvl):
        if lvl == self.level:
            return
        self.level = lvl
        self.sim.level = lvl
        self.app.write(f"{lvl}\n")
        self.app.log_msg(f"\u2192 OTTO SPEED {lvl}")
        self.refresh_buttons()

    def heartbeat(self):
        if self.dir != "S":                   # keep reminding Otto while an arrow is held
            self.app.write(self.dir + "\n")

    def refresh_buttons(self):
        for letter, b in self.pad_btns.items():
            if letter == self.dir and letter != "S":
                b.config(bg=ACCENT, fg=BG)
            else:
                b.config(bg=INPUT, fg=(ROSE if letter == "S" else TEXT))
        for i, b in enumerate(self.speed_btns):
            on = i == self.level
            b.config(bg=(ACCENT if on else INPUT), fg=(BG if on else MUTED),
                     activebackground=(ACCENT if on else INPUT))
        self.speed_lbl.config(text=f"{TICK_MS[self.level]} ms per degree"
                                   f"{'  (the lecture speed)' if self.level == START_LEVEL else ''}")

    # ------------------------------------------------------------
    # PAGE HOOKS
    # ------------------------------------------------------------
    def on_show(self):
        if self.app.connected:
            self.app.write("?\n")

    def on_connect(self):
        self.app.write(f"{self.level}\n?\n")

    def on_hide(self):
        self.release_all()
        self.app.write("S\n")

    def on_disconnect(self):
        self.app.write("S\n")
        self.says.config(text="Arduino: \u2013", fg=DIM)

    def on_line(self, line):
        if not line.startswith("OTTO:"):
            return False
        rest = line[5:].strip()
        if rest.startswith("?"):
            self.says.config(text=f"Arduino: didn't know the word \"{rest[1:].strip()}\"", fg=ROSE)
        else:
            self.says.config(text=f"Arduino: Otto is {'walking ' if rest != 'S' else ''}"
                                  f"{NAMES.get(rest, rest)}", fg=ACCENT)
        return True

    # ------------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------------
    def animate(self):
        self.t += 0.05
        self.sim.run(50)
        self.draw()

    def draw(self):
        c = self.scene
        c.delete("all")
        W = c.winfo_width()
        W = W if W > 50 else 600
        s = self.sim.servo

        # ---- Otto (front view): feet tilt with pins 5/11, legs swing with pins 6/9 ----
        cx, base = W * 0.32, 250
        lean = ((s[5] - 90) + (s[11] - 90)) * 0.12           # the whole body leans with the feet
        c.create_line(cx - 120, base + 14, cx + 120, base + 14, fill=blend(FLOOR, DIM, 0.6), width=2)

        def rot(x, y):
            a = math.radians(lean)
            dx, dy = x - cx, y - base
            return cx + dx * math.cos(a) - dy * math.sin(a), base + dx * math.sin(a) + dy * math.cos(a)

        def rect(x0, y0, x1, y1, **kw):
            pts = [rot(x0, y0), rot(x1, y0), rot(x1, y1), rot(x0, y1)]
            c.create_polygon([v for p in pts for v in p], **kw)

        for side, foot, leg in ((-1, 5, 6), (1, 11, 9)):
            lx = cx + side * 28 + (s[leg] - 90) * 0.35 * side      # leg swing
            rect(lx - 9, base - 70, lx + 9, base - 10, fill=DIM, outline="")
            # foot tilts with its servo
            a = math.radians((s[foot] - 90) * 0.6)
            fx, fy = rot(lx, base)
            pts = []
            for px, py in ((-26, -8), (26, -8), (26, 8), (-26, 8)):
                pts += [fx + px * math.cos(a) - py * math.sin(a), fy + px * math.sin(a) + py * math.cos(a)]
            c.create_polygon(pts, fill=ACCENT, outline="")
        rect(cx - 52, base - 120, cx + 52, base - 70, fill=blend(SAND, BG, 0.25), outline="")
        rect(cx - 60, base - 205, cx + 60, base - 120, fill=SAND, outline="")
        for ex in (-28, 28):
            x, y = rot(cx + ex, base - 165)
            c.create_oval(x - 20, y - 20, x + 20, y + 20, fill=INPUT, outline="")
            c.create_oval(x - 8, y - 8, x + 8, y + 8, fill=blend(INPUT, BLUE, 0.5), outline="")

        # ---- servo dials ----
        dials = [(5, "foot"), (11, "foot"), (6, "leg"), (9, "leg")]
        x0 = W * 0.62
        for i, (pin, part) in enumerate(dials):
            dx = x0 + (i % 2) * 120
            dy = 90 + (i // 2) * 120
            r = 40
            c.create_arc(dx - r, dy - r, dx + r, dy + r, start=0, extent=180, style="arc",
                         outline=INPUT, width=6)
            ang = math.radians(180 - s[pin])
            c.create_line(dx, dy, dx + r * math.cos(ang), dy - r * math.sin(ang),
                          fill=(ACCENT if s[pin] != 90 else MUTED), width=3)
            c.create_oval(dx - 4, dy - 4, dx + 4, dy + 4, fill=TEXT, outline="")
            c.create_text(dx, dy + 16, text=f"{s[pin]}\u00B0", fill=TEXT, font=("Consolas", 10))
            c.create_text(dx, dy + 34, text=f"pin {pin}  {part}", fill=DIM, font=(FONT, 9))

        walk = self.sim.walk
        cap = "Standing" if walk == "S" else f"Walking {NAMES[walk]}"
        if walk != "S" and self.dir == "S":
            cap += "  \u00B7  finishing the step"
        if not self.app.connected:
            cap += "      practice"
        self.caption.config(text=cap)
