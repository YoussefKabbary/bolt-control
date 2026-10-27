# -*- coding: utf-8 -*-
"""Calm theme, small widget helpers and the Page base class shared by every screen."""

import tkinter as tk

# ---------------- calm theme: muted colors, one soft accent ----------------
BG     = "#1b1f26"
CARD   = "#232831"
INPUT  = "#2c323d"
HOVER  = "#363d4a"
TEXT   = "#d6dbe3"
MUTED  = "#8b94a3"
DIM    = "#5d6675"
ACCENT = "#7fb5a6"     # soft sage: active direction, connect, "Arduino says"
BLUE   = "#8eaed4"     # horn
SAND   = "#d4b483"     # lights, car body, LED glow
ROSE   = "#cf8d8d"     # handbrake, stop, not connected
FLOOR  = "#1e232b"
GRID   = "#262c35"
SMOKE  = "#8a9099"

FONT   = "Segoe UI"
FONT_B = "Segoe UI Semibold"


def blend(c1, c2, t):
    """Color between c1 (t=0) and c2 (t=1)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def button(parent, text, command=None, **kw):
    """Flat, quiet button. Hold-to-use buttons bind press/release instead of command."""
    opts = dict(bg=INPUT, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
                relief=tk.FLAT, bd=0, font=(FONT, 10), cursor="hand2", takefocus=0)
    opts.update(kw)
    if command:
        opts["command"] = command
    return tk.Button(parent, text=text, **opts)


def section_title(parent, text):
    tk.Label(parent, text=text, fg=MUTED, bg=CARD,
             font=(FONT_B, 9)).pack(anchor="w", padx=16, pady=(12, 6))


def card(parent, title, **pack):
    """A titled card packed into parent; returns the inner frame to put widgets in."""
    f = tk.Frame(parent, bg=CARD)
    f.pack(**(pack or dict(fill=tk.X, pady=6)))
    section_title(f, title)
    inner = tk.Frame(f, bg=CARD)
    inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 14))
    return inner


def says_label(parent):
    """The 'Arduino: ...' line every page shows under its controls."""
    lbl = tk.Label(parent, text="Arduino: \u2013", fg=DIM, bg=INPUT, font=(FONT, 9),
                   anchor="w", justify=tk.LEFT, padx=8)
    lbl.pack(fill=tk.X, pady=(10, 0), ipady=5)
    return lbl


class Page:
    """One project screen. BoltApp calls these hooks; pages override what they need.

    app.write(text) sends to the Arduino (does nothing when not connected),
    app.log_msg(text) writes to the log, app.connected says if a port is open.
    """
    key = ""            # name used by BoltApp.open_page()
    title = ""          # header + home card title
    blurb = ""          # one line on the home card
    sketch = ""         # Arduino sketch to upload for this page
    keys_help = ""      # keyboard hint under the log

    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent, bg=BG)

    @staticmethod
    def draw_icon(c):
        """Draw the home-card icon on a 64x64 canvas."""

    def on_show(self): pass
    def on_hide(self): pass
    def on_connect(self): pass
    def on_disconnect(self): pass        # called while the port is still open

    def on_line(self, line):
        """A line from the Arduino. Return True if this page understood it."""
        return False
