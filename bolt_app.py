#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOLT CONTROL (bolt_app.py)
======================================================
Robotics Club control panel for the PC. Pick a project on the home screen,
connect to its Arduino over USB or HC-05 Bluetooth, and control it.

  Car    car_firmware/car_firmware.ino      drive in 8 directions, drift, lights, horn
  Otto   otto_firmware/otto_firmware.ino    walk Otto with the arrows
  Voice  voice_firmware/voice_firmware.ino  say "forward", "left", "stop"... (car, or Otto
         with otto_firmware.ino)
  LED    led_firmware/led_firmware.ino      one LED on / off (same as the phone LED/Lamp)
  RGB    rgb_firmware/rgb_firmware.ino      any color on an RGB LED
  Terminal  any sketch                      send anything, see every answer (Serial Monitor)

Every page works offline too (practice mode). The connection part (USB dropdown,
Bluetooth scan, read/send, log) is taken from aquarium_kids.py.
"""

import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime

from ui import (BG, CARD, INPUT, HOVER, TEXT, MUTED, DIM, ACCENT, ROSE, FLOOR,
                FONT, FONT_B, button, card)
from page_car import CarPage
from page_otto import OttoPage
from page_voice import VoicePage
from page_led import LedPage
from page_rgb import RgbPage
from page_terminal import TerminalPage

BAUD = 9600
TICK_MS = 100          # pages with a heartbeat (the car) resend this often
FRAME_MS = 50          # animation speed (~20 fps)

PAGES = [CarPage, OttoPage, VoicePage, LedPage, RgbPage, TerminalPage]


class BoltApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bolt Control")
        self.root.geometry("1040x760")
        self.root.minsize(960, 700)
        self.root.config(bg=BG)

        # serial state
        self.ser = None
        self.connected = False
        self.stop_read = False

        self.pages = {}              # key -> page, built the first time it opens
        self.page = None             # page on screen (None = home)
        self.held = set()            # keys held down (to skip Windows auto-repeat)

        self.build_header()
        self.home = tk.Frame(self.root, bg=BG)
        self.work = tk.Frame(self.root, bg=BG)
        self.build_home()
        self.build_work()
        self.refresh_ports()
        self.show_home()

        self.scan_on = True
        threading.Thread(target=self.scan_loop, daemon=True).start()

        self.root.bind_all("<KeyPress>", self.key_down)
        self.root.bind_all("<KeyRelease>", self.key_up)
        # window lost focus -> keys are no longer held, stop whatever they were doing
        self.root.bind_all("<FocusOut>", lambda e: self.root.after(30, self._check_focus))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.animate()
        self.tick()

    # ------------------------------------------------------------
    # HEADER / HOME / PAGES
    # ------------------------------------------------------------
    def build_header(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill=tk.X, padx=20, pady=(14, 8))
        self.back_btn = button(head, "\u2039  Home", command=self.show_home, fg=MUTED,
                               padx=12, pady=4)
        self.title_lbl = tk.Label(head, text="Bolt Control", fg=TEXT, bg=BG, font=(FONT_B, 17))
        self.title_lbl.pack(side=tk.LEFT)
        self.status = tk.Label(head, text="\u25CF  Not connected  \u00B7  practice", fg=ROSE,
                               bg=BG, font=(FONT, 10))
        self.status.pack(side=tk.RIGHT)

    def build_home(self):
        wrap = tk.Frame(self.home, bg=BG)
        wrap.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(wrap, text="Choose a project", fg=MUTED, bg=BG,
                 font=(FONT, 11)).pack(anchor="w", padx=8, pady=(0, 6))
        grid = tk.Frame(wrap, bg=BG)
        grid.pack()
        for i, cls in enumerate(PAGES):
            self.home_card(grid, cls).grid(row=i // 3, column=i % 3, padx=8, pady=8)
        tk.Label(wrap, text="Upload the sketch named on the card to the Arduino, "
                            "then open the page and connect.",
                 fg=DIM, bg=BG, font=(FONT, 9)).pack(anchor="w", padx=8, pady=(6, 0))

    def home_card(self, parent, cls):
        f = tk.Frame(parent, bg=CARD, width=310, height=170, cursor="hand2")
        icon = tk.Canvas(f, width=64, height=64, bg=CARD, highlightthickness=0)
        icon.place(x=20, y=22)
        cls.draw_icon(icon)
        tk.Label(f, text=cls.title, fg=TEXT, bg=CARD, font=(FONT_B, 14)).place(x=100, y=18)
        tk.Label(f, text=cls.blurb, fg=MUTED, bg=CARD, font=(FONT, 10),
                 wraplength=196, justify=tk.LEFT).place(x=100, y=52)
        tk.Label(f, text=cls.sketch, fg=DIM, bg=CARD, font=("Consolas", 8),
                 wraplength=196, justify=tk.LEFT).place(x=100, y=128)

        parts = [f] + f.winfo_children()

        def paint(color):
            for w in parts:
                w.config(bg=color)

        def leave(e):
            inside = f.winfo_containing(e.x_root, e.y_root)
            if inside not in parts:
                paint(CARD)

        for w in parts:
            w.bind("<Button-1>", lambda e, k=cls.key: self.open_page(k))
            w.bind("<Enter>", lambda e: paint(HOVER))
            w.bind("<Leave>", leave)
        return f

    def build_work(self):
        self.page_host = tk.Frame(self.work, bg=BG)
        self.page_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 8))
        right = tk.Frame(self.work, bg=BG, width=360)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        right.pack_propagate(False)
        self.build_connection(right)

    def open_page(self, key):
        self._leave_page()
        page = self.pages.get(key)
        if page is None:
            cls = next(c for c in PAGES if c.key == key)
            page = cls(self, self.page_host)
            self.pages[key] = page
        self.page = page
        self.home.pack_forget()
        self.work.pack(fill=tk.BOTH, expand=True)
        page.frame.pack(fill=tk.BOTH, expand=True)
        self.back_btn.pack(side=tk.LEFT, padx=(0, 14), before=self.title_lbl)
        self.title_lbl.config(text=page.title)
        self.keys_lbl.config(text=page.keys_help)
        self.root.focus_set()
        page.on_show()

    def show_home(self):
        self._leave_page()
        self.work.pack_forget()
        self.home.pack(fill=tk.BOTH, expand=True)
        self.back_btn.pack_forget()
        self.title_lbl.config(text="Bolt Control")

    def _leave_page(self):
        if self.page:
            self.page.on_hide()          # the car / voice page stops the car here
            self.page.frame.pack_forget()
            self.page = None
        self.held.clear()

    # ------------------------------------------------------------
    # KEYBOARD (forwarded to the page on screen)
    # ------------------------------------------------------------
    def key_down(self, e):
        if isinstance(e.widget, tk.Entry):          # typing in a text box
            return
        k = e.keysym.lower()
        if k in self.held:                          # Windows auto-repeat
            return
        self.held.add(k)
        if self.page and hasattr(self.page, "key_down"):
            self.page.key_down(k)

    def key_up(self, e):
        k = e.keysym.lower()
        if k not in self.held:
            return
        self.held.discard(k)
        if self.page and hasattr(self.page, "key_up"):
            self.page.key_up(k)

    def _check_focus(self):
        try:
            has_focus = self.root.focus_get() is not None
        except Exception:
            has_focus = True     # a dropdown menu is open; focus is still ours
        if not has_focus:
            self.held.clear()
            if self.page and hasattr(self.page, "release_all"):
                self.page.release_all()

    # ------------------------------------------------------------
    # LOOPS
    # ------------------------------------------------------------
    def animate(self):
        if self.page and hasattr(self.page, "animate"):
            self.page.animate()
        self.root.after(FRAME_MS, self.animate)

    def tick(self):
        if self.connected and self.page and hasattr(self.page, "heartbeat"):
            self.page.heartbeat()
        self.root.after(TICK_MS, self.tick)

    # ------------------------------------------------------------
    # CONNECTION PANEL  (from aquarium_kids.py)
    # ------------------------------------------------------------
    def build_connection(self, right):
        usb = card(right, "USB")
        r1 = tk.Frame(usb, bg=CARD); r1.pack(fill=tk.X)
        self.port_var = tk.StringVar()
        self.port_menu = tk.OptionMenu(r1, self.port_var, "")
        self.port_menu.config(bg=INPUT, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
                              relief=tk.FLAT, bd=0, highlightthickness=0, font=(FONT, 10),
                              indicatoron=False, cursor="hand2", takefocus=0)
        self.port_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT,
                                      activeforeground=BG, bd=0)
        self.port_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))
        button(r1, "Refresh", command=self.refresh_ports, fg=MUTED,
               font=(FONT, 9), padx=12).pack(side=tk.LEFT, fill=tk.Y)
        self.port_info = tk.Label(usb, text="0 ports", fg=DIM, bg=CARD, font=(FONT, 9))
        self.port_info.pack(anchor="w", pady=(6, 8))
        self.connect_btn = button(usb, "Connect", command=self.toggle_usb, bg=ACCENT, fg=BG,
                                  activebackground=ACCENT, activeforeground=BG,
                                  font=(FONT_B, 10), pady=8)
        self.connect_btn.pack(fill=tk.X)
        tk.Label(usb, text="USB works only with the HC-05 RX/TX unplugged.",
                 fg=DIM, bg=CARD, font=(FONT, 8)).pack(anchor="w", pady=(8, 0))

        bt = card(right, "BLUETOOTH")
        top = tk.Frame(bt, bg=CARD); top.pack(fill=tk.X)
        self.scan_lbl = tk.Label(top, text="Scanning...", fg=DIM, bg=CARD, font=(FONT, 9))
        self.scan_lbl.pack(side=tk.LEFT)
        button(top, "\u21BB  Rescan", command=self.rescan_bt, fg=MUTED,
               font=(FONT, 9), padx=12, pady=2).pack(side=tk.RIGHT)
        self.bt_frame = tk.Frame(bt, bg=CARD); self.bt_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(bt, text="HC-05 makes 2 COM ports; if one fails, try the other.",
                 fg=DIM, bg=CARD, font=(FONT, 8)).pack(anchor="w", pady=(8, 0))

        logc = card(right, "LOG")
        # no scrollbar (the white Windows one is too loud); the mouse wheel scrolls it
        self.log = tk.Text(logc, height=8, bg=FLOOR, fg=MUTED, relief=tk.FLAT, bd=0,
                           padx=8, pady=6, font=("Consolas", 9), state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True)

        self.keys_lbl = tk.Label(right, text="", fg=DIM, bg=BG, font=(FONT, 9), justify=tk.LEFT)
        self.keys_lbl.pack(anchor="w", pady=(6, 0))
        self.log_msg("Welcome. Connect to Bolt, or try the page offline to practice.")

    def refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        names = [p.device for p in ports]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for n in names:
            menu.add_command(label=n, command=lambda v=n: self.port_var.set(v))
        if names and self.port_var.get() not in names:
            self.port_var.set(names[0])
        self.port_info.config(text=f"{len(names)} ports")
        self.update_bt(ports)

    def rescan_bt(self):
        self.scan_lbl.config(text="Scanning...")
        try:
            ports = list(serial.tools.list_ports.comports())
            self.update_bt(ports)
            self.port_info.config(text=f"{len(ports)} ports")
            self.log_msg("Rescanned devices")
        except Exception as e:
            self.log_msg(f"Rescan error: {e}")

    def scan_loop(self):
        while self.scan_on:
            try:
                ports = list(serial.tools.list_ports.comports())
                self.root.after(0, lambda p=ports: self.update_bt(p))
            except Exception:
                pass
            time.sleep(2)

    def update_bt(self, ports):
        bt = []
        for p in ports:
            blob = (str(p.description) + " " + str(p.hwid)).lower()
            if any(k in blob for k in ("bluetooth", "hc-", "bth", "rfcomm")):
                bt.append(p.device)
        self.scan_lbl.config(text=f"{len(bt)} found" if bt else "Scanning...")
        for w in self.bt_frame.winfo_children():
            w.destroy()
        if not bt:
            tk.Label(self.bt_frame, text="No devices found", fg=DIM, bg=CARD,
                     font=(FONT, 9)).pack(anchor="w", pady=6)
            return
        for dev in bt:
            conn = self.connected and self.ser and getattr(self.ser, "port", None) == dev
            txt = (f"\u2713  Connected  \u00B7  {dev}" if conn else dev)
            button(self.bt_frame, txt, command=lambda d=dev: self.connect_bt(d),
                   bg=(ACCENT if conn else INPUT), fg=(BG if conn else TEXT),
                   activebackground=(ACCENT if conn else HOVER), pady=7).pack(fill=tk.X, pady=3)

    def toggle_usb(self):
        if self.connected:
            self.disconnect()
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showwarning("No Port", "Select a COM port (or Refresh).")
                return
            self.connect(port, "USB")

    def connect_bt(self, dev):
        if self.connected and self.ser and getattr(self.ser, "port", None) == dev:
            self.disconnect(); return
        if self.connected:
            self.disconnect()
        self.connect(dev, "BLUETOOTH")

    def connect(self, port, mode):
        self.log_msg(f"Connecting to {port} ({mode})...")
        try:
            self.ser = serial.Serial(port, BAUD, timeout=1, write_timeout=2)
            time.sleep(1.2)
            try:
                self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
            except Exception:
                pass
        except Exception as e:
            msg = str(e)
            self.log_msg(f"FAILED: {msg}")
            if any(k in msg.lower() for k in ("could not open", "semaphore", "denied")):
                self.log_msg("HINT: port busy / wrong COM. Try the other Bluetooth COM, or close Arduino IDE.")
            messagebox.showerror("Connection Failed", f"{port}\n\n{msg}")
            self.ser = None
            return
        self.connected = True
        self.status.config(text=f"\u25CF  Connected  \u00B7  {port}", fg=ACCENT)
        self.connect_btn.config(text="Disconnect", bg=INPUT, fg=ROSE,
                                activebackground=HOVER, activeforeground=ROSE)
        self.log_msg(f"\u2713 Connected to {port} ({mode})")
        self.stop_read = False
        threading.Thread(target=self.read_loop, daemon=True).start()
        if self.page:
            self.page.on_connect()

    def disconnect(self):
        if self.page and self.ser:
            self.page.on_disconnect()      # last chance to stop the car
        self.stop_read = True
        time.sleep(0.2)
        if self.ser:
            try: self.ser.close()
            except Exception: pass
        self.ser = None
        self.connected = False
        self.status.config(text="\u25CF  Not connected  \u00B7  practice", fg=ROSE)
        self.connect_btn.config(text="Connect", bg=ACCENT, fg=BG,
                                activebackground=ACCENT, activeforeground=BG)
        self.log_msg("Disconnected")

    # ------------------------------------------------------------
    # READ / SEND
    # ------------------------------------------------------------
    def read_loop(self):
        buf = ""
        last = time.time()
        while not self.stop_read and self.ser:
            try:
                n = self.ser.in_waiting
                if n:
                    buf += self.ser.read(n).decode("utf-8", errors="ignore")
                    last = time.time()
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            self.root.after(0, lambda l=line: self.parse(l))
                else:
                    if buf.strip() and time.time() - last > 0.2:   # text with no newline
                        line, buf = buf.strip(), ""
                        self.root.after(0, lambda l=line: self.parse(l))
                    time.sleep(0.03)
            except Exception:
                self.root.after(0, lambda: self.log_msg("Connection lost."))
                self.root.after(0, self.disconnect)
                break

    def parse(self, line):
        if self.page and self.page.on_line(line):
            return
        self.log_msg(f"\u2190 {line}")     # Ready / FAILSAFE / anything a page doesn't use

    def write(self, data):
        """Send text to the Arduino. Does nothing when not connected (practice mode)."""
        if not self.connected or not self.ser:
            return
        try:
            self.ser.write(data.encode())
        except Exception as e:
            self.log_msg(f"Send error: {e}")
            self.disconnect()

    # ------------------------------------------------------------
    # LOG / CLOSE
    # ------------------------------------------------------------
    def log_msg(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.config(state=tk.NORMAL)      # read-only, so typed keys never land here
        self.log.insert(tk.END, f"[{ts}] {msg}\n")
        if int(self.log.index("end-1c").split(".")[0]) > 200:
            self.log.delete("1.0", "50.0")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def on_close(self):
        self.scan_on = False
        self._leave_page()                 # stops the car / the microphone
        self.stop_read = True
        time.sleep(0.2)
        if self.ser:
            try: self.ser.close()
            except Exception: pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BoltApp(root)
    root.mainloop()
