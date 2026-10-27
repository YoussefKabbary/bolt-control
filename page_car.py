# -*- coding: utf-8 -*-
"""
CAR page: drive Bolt (car_firmware/car_firmware.ino).

  - 8 directions + stop: hold a button / key to drive, let go to stop
  - handbrake (drift), lights, horn, speed 0-9
  - same letters as the phone "Car Controller" app: F B L R S, X/x, Y, 0-9

KEYBOARD
  W A S D  or arrows   drive   (W+D = forward-right, S+A = back-left ...)
  SPACE                handbrake (hold while turning to drift)
  H                    horn (hold)
  L                    lights on/off
  0-9                  speed
"""

import tkinter as tk
import math
import re

from ui import (BG, CARD, INPUT, TEXT, MUTED, DIM, ACCENT, BLUE, SAND, ROSE, FLOOR, GRID,
                SMOKE, FONT, FONT_B, blend, button, section_title, says_label, Page)

# speed level -> PWM, same numbers as the firmware
SPEED_MIN, SPEED_MAX = 100, 255
START_LEVEL = 3

# (forward/back, right/left) -> letter
DIRS = {
    ( 1,  0): "F", (-1,  0): "B", (0,  1): "R", (0, -1): "L", (0, 0): "S",
    ( 1,  1): "I", ( 1, -1): "G", (-1, 1): "J", (-1, -1): "H",
}
NAMES = {"F": "FORWARD", "B": "BACK", "L": "LEFT", "R": "RIGHT", "S": "STOP",
         "G": "FORWARD-LEFT", "I": "FORWARD-RIGHT", "H": "BACK-LEFT", "J": "BACK-RIGHT"}

# wheel power in % (left, right), same table as mix() in the firmware
TURN_INNER = 40
MIX = {"F": (100, 100), "B": (-100, -100), "R": (100, 0), "L": (0, 100), "S": (0, 0),
       "I": (100, TURN_INNER), "G": (TURN_INNER, 100),
       "J": (-100, -TURN_INNER), "H": (-TURN_INNER, -100)}

# keyboard -> (forward/back, right/left)
KEYS = {"w": (1, 0), "up": (1, 0), "s": (-1, 0), "down": (-1, 0),
        "d": (0, 1), "right": (0, 1), "a": (0, -1), "left": (0, -1)}

# on-screen pad: (label, letter), row by row
PAD = [
    [("\u25E4", "G"), ("\u25B2", "F"), ("\u25E5", "I")],
    [("\u25C0", "L"), ("\u25A0", "S"), ("\u25B6", "R")],
    [("\u25E3", "H"), ("\u25BC", "B"), ("\u25E2", "J")],
]


def speed_pwm(level):
    return SPEED_MIN + level * (SPEED_MAX - SPEED_MIN) // 9


