# -*- coding: utf-8 -*-
"""
VOICE page: say a word, the PC hears it and sends it, like the phone app's
Voice Terminal (Lecture 6). Works with voice_firmware.ino (Bolt car) and
otto_firmware.ino (Otto).

Each word is sent as text with a newline: "forward\n", "stop\n" ...
You can also click a word, or type any word, without the microphone.

KEYBOARD
  SPACE   send "stop"
"""

import tkinter as tk

from ui import (BG, CARD, INPUT, TEXT, MUTED, DIM, ACCENT, SAND, ROSE, FONT, FONT_B,
                blend, button, card, says_label, Page)
from voice_listener import VoiceListener

WORDS = ["forward", "back", "left", "right", "stop"]
SYNONYMS = {"go": "forward", "backward": "back", "backwards": "back"}
MIN_CONFIDENCE = 0.6           # below this the word is shown but not sent
ARROWS = {"forward": "\u25B2", "back": "\u25BC", "left": "\u25C0", "right": "\u25B6", "stop": "\u25A0"}
OTTO_NAMES = {"F": "walking forward", "B": "walking back", "L": "walking left",
              "R": "walking right", "S": "standing"}


class VoicePage(Page):
    key = "voice"
    title = "Voice"
    blurb = "Say forward, back, left, right or stop to drive Bolt or Otto"
    sketch = "voice_firmware.ino  \u00B7  otto_firmware.ino"
    keys_help = "Space  stop\nClick a word to send it without the microphone."

    def __init__(self, app, parent):
        super().__init__(app, parent)
        self.listener = VoiceListener(WORDS + list(SYNONYMS), self._event)
        self.listening = False
        self.ready = False
        self.last = None             # (word, confidence, sent)
        self.history = []
        self.t = 0.0

        lc = card(self.frame, "LISTEN  \u00B7  English, works offline", pady=6, fill=tk.X)
        self.canvas = tk.Canvas(lc, height=230, bg=CARD, highlightthickness=0)
        self.canvas.pack(fill=tk.X)
        self.canvas.bind("<Button-1>", lambda e: self.toggle_listening() if e.x < 220 else None)
        row = tk.Frame(lc, bg=CARD); row.pack(fill=tk.X, pady=(8, 0))
        self.listen_btn = button(row, "", command=self.toggle_listening, font=(FONT_B, 11),
                                 padx=18, pady=10)
        self.listen_btn.pack(side=tk.LEFT)
        self.status = tk.Label(row, text="", fg=MUTED, bg=CARD, font=(FONT, 10))
        self.status.pack(side=tk.LEFT, padx=14)

        wc = card(self.frame, "WORDS", fill=tk.BOTH, expand=True, pady=6)
        chips = tk.Frame(wc, bg=CARD); chips.pack(fill=tk.X)
        for w in WORDS:
            stop = w == "stop"
            button(chips, f"{ARROWS[w]}  {w}", command=lambda v=w: self.send_word(v),
                   fg=(ROSE if stop else TEXT), activebackground=(ROSE if stop else ACCENT),
                   activeforeground=BG, padx=14, pady=8).pack(side=tk.LEFT, padx=(0, 6))
        tr = tk.Frame(wc, bg=CARD); tr.pack(fill=tk.X, pady=(12, 0))
        box = tk.Frame(tr, bg=INPUT)
        box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry = tk.Entry(box, bg=INPUT, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT,
                              font=(FONT, 11), bd=0)
        self.entry.pack(fill=tk.X, ipady=7, padx=10)
        self.entry.bind("<Return>", lambda e: self.send_typed())
        button(tr, "Send", command=self.send_typed, padx=16, pady=6).pack(side=tk.LEFT)
        tk.Label(wc, text="Type any word, like the phone Voice Terminal.",
                 fg=DIM, bg=CARD, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
        self.says = says_label(wc)
        self.refresh()

    @staticmethod
    def draw_icon(c):
        c.create_oval(24, 6, 40, 22, fill=SAND, outline="")
        c.create_rectangle(24, 14, 40, 34, fill=SAND, outline="")
        c.create_oval(24, 26, 40, 42, fill=SAND, outline="")
        c.create_arc(16, 18, 48, 46, start=180, extent=180, style="arc", outline=ACCENT, width=3)
        c.create_line(32, 46, 32, 56, fill=ACCENT, width=3)
        c.create_line(24, 56, 40, 56, fill=ACCENT, width=3)

    # ------------------------------------------------------------
    # LISTENING
    # ------------------------------------------------------------
    def toggle_listening(self):
        if self.listening:
            self.stop_listening()
        else:
            self.listening = True
            self.ready = False
            self.listener.start()
            self.app.log_msg("Microphone on")
            self.refresh()

    def stop_listening(self):
        if not self.listening:
            return
        self.listening = False
        self.ready = False
        self.listener.stop()
        self.app.log_msg("Microphone off")
        self.refresh()

    def _event(self, kind, text, conf):
        # called from the listener thread: hop over to the Tk thread
        self.app.root.after(0, lambda: self.on_event(kind, text, conf))

    def on_event(self, kind, text, conf):
        if kind == "ready" and self.listening:
            self.ready = True
        elif kind == "heard" and self.listening:
            self.heard(text, conf)
        elif kind == "error":
            self.listening = False
            self.ready = False
            self.status_text = f"Microphone problem: {text}"
            self.app.log_msg(f"Microphone problem: {text}")
        elif kind == "ended" and self.listening:      # stopped by itself
            self.listening = False
            self.ready = False
        self.refresh()

    def heard(self, word, conf):
        w = SYNONYMS.get(word, word)
        if conf < MIN_CONFIDENCE:
            self.last = (w, conf, False)
            self.app.log_msg(f"Not sure: \"{w}\" ({conf:.0%}), not sent")
            self.refresh()
            return
        self.send_word(w, conf)

    # ------------------------------------------------------------
    # SENDING
    # ------------------------------------------------------------
    def send_word(self, word, conf=None):
        word = word.strip().lower()
        if not word:
            return
        self.app.write(word + "\n")
        self.last = (word, conf, True)
        self.history = (self.history + [word])[-6:]
        how = f" ({conf:.0%})" if conf is not None else ""
        self.app.log_msg(f"\u2192 VOICE \"{word}\"{how}")
        self.refresh()

    def send_typed(self):
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        self.send_word(text)
        self.app.root.focus_set()         # give Space back to "stop"

    def key_down(self, k):
        if k == "space":
            self.send_word("stop")

    # ------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------
    status_text = ""

    def refresh(self):
        if self.listening:
            self.listen_btn.config(text="Stop listening", bg=ROSE, fg=BG,
                                   activebackground=ROSE, activeforeground=BG)
            self.status.config(text=("Listening... say a word" if self.ready else "Starting the microphone..."),
                               fg=(ACCENT if self.ready else MUTED))
            self.status_text = ""
        else:
            self.listen_btn.config(text="Start listening", bg=ACCENT, fg=BG,
                                   activebackground=ACCENT, activeforeground=BG)
            self.status.config(text=(self.status_text or "Microphone off"),
                               fg=(ROSE if self.status_text else DIM))
        self.draw()

    def animate(self):
        if self.listening:
            self.t += 0.05
            self.draw()

    def draw(self):
        c = self.canvas
        c.delete("all")
        W = c.winfo_width()
        W = W if W > 50 else 600
        mx, my = 110, 105

        # microphone with soft rings while listening
        if self.listening and self.ready:
            for k in range(3):
                r = 52 + ((self.t * 30 + k * 18) % 54)
                c.create_oval(mx - r, my - r, mx + r, my + r,
                              outline=blend(CARD, ACCENT, max(0.0, 1 - (r - 52) / 54) * 0.7), width=2)
        col = ACCENT if self.listening else DIM
        c.create_oval(mx - 46, my - 46, mx + 46, my + 46, fill=(blend(CARD, ACCENT, 0.15) if self.listening
                                                                 else INPUT), outline="")
        c.create_oval(mx - 13, my - 32, mx + 13, my - 6, fill=col, outline="")
        c.create_rectangle(mx - 13, my - 19, mx + 13, my + 4, fill=col, outline="")
        c.create_oval(mx - 13, my - 9, mx + 13, my + 17, fill=col, outline="")
        c.create_arc(mx - 22, my - 10, mx + 22, my + 26, start=180, extent=180, style="arc",
                     outline=col, width=3)
        c.create_line(mx, my + 26, mx, my + 34, fill=col, width=3)

        # what it heard
        x = 240
        if self.last:
            word, conf, sent = self.last
            c.create_text(x, 70, text=f"{ARROWS.get(word, '')}  {word}", anchor="w",
                          fill=(TEXT if sent else DIM), font=(FONT_B, 30))
            if conf is not None:
                note = f"{conf:.0%} sure" + ("" if sent else "  \u00B7  not sent, say it again")
            else:
                note = "sent by click / typing"
            c.create_text(x, 118, text=note, anchor="w", fill=(MUTED if sent else ROSE), font=(FONT, 10))
        else:
            c.create_text(x, 70, text="Say a word", anchor="w", fill=DIM, font=(FONT_B, 24))
            c.create_text(x, 112, text="forward  \u00B7  back  \u00B7  left  \u00B7  right  \u00B7  stop",
                          anchor="w", fill=DIM, font=(FONT, 10))
        if self.history:
            c.create_text(x, 170, text="  \u00B7  ".join(self.history), anchor="w", fill=DIM, font=(FONT, 10))
        if not self.app.connected:
            c.create_text(W - 12, 12, text="practice", fill=DIM, font=(FONT, 9), anchor="ne")

    # ------------------------------------------------------------
    # PAGE HOOKS
    # ------------------------------------------------------------
    def on_show(self):
        self.draw()

    def on_hide(self):
        self.stop_listening()
        self.app.write("stop\n")              # don't leave the robot driving

    def on_disconnect(self):
        self.app.write("stop\n")
        self.says.config(text="Arduino: \u2013", fg=DIM)

    def on_line(self, line):
        if line.startswith("VOICE:"):
            rest = line[6:].strip()
            if rest.startswith("?"):
                self.says.config(text=f"Arduino: didn't know \"{rest[1:].strip()}\"", fg=ROSE)
            else:
                self.says.config(text=f"Arduino: {rest}", fg=ACCENT)
            return True
        if line.startswith("OTTO:"):
            rest = line[5:].strip()
            if rest.startswith("?"):
                self.says.config(text=f"Otto: didn't know \"{rest[1:].strip()}\"", fg=ROSE)
            else:
                self.says.config(text=f"Otto: {OTTO_NAMES.get(rest, rest)}", fg=ACCENT)
            return True
        return False

