"""Drive bolt_app.py with a fake serial port and check what every page sends.

Run: python tests/test_app.py   (needs pyserial; opens a Tk window briefly)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tkinter as tk
import bolt_app
import page_car, page_otto, page_rgb, page_voice

fails = []
count = [0]
def check(name, got, want):
    count[0] += 1
    if got != want:
        print(f"FAIL {name}: got {got!r} want {want!r}")
        fails.append(name)

class FakeSer:
    port = "COM99"
    in_waiting = 0
    def __init__(self): self.out = []
    def write(self, b): self.out.append(b.decode())
    def close(self): pass
    def take(self):
        o, self.out = self.out, []
        return o

root = tk.Tk()
app = bolt_app.BoltApp(root)
root.update()

class Ev:
    def __init__(self, k, widget=None): self.keysym = k; self.widget = widget or root
def press(k): app.key_down(Ev(k))
def release(k): app.key_up(Ev(k))

ser = FakeSer()
def connect():
    app.ser = ser; app.connected = True
    if app.page: app.page.on_connect()
    return ser.take()

# ================= home =================
check("starts on home", app.page, None)
check("6 cards", [c.key for c in bolt_app.PAGES], ["car", "otto", "voice", "led", "rgb", "terminal"])

# ================= CAR =================
app.open_page("car"); car = app.page
check("car page open", car.key, "car")
press("w"); release("w")
check("practice: back to S", car.dir, "S")
connect()
combos = [(("w",), "F"), (("s",), "B"), (("a",), "L"), (("d",), "R"),
          (("w", "d"), "I"), (("w", "a"), "G"), (("s", "d"), "J"), (("s", "a"), "H"),
          (("Up", "Right"), "I"), (("Down", "Left"), "H"), (("w", "s"), "S"), (("W",), "F")]
for keys, want in combos:
    for k in keys: press(k)
    check(f"car keys {'+'.join(keys)}", car.dir, want)
    for k in keys: release(k)
    check(f"car keys {'+'.join(keys)} released", car.dir, "S")
ser.take()
press("w"); press("w"); press("w")
check("car auto-repeat sends once", ser.take(), ["F"])
press("d"); check("car w+d", ser.take(), ["I"])
release("w"); check("car let go w", ser.take(), ["R"])
release("d"); check("car let go d", ser.take(), ["S"])
car.pad_press("J"); check("car pad J", ser.take(), ["J"])
car.pad_release(); check("car pad release", ser.take(), ["S"])
press("space"); check("handbrake on", ser.take(), ["D"])
release("space"); check("handbrake off", ser.take(), ["d"])
press("h"); check("horn", ser.take(), ["Y"])
app.tick(); check("heartbeat while honking", ser.take(), ["#S3dxY"])
release("h"); app.tick(); check("heartbeat after horn", ser.take(), ["#S3dx"])
press("l"); release("l"); check("lights on", ser.take(), ["X"])
press("l"); release("l"); check("lights off", ser.take(), ["x"])
press("7"); release("7"); check("speed 7", ser.take(), ["7"])
car.speed_btns[2].invoke(); check("speed button 2", (ser.take(), car.level), (["2"], 2))
car.set_level(7); ser.take()
press("w"); press("d"); press("space"); app.tick()
check("drift sequence", ser.take(), ["F", "I", "D", "#I7Dx"])
check("drift wheels", car.wheel_power(), (1.0, -1.0, False))
release("d"); check("handbrake straight locks", car.wheel_power()[2], True)
release("w"); release("space"); ser.take()
car.pad_press("I")
pwm = page_car.speed_pwm(7)
pl, pr, _ = car.wheel_power()
check("I wheels match firmware", (round(pl * 255), round(pr * 255)), (pwm, pwm * 40 // 100))
car.pad_release(); ser.take()
press("w"); press("space"); press("h"); ser.take()
app.held.clear(); car.release_all()
check("car release_all", (car.dir, car.handbrake, car.horn, ser.take()), ("S", False, False, ["d", "S"]))
app.parse("DIR:I | SPD:7 | HB:1 | LT:1 | HN:0 | LM:255 | RM:-255")
check("car status line", car.car_says.cget("text"),
      "Arduino: Forward-right  \u00B7  speed 7  \u00B7  handbrake  \u00B7  lights on\nwheels  L 255   R -255")
car.pad_press("F")
y0 = car.car_y
for _ in range(10): car.step_car()
check("car moves up", car.car_y < y0, True)
car.pad_release(); ser.take()

# leaving the page stops the car
car.pad_press("F"); ser.take()
app.show_home()
check("leaving car page stops it", ser.take(), ["S", "Sd"])
check("home again", app.page, None)

# ================= OTTO =================
app.open_page("otto"); otto = app.page
check("otto on_show asks", ser.take(), ["?\n"])
press("w"); check("otto forward", ser.take(), ["F\n"])
app.tick(); check("otto heartbeat while held", ser.take(), ["F\n"])
press("a"); check("otto newest key wins", ser.take(), ["L\n"])
release("a"); check("otto back to forward", ser.take(), ["F\n"])
release("w"); check("otto stop on release", ser.take(), ["S\n"])
app.tick(); check("otto no heartbeat when stopped", ser.take(), [])
otto.pad_press("B"); check("otto pad back", ser.take(), ["B\n"])
otto.pad_release(); ser.take()
press("3"); release("3"); check("otto speed", ser.take(), ["3\n"])
press("5"); release("5"); ser.take()
# the simulation walks with the firmware's numbers
sim = page_otto.OttoSim()
sim.want = "F"
seen5, seen6 = set(), set()
for _ in range(2000):
    sim.tick(); seen5.add(sim.servo[5]); seen6.add(sim.servo[6])
check("otto feet range 60..120", (min(seen5), max(seen5)), (60, 120))
check("otto legs range 70..105", (min(seen6 - {90}), max(seen6)), (70, 105))
sim.want = "S"
for _ in range(400): sim.tick()
check("otto stands after stop", (sim.walk, sim.servo), ("S", {5: 90, 11: 90, 6: 90, 9: 90}))
sim2 = page_otto.OttoSim(); sim2.want = "L"
moved = set()
for _ in range(300):
    sim2.tick(); moved |= {p for p, a in sim2.servo.items() if a != 90}
check("otto left walk moves only 5 and 6", moved, {5, 6})
app.parse("OTTO:F"); check("otto says", otto.says.cget("text"), "Arduino: Otto is walking forward")
app.parse("OTTO:? dance"); check("otto unknown word", otto.says.cget("text"), 'Arduino: didn\'t know the word "dance"')
otto.pad_press("R"); ser.take()
app.open_page("led")
check("leaving otto stops it", ser.take()[:2], ["S\n", "S\n"])

# ================= LED =================
led = app.page
check("led asks on show", ser.take(), [])  # (asked already above, see next line)
app.show_home(); app.open_page("led"); check("led asks", ser.take(), ["?"])
app.parse("LED:1"); check("led takes the asked state", led.on, True)
press("space"); release("space"); check("led space toggles off", ser.take(), ["0"])
press("1"); release("1"); check("led 1", ser.take(), ["1"])
press("0"); release("0"); check("led 0", ser.take(), ["0"])
led.btn.invoke(); check("led button", ser.take(), ["1"])
app.parse("LED:0"); check("led unasked answer doesn't flip the page", led.on, True)
check("led says", led.says.cget("text"), "Arduino: LED is off")

# ================= RGB =================
app.open_page("rgb"); rgb = app.page
check("rgb asks", ser.take(), ["?"])
app.parse("RGB:10,20,30"); check("rgb takes the asked color", (rgb.rgb, [s.value for s in rgb.sliders]),
                                 ([10, 20, 30], [10, 20, 30]))
rgb.pick((255, 80, 0), "ORANGE"); check("rgb preset", ser.take(), ["#FF5000\n"])
# throttle: fast changes inside one gap send once now, the last one after the gap
rgb.timer and root.after_cancel(rgb.timer); rgb.timer = None
rgb.set_rgb([1, 2, 3]); rgb.set_rgb([4, 5, 6]); rgb.set_rgb([7, 8, 9])
check("rgb throttle: first now", ser.take(), ["#010203\n"])
root.after(120, root.quit); root.mainloop()
check("rgb throttle: last after gap", ser.take(), ["#070809\n"])
press("space"); release("space"); root.after(80, root.quit); root.mainloop()
check("rgb space = off", ser.take(), ["#000000\n"])
check("hex", page_rgb.hex_color((255, 128, 0)), "#FF8000")

# ================= VOICE =================
app.open_page("voice"); voice = app.page
ser.take()
voice.listening = True
voice.on_event("heard", "forward", 0.93); check("voice heard", ser.take(), ["forward\n"])
voice.on_event("heard", "go", 0.88); check("voice synonym go", ser.take(), ["forward\n"])
voice.on_event("heard", "backward", 0.8); check("voice synonym backward", ser.take(), ["back\n"])
voice.on_event("heard", "left", 0.4); check("voice low confidence not sent", ser.take(), [])
check("voice shows unsure word", voice.last, ("left", 0.4, False))
voice.listening = False
press("space"); release("space"); check("voice space = stop", ser.take(), ["stop\n"])
voice.entry.insert(0, "  Right "); voice.send_typed(); check("voice typed", ser.take(), ["right\n"])
# typing in the box must not trigger page keys
app.key_down(Ev("space", widget=voice.entry)); check("space in entry ignored", ser.take(), [])
app.key_up(Ev("space", widget=voice.entry))
app.parse("VOICE:left"); check("voice says", voice.says.cget("text"), "Arduino: left")
app.parse("OTTO:S"); check("voice otto says", voice.says.cget("text"), "Otto: standing")
check("history", voice.history[-3:], ["back", "stop", "right"])
app.show_home(); check("leaving voice sends stop", ser.take(), ["stop\n"])

# ================= TERMINAL =================
import page_terminal, threading, time as _t
app.open_page("terminal"); term = app.page
ser.take()
NL, CR = chr(10), chr(13)
term.entry.insert(0, "hello"); term.send(); check("terminal newline", ser.take(), ["hello" + NL])
term.set_ending(""); term.entry.insert(0, "F"); term.send(); check("terminal no ending", ser.take(), ["F"])
term.set_ending(CR + NL); term.entry.insert(0, "255,0,0"); term.send(); check("terminal CRLF", ser.take(), ["255,0,0" + CR + NL])
term.set_ending(""); term.send(); check("terminal empty + no ending sends nothing", ser.take(), [])
term.set_ending(NL)
term.recall(-1); check("terminal history up", term.entry.get(), "255,0,0")
term.recall(-1); check("terminal history up again", term.entry.get(), "F")
term.recall(1); term.recall(1); check("terminal history back to empty", term.entry.get(), "")
app.parse("LED:1"); check("terminal shows every line", "LED:1" in term.out.get("1.0", "end"), True)
check("terminal lines not in the log", "LED:1" in app.log.get("1.0", "end"), False)
# space typed in the terminal box must not reach a page
app.key_down(Ev("space", widget=term.entry)); check("space in terminal entry", ser.take(), [])
app.key_up(Ev("space", widget=term.entry))

class ReadSer:
    port = "COM98"
    def __init__(self, chunks): self.chunks = list(chunks)
    @property
    def in_waiting(self): return len(self.chunks[0]) if self.chunks else 0
    def read(self, n): return self.chunks.pop(0)
    def write(self, b): pass
    def close(self): pass
app.ser = ReadSer([b"=== Ready ===\r\nDIR:S", b" | x\r\n", b"no newline here"])
app.stop_read = False
th = threading.Thread(target=app.read_loop, daemon=True); th.start()
root.after(700, root.quit); root.mainloop()          # the real app reads while Tk runs
app.stop_read = True; th.join(1)
root.after(50, root.quit); root.mainloop()
txt = term.out.get("1.0", "end")
check("read: full line", "=== Ready ===" in txt, True)
check("read: line split across chunks", "DIR:S | x" in txt, True)
check("read: text without newline shows after a pause", "no newline here" in txt, True)
app.ser = ser; app.stop_read = False; app.connected = True

# ================= disconnect from a page stops it =================
app.open_page("car"); ser.take()
car.pad_press("F"); ser.take()
sent = ser
app.disconnect()
check("disconnect on car page", sent.take()[:1], ["Sd"])
check("disconnected", app.connected, False)

app.scan_on = False
root.destroy()
print(f"\n{count[0]} checks, " + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