class CarPage(Page):
    key = "car"
    title = "Car"
    blurb = "Drive Bolt in 8 directions, drift, lights and horn"
    sketch = "car_firmware.ino"
    keys_help = ("W A S D / arrows  drive     Space  handbrake\n"
                 "H  horn     L  lights     0-9  speed")

    def __init__(self, app, parent):
        super().__init__(app, parent)

        # driving state (what the PC is asking the car to do)
        self.keys = set()            # held driving keys
        self.pad_dir = None          # letter held on the on-screen pad
        self.dir = "S"
        self.handbrake = False
        self.horn = False
        self.lights = False
        self.level = START_LEVEL

        # animation state: a top-down car on a floor
        self.t = 0.0
        self.car_x, self.car_y, self.car_a = 300.0, 150.0, 0.0
        self.vx, self.vy = 0.0, 0.0
        self.smoke = []              # [x, y, life]

        self.build_ui()

    @staticmethod
    def draw_icon(c):
        c.create_rectangle(20, 10, 44, 54, fill=SAND, outline="")
        c.create_rectangle(23, 20, 41, 30, fill=INPUT, outline="")
        for x in (12, 44):
            for y in (14, 38):
                c.create_rectangle(x, y, x + 8, y + 12, fill=ACCENT, outline="")

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------
    def build_ui(self):
        # ---- the animated car (top) ----
        scene_card = tk.Frame(self.frame, bg=CARD)
        scene_card.pack(fill=tk.X, pady=6)
        self.scene = tk.Canvas(scene_card, height=300, bg=FLOOR, highlightthickness=0)
        self.scene.pack(fill=tk.X, padx=10, pady=(10, 0))
        cap = tk.Frame(scene_card, bg=CARD); cap.pack(fill=tk.X, padx=12, pady=8)
        self.caption = tk.Label(cap, text="", fg=TEXT, bg=CARD, font=(FONT, 11))
        self.caption.pack(side=tk.LEFT)
        self.wheels_lbl = tk.Label(cap, text="", fg=MUTED, bg=CARD, font=("Consolas", 9))
        self.wheels_lbl.pack(side=tk.RIGHT)

        row = tk.Frame(self.frame, bg=BG)
        row.pack(fill=tk.BOTH, expand=True)

        # ---- drive pad (hold to drive) ----
        pad_card = tk.Frame(row, bg=CARD)
        pad_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), pady=6)
        section_title(pad_card, "DRIVE  \u00B7  hold to move")
        grid = tk.Frame(pad_card, bg=CARD)
        grid.pack(padx=16, pady=(0, 14))
        self.pad_btns = {}
        for r, line in enumerate(PAD):
            for c, (label, letter) in enumerate(line):
                stop = letter == "S"
                b = button(grid, label, font=(FONT, 16), width=4,
                           activebackground=(ROSE if stop else ACCENT), activeforeground=BG)
                b.grid(row=r, column=c, padx=3, pady=3, ipady=8)
                b.bind("<ButtonPress-1>", lambda e, d=letter: self.pad_press(d))
                b.bind("<ButtonRelease-1>", lambda e: self.pad_release())
                self.pad_btns[letter] = b

        # ---- extras: handbrake / horn / lights / speed ----
        ex_card = tk.Frame(row, bg=CARD)
        ex_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        section_title(ex_card, "EXTRAS")
        ex = tk.Frame(ex_card, bg=CARD)
        ex.pack(fill=tk.X, padx=16, pady=(0, 14))

        self.btn_hb = button(ex, "Handbrake / drift      Space", pady=9,
                             activebackground=ROSE, activeforeground=BG)
        self.btn_hb.pack(fill=tk.X, pady=3)
        self.btn_hb.bind("<ButtonPress-1>", lambda e: self.set_handbrake(True))
        self.btn_hb.bind("<ButtonRelease-1>", lambda e: self.set_handbrake(False))

        self.btn_horn = button(ex, "Horn      H", pady=9, activebackground=BLUE, activeforeground=BG)
        self.btn_horn.pack(fill=tk.X, pady=3)
        self.btn_horn.bind("<ButtonPress-1>", lambda e: self.set_horn(True))
        self.btn_horn.bind("<ButtonRelease-1>", lambda e: self.set_horn(False))

        self.btn_lights = button(ex, "", command=self.toggle_lights, pady=9)
        self.btn_lights.pack(fill=tk.X, pady=3)

        tk.Label(ex, text="Speed", fg=MUTED, bg=CARD, font=(FONT, 9)).pack(anchor="w", pady=(10, 4))
        sp = tk.Frame(ex, bg=CARD); sp.pack(fill=tk.X)
        self.speed_btns = []
        for i in range(10):
            b = button(sp, str(i), command=lambda v=i: self.set_level(v),
                       font=(FONT, 9), padx=0, pady=4)
            b.grid(row=0, column=i, sticky="ew", padx=1)
            sp.columnconfigure(i, weight=1, uniform="speed")
            self.speed_btns.append(b)

        self.car_says = says_label(ex)
        self.refresh_buttons()

    def refresh_buttons(self):
        """Highlight the direction being driven, the active extras and the speed."""
        for letter, b in self.pad_btns.items():
            if letter == self.dir and letter != "S":
                b.config(bg=ACCENT, fg=BG)
            else:
                b.config(bg=INPUT, fg=(ROSE if letter == "S" else TEXT))
        self.btn_hb.config(bg=(ROSE if self.handbrake else INPUT), fg=(BG if self.handbrake else TEXT))
        self.btn_horn.config(bg=(BLUE if self.horn else INPUT), fg=(BG if self.horn else TEXT))
        self.btn_lights.config(text=f"Lights: {'on' if self.lights else 'off'}      L",
                               bg=(SAND if self.lights else INPUT),
                               fg=(BG if self.lights else TEXT),
                               activebackground=(SAND if self.lights else INPUT),
                               activeforeground=(BG if self.lights else TEXT))
        for i, b in enumerate(self.speed_btns):
            on = i == self.level
            b.config(bg=(ACCENT if on else INPUT), fg=(BG if on else MUTED),
                     activebackground=(ACCENT if on else INPUT))

    # ------------------------------------------------------------
    # INPUT: pad, keyboard, extras
    # ------------------------------------------------------------
    def release_all(self):
        self.keys.clear()
        self.pad_dir = None
        self.set_horn(False)
        self.set_handbrake(False)
        self.update_drive()

    def key_down(self, k):
        if k in KEYS:
            self.keys.add(k)
            self.update_drive()
        elif k == "space":
            self.set_handbrake(True)
        elif k == "h":
            self.set_horn(True)
        elif k == "l":
            self.toggle_lights()
        elif len(k) == 1 and k.isdigit():
            self.set_level(int(k))

    def key_up(self, k):
        if k in KEYS:
            self.keys.discard(k)
            self.update_drive()
        elif k == "space":
            self.set_handbrake(False)
        elif k == "h":
            self.set_horn(False)

    def pad_press(self, letter):
        self.pad_dir = letter
        self.update_drive()

    def pad_release(self):
        self.pad_dir = None
        self.update_drive()

    def update_drive(self):
        """Work out the direction from the pad / held keys; send it if it changed."""
        if self.pad_dir:
            d = self.pad_dir
        else:
            fb = sum(KEYS[k][0] for k in self.keys)
            rl = sum(KEYS[k][1] for k in self.keys)
            d = DIRS[(max(-1, min(1, fb)), max(-1, min(1, rl)))]
        if d == self.dir:
            return
        self.dir = d
        self.app.write(d)
        self.app.log_msg(f"\u2192 {NAMES[d]}")
        self.refresh_buttons()

    def set_handbrake(self, on):
        if on == self.handbrake:
            return
        self.handbrake = on
        self.app.write("D" if on else "d")
        self.app.log_msg("\u2192 HANDBRAKE ON" if on else "\u2192 HANDBRAKE OFF")
        self.refresh_buttons()

    def set_horn(self, on):
        if on == self.horn:
            return
        self.horn = on
        if on:
            self.app.write("Y")          # the heartbeat keeps sending Y while held
            self.app.log_msg("\u2192 HORN")
        self.refresh_buttons()

    def toggle_lights(self):
        self.lights = not self.lights
        self.app.write("X" if self.lights else "x")
        self.app.log_msg(f"\u2192 LIGHTS {'ON' if self.lights else 'OFF'}")
        self.refresh_buttons()

    def set_level(self, lvl):
        if lvl == self.level:
            return
        self.level = lvl
        self.app.write(str(lvl))
        self.app.log_msg(f"\u2192 SPEED {lvl}")
        self.refresh_buttons()

    def heartbeat(self):
        # resend the whole state: keeps the car going, re-syncs it after a reset or a
        # lost byte, and feeds its failsafe ('#' arms it; if these stop, the car stops)
        self.app.write("#" + self.dir + str(self.level) + ("D" if self.handbrake else "d")
                       + ("X" if self.lights else "x") + ("Y" if self.horn else ""))

    # ------------------------------------------------------------
    # PAGE HOOKS
    # ------------------------------------------------------------
    def on_hide(self):
        self.release_all()
        self.app.write("Sd")                  # make sure the car is stopped

    def on_disconnect(self):
        self.app.write("Sd")                  # stop the car before letting go
        self.car_says.config(text="Arduino: \u2013", fg=DIM)

    def on_line(self, line):
        m = re.search(r"DIR:(\w)\s*\|\s*SPD:(\d)\s*\|\s*HB:(\d)\s*\|\s*LT:(\d)\s*\|\s*HN:(\d)"
                      r"\s*\|\s*LM:(-?\d+)\s*\|\s*RM:(-?\d+)", line)
        if not m:
            return False
        d, spd, hb, lt, hn, lm, rm = m.groups()
        parts = [NAMES.get(d, d).capitalize(), f"speed {spd}"]
        if hb == "1": parts.append("handbrake")
        if lt == "1": parts.append("lights on")
        if hn == "1": parts.append("horn")
        sep = "  \u00B7  "
        self.car_says.config(text=f"Arduino: {sep.join(parts)}\nwheels  L {lm}   R {rm}", fg=ACCENT)
        return True

    # ------------------------------------------------------------
    # ANIMATION  (~20 fps, same rules as the firmware)
    # ------------------------------------------------------------
    def wheel_power(self):
        """Left/right wheel power (-1..1) and whether the wheels are locked."""
        l, r = MIX[self.dir]
        if self.handbrake:
            spin = l - r
            if spin == 0:
                return 0.0, 0.0, True
            s = 1.0 if spin > 0 else -1.0
            return s, -s, False
        k = speed_pwm(self.level) / 255
        return l / 100 * k, r / 100 * k, False

    def animate(self):
        self.t += 0.05
        self.step_car()
        self.draw_scene()

    def step_car(self):
        pl, pr, locked = self.wheel_power()
        self.car_a += (pl - pr) * 0.07                  # turn
        v = (pl + pr) / 2 * 7.0                         # px per frame
        tx, ty = math.sin(self.car_a) * v, -math.cos(self.car_a) * v
        grip = 0.04 if self.handbrake else 0.3          # handbrake = tyres slide
        self.vx += (tx - self.vx) * grip
        self.vy += (ty - self.vy) * grip
        self.car_x += self.vx
        self.car_y += self.vy

        W = self.scene_width()
        H = 300
        if self.car_x < -40: self.car_x = W + 40
        if self.car_x > W + 40: self.car_x = -40
        if self.car_y < -40: self.car_y = H + 40
        if self.car_y > H + 40: self.car_y = -40

        # tyre smoke while drifting / skidding
        sliding = math.hypot(self.vx, self.vy) > 1.0
        if self.handbrake and (abs(pl - pr) > 0 or sliding):
            for lx in (-18, 18):
                x, y = self.to_world(lx, 30)
                self.smoke.append([x, y, 1.0])
        for p in self.smoke:
            p[2] -= 0.04
        self.smoke = [p for p in self.smoke if p[2] > 0][-120:]

        self.wheels_lbl.config(text=self.wheels_text(pl, pr, locked))

    def wheels_text(self, pl, pr, locked):
        if locked:
            return "L  lock    R  lock"
        return f"L {round(pl * 255):+4d}    R {round(pr * 255):+4d}"

    def scene_width(self):
        w = self.scene.winfo_width()
        return w if w > 50 else 600      # not shown yet

    def to_world(self, lx, ly):
        """Car coordinates (x right, y back) -> canvas coordinates."""
        ca, sa = math.cos(self.car_a), math.sin(self.car_a)
        return (self.car_x + lx * ca - ly * sa, self.car_y + lx * sa + ly * ca)

    def poly(self, pts):
        out = []
        for lx, ly in pts:
            out.extend(self.to_world(lx, ly))
        return out

    def draw_scene(self):
        c = self.scene
        c.delete("all")
        W = self.scene_width()
        H = 300

        for x in range(0, W, 40):
            c.create_line(x, 0, x, H, fill=GRID)
        for y in range(0, H, 40):
            c.create_line(0, y, W, y, fill=GRID)

        # smoke puffs (grow and fade into the floor)
        for x, y, life in self.smoke:
            r = 6 + (1 - life) * 14
            c.create_oval(x - r, y - r, x + r, y + r, fill=blend(FLOOR, SMOKE, life * 0.7), outline="")

        # headlight beams
        if self.lights:
            for side in (-1, 1):
                c.create_polygon(self.poly([(side * 12, -34), (side * 6, -34),
                                            (side * 2, -120), (side * 40, -120)]),
                                 fill=blend(FLOOR, SAND, 0.18), outline="")

        pl, pr, locked = self.wheel_power()

        def wheel_color(p):
            if locked: return ROSE
            if p > 0: return ACCENT
            if p < 0: return BLUE
            return DIM

        for lx, p in ((-22, pl), (22, pr)):
            for ly in (-20, 20):
                c.create_polygon(self.poly([(lx - 5, ly - 10), (lx + 5, ly - 10),
                                            (lx + 5, ly + 10), (lx - 5, ly + 10)]),
                                 fill=wheel_color(p), outline="")

        # body + windshield + lights
        c.create_polygon(self.poly([(-18, -34), (18, -34), (18, 34), (-18, 34)]),
                         fill=SAND, outline="")
        c.create_polygon(self.poly([(-14, -18), (14, -18), (12, -6), (-12, -6)]),
                         fill=INPUT, outline="")
        for side in (-1, 1):
            x, y = self.to_world(side * 11, -32)
            c.create_oval(x - 4, y - 4, x + 4, y + 4,
                          fill=("#f2e3bd" if self.lights else blend(SAND, BG, 0.5)), outline="")

        # horn waves
        if self.horn:
            x, y = self.to_world(0, -44)
            for k in range(3):
                r = 12 + k * 10 + (self.t * 60) % 10
                c.create_oval(x - r, y - r, x + r, y + r, outline=blend(FLOOR, BLUE, 0.7), width=2)
            c.create_text(x, y - 46, text="beep", fill=TEXT, font=(FONT_B, 11))

        # caption
        if self.handbrake and not locked:
            cap = "Drifting"
        elif self.handbrake:
            cap = "Handbrake \u2013 wheels locked"
        elif self.dir == "S":
            cap = "Waiting"
        else:
            cap = f"{NAMES[self.dir].capitalize()}  \u00B7  speed {self.level}"
        if not self.app.connected:
            cap += "      practice"
        self.caption.config(text=cap)
