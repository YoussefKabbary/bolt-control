/*
 * ============================================================
 * OTTO ROBOT - BLUETOOTH + VOICE FIRMWARE  (Robotics Club, Otto Lecture 9)
 * ============================================================
 * Works with the Otto page and the Voice page in Bolt Control, and with the
 * phone app (Car Controller arrows and Voice Terminal words).
 * The walk is the same as the lecture blocks, without delay(), so Otto
 * hears new commands while he walks.
 *
 * WIRING (Arduino Nano)
 *   Servos:  pin 5  + pin 11  = feet  (tilt together, 60..120)
 *            pin 6  + pin 9   = legs  (swing together, 70..105)
 *            left walk moves only 5 + 6, right walk only 11 + 9
 *   HC-05:   RX -> TX(1) ,  TX -> RX(0) ,  GND -> GND ,  VCC -> 5V
 *            (the lecture code reads "serial 0"). Unplug RX/TX while uploading.
 *   Power:   battery (7-20V) -> buck converter input+ / input-
 *            buck output+ (5V) -> servo red wires + Nano 5V ; output- -> GND
 *
 * COMMANDS
 *   letters (Car Controller, Otto page):  F forward  B back  L left  R right
 *            -> keeps walking until  S  (Otto finishes his step, then stands)
 *   words   (Voice Terminal, Voice page): forward / go, back, left, right
 *            -> WORD_STEPS steps, then stands ;  stop -> stands after this step
 *   0..9    speed (5 = the lecture's 0.01 s per degree)
 *   ?       ask what Otto is doing
 *
 * ANSWER:  OTTO:F / OTTO:B / OTTO:L / OTTO:R  while walking,  OTTO:S  standing,
 *          OTTO:? <word>  for a word Otto doesn't know
 * ============================================================
 */

#include <Servo.h>

// ---------- pins ----------
#define FOOT_A   5      // side A = left walk
#define LEG_A    6
#define FOOT_B  11      // side B = right walk
#define LEG_B    9

// ---------- tuning ----------
const int  WORD_STEPS  = 3;              // steps for one spoken word
const int  START_LEVEL = 5;              // speed 5 = 10 ms per degree, like the lecture
const byte TICK_MS[10] = {20, 18, 16, 14, 12, 10, 9, 8, 7, 6};
const unsigned long INPUT_GAP = 80;      // a word / letter ends after a newline or this pause

// ---------- one step = 5 moves (from the lecture blocks) ----------
const byte FEET = 0, LEGS = 1;
struct Move { byte group; int from; int to; };
const Move STEP_FWD[5]  = {{FEET, 90, 60},  {LEGS, 105, 70}, {FEET, 60, 120},
                           {LEGS, 70, 105}, {FEET, 120, 90}};
const Move STEP_BACK[5] = {{FEET, 90, 120}, {LEGS, 105, 70}, {FEET, 120, 60},
                           {LEGS, 70, 105}, {FEET, 60, 90}};

Servo footA, legA, footB, legB;

// ---------- state ----------
char walk = 'S';            // what Otto is doing now
char want = 'S';            // what he was asked to do
int  stepsLeft = -1;        // -1 = keep walking (letters), > 0 = steps left (words)
bool useA = true, useB = true;
const Move *step = STEP_FWD;
byte moveIdx = 0;
int  angle = 90;
byte tickMs = TICK_MS[START_LEVEL];
unsigned long lastTick = 0;

char buf[24];
byte len = 0;
unsigned long lastChar = 0;

// ============================================================
void setup() {
  Serial.begin(9600);                   // HC-05 talks at 9600
  footA.attach(FOOT_A); legA.attach(LEG_A);
  footB.attach(FOOT_B); legB.attach(LEG_B);
  home();                               // the lecture's "origin servo"
  Serial.println("=== Otto Ready ===");
  report();
}

// ============================================================
void loop() {
  unsigned long now = millis();
  readInput(now);

  if (walk == 'S') {
    if (want != 'S') startStep(want, now);
    return;
  }

  if (now - lastTick < tickMs) return;  // one degree every tickMs
  lastTick = now;

  const Move &m = step[moveIdx];
  angle += (m.to > m.from) ? 1 : -1;
  writeGroup(m.group, angle);
  if (angle == m.to) {
    moveIdx++;
    if (moveIdx < 5) angle = step[moveIdx].from;
    else stepDone(now);
  }
}

// ============================================================
// WALKING
// ============================================================
void startStep(char c, unsigned long now) {
  if (c != walk) { walk = c; report(); }
  useA = (c != 'R');                    // left walk: side A only
  useB = (c != 'L');                    // right walk: side B only
  step = (c == 'B') ? STEP_BACK : STEP_FWD;
  moveIdx = 0;
  angle = step[0].from;
  lastTick = now;
}

void stepDone(unsigned long now) {
  if (stepsLeft > 0) stepsLeft--;
  if (want == 'S' || stepsLeft == 0) {  // asked to stop, or the spoken steps are done
    want = 'S';
    walk = 'S';
    home();
    report();
  } else {
    startStep(want, now);               // next step (maybe in a new direction)
  }
}

void writeGroup(byte group, int a) {
  if (group == FEET) {
    if (useA) footA.write(a);
    if (useB) footB.write(a);
  } else {
    if (useA) legA.write(a);
    if (useB) legB.write(a);
  }
}

void home() {
  footA.write(90); legA.write(90);
  footB.write(90); legB.write(90);
}

// ============================================================
// INPUT: single letters (arrows) or words (voice)
// ============================================================
void readInput(unsigned long now) {
  while (Serial.available()) {
    char c = Serial.read();
    lastChar = now;
    if (c == '\n' || c == '\r') endInput();
    else if (len < sizeof(buf) - 1) buf[len++] = c;
  }
  // the phone app sends no newline: the input ends after a short pause
  if (len > 0 && now - lastChar > INPUT_GAP) endInput();
}

void endInput() {
  buf[len] = 0;
  byte n = len;
  len = 0;
  if (n == 0) return;

  bool isWord = false;                  // words have small letters, commands don't
  for (byte i = 0; i < n; i++) if (islower(buf[i])) isWord = true;
  if (!isWord) {
    for (byte i = 0; i < n; i++) letter(buf[i]);
    return;
  }

  for (byte i = 0; i < n; i++) buf[i] = tolower(buf[i]);
  if      (strstr(buf, "stop"))                       { want = 'S'; stepsLeft = -1; }
  else if (strstr(buf, "forw") || strstr(buf, "go"))  spoken('F');   // "forw" also catches typos like "Forwaed"
  else if (strstr(buf, "back"))                       spoken('B');
  else if (strstr(buf, "left"))                       spoken('L');
  else if (strstr(buf, "right"))                      spoken('R');
  else { Serial.print("OTTO:? "); Serial.println(buf); }
}

void letter(char c) {
  if (c == 'F' || c == 'B' || c == 'L' || c == 'R') { want = c; stepsLeft = -1; }
  else if (c == 'S')                  { want = 'S'; stepsLeft = -1; }
  else if (c >= '0' && c <= '9')      tickMs = TICK_MS[c - '0'];
  else if (c == '?')                  report();
}

void spoken(char c) {
  want = c;
  stepsLeft = WORD_STEPS;
}

void report() {
  Serial.print("OTTO:");
  Serial.println(walk);
}
