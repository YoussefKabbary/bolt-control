# -*- coding: utf-8 -*-
"""
TERMINAL page: send anything to the Arduino and see everything it answers,
like the Arduino IDE's Serial Monitor. Works with any sketch at 9600 baud.

  Enter          send
  Up / Down      earlier lines you sent
"""

import tkinter as tk
from datetime import datetime

from ui import (CARD, INPUT, TEXT, MUTED, DIM, ACCENT, ROSE, FLOOR, FONT, FONT_B,
                button, card, Page)

ENDINGS = [("No line ending", ""), ("Newline  \\n", "\n"),
           ("Carriage return  \\r", "\r"), ("Both  \\r\\n", "\r\n")]
MAX_LINES = 500


class TerminalPage(Page):
    key = "terminal"
    title = "Terminal"
    blurb = "Send anything and see what the Arduino answers, like the Serial Monitor"
    sketch = "any sketch  \u00B7  9600 baud"
    keys_help = "Enter  send     Up / Down  earlier lines"

    def __init__(self, app, parent):
        super().__init__(app, parent)
        self.ending = "\n"
        self.history = []
        self.hist_pos = 0

        c = card(self.frame, "SERIAL TERMINAL  \u00B7  9600 baud", fill=tk.BOTH, expand=True, pady=6)
        self.out = tk.Text(c, bg=FLOOR, fg=TEXT, relief=tk.FLAT, bd=0, padx=10, pady=8,
                           font=("Consolas", 10), state=tk.DISABLED, wrap=tk.CHAR)
        self.out.pack(fill=tk.BOTH, expand=True)
        self.out.tag_config("time", foreground=DIM)
        self.out.tag_config("sent", foreground=ACCENT)
        self.out.tag_config("got", foreground=TEXT)
        self.out.tag_config("info", foreground=DIM)
        self.out.tag_config("warn", foreground=ROSE)

        row = tk.Frame(c, bg=CARD); row.pack(fill=tk.X, pady=(10, 0))
        box = tk.Frame(row, bg=INPUT)
        box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry = tk.Entry(box, bg=INPUT, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT,
                              font=("Consolas", 11), bd=0)
        self.entry.pack(fill=tk.X, ipady=8, padx=10)
        self.entry.bind("<Return>", lambda e: self.send())
        self.entry.bind("<Up>", lambda e: self.recall(-1))
        self.entry.bind("<Down>", lambda e: self.recall(1))
        button(row, "Send", command=self.send, bg=ACCENT, fg="#1b1f26", activebackground=ACCENT,
               activeforeground="#1b1f26", font=(FONT_B, 10), padx=20, pady=7).pack(side=tk.LEFT)

        opts = tk.Frame(c, bg=CARD); opts.pack(fill=tk.X, pady=(8, 0))
        self.end_btns = []
        for label, value in ENDINGS:
            b = button(opts, label, command=lambda v=value: self.set_ending(v),
                       font=(FONT, 9), padx=10, pady=4)
            b.pack(side=tk.LEFT, padx=(0, 4))
            self.end_btns.append((b, value))
        button(opts, "Clear", command=self.clear, fg=MUTED, font=(FONT, 9),
               padx=12, pady=4).pack(side=tk.RIGHT)
        self.refresh_endings()
        self.add("info", "Type below and press Enter. Everything the Arduino prints shows up here.")

    @staticmethod
    def draw_icon(c):
        c.create_rectangle(6, 10, 58, 54, fill=INPUT, outline="")
        c.create_line(14, 24, 22, 31, 14, 38, fill=ACCENT, width=3)
        c.create_line(27, 40, 42, 40, fill=TEXT, width=3)

    # ------------------------------------------------------------
    def set_ending(self, value):
        self.ending = value
        self.refresh_endings()
        self.entry.focus_set()

    def refresh_endings(self):
        for b, value in self.end_btns:
            on = value == self.ending
            b.config(bg=(ACCENT if on else INPUT), fg=("#1b1f26" if on else MUTED),
                     activebackground=(ACCENT if on else INPUT))

    def send(self):
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        if not text and not self.ending:
            return
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.hist_pos = len(self.history)
        if not self.app.connected:
            self.add("warn", f"{text}   (not connected, not sent)")
            return
        self.app.write(text + self.ending)
        self.add("sent", "\u2192 " + text)

    def recall(self, step):
        if not self.history:
            return "break"
        self.hist_pos = max(0, min(len(self.history), self.hist_pos + step))
        self.entry.delete(0, tk.END)
        if self.hist_pos < len(self.history):
            self.entry.insert(0, self.history[self.hist_pos])
        return "break"

    def add(self, tag, text):
        out = self.out
        out.config(state=tk.NORMAL)
        out.insert(tk.END, datetime.now().strftime("%H:%M:%S  "), "time")
        out.insert(tk.END, text + "\n", tag)
        lines = int(out.index("end-1c").split(".")[0])
        if lines > MAX_LINES:
            out.delete("1.0", f"{lines - MAX_LINES}.0")
        out.see(tk.END)
        out.config(state=tk.DISABLED)

    def clear(self):
        self.out.config(state=tk.NORMAL)
        self.out.delete("1.0", tk.END)
        self.out.config(state=tk.DISABLED)
        self.entry.focus_set()

    # ------------------------------------------------------------
    # PAGE HOOKS
    # ------------------------------------------------------------
    def on_show(self):
        self.entry.focus_set()

    def on_connect(self):
        self.add("info", "Connected")

    def on_disconnect(self):
        self.add("info", "Disconnected")

    def on_line(self, line):
        self.add("got", "\u2190 " + line)    # everything the Arduino says shows here
        return True
