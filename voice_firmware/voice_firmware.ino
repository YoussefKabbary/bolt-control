/*
 * ============================================================
 * VOICE-CONTROLLED BOLT - ARDUINO FIRMWARE  (Robotics Club, Lecture 6)
 * ============================================================
 * Works with the Voice page in Bolt Control AND the phone app's
 * Voice Terminal (Arduino Bluetooth Controller by Giristudio).
 * Same wiring as the book (Chapters 7-9) and car_firmware.ino.
 *
 * WIRING
 *   L298N:   ENA=10(PWM)  IN1=9  IN2=8    -> LEFT motor
 *            IN3=7  IN4=6  ENB=5(PWM)     -> RIGHT motor
 *   HC-05:   RX -> TX(1) ,  TX -> RX(0) ,  GND -> GND ,  VCC -> 5V
 *            Unplug RX/TX while uploading.
 *
 * WORDS (small or capital letters, "go forward" works too)
 *   forward / go   drive forward until "stop"
 *   back           drive backward until "stop"
 *   left / right   turn for TURN_TIME, then stop (0 = keep turning until "stop")
 *   stop           stop
 *
 * ANSWER:  VOICE:<word>   or   VOICE:? <what it got>  for an unknown word
 * ============================================================
 */

// ---------- pins (the book) ----------
#define ENA  10   // left motor speed (PWM)
#define IN1   9   // left motor +
#define IN2   8   // left motor -
#define IN3   7   // right motor +
#define IN4   6   // right motor -
#define ENB   5   // right motor speed (PWM)

// ---------- tuning ----------
const int SPEED = 150;                  // the book's medium speed
const unsigned long TURN_TIME = 600;    // ms a "left" / "right" turn lasts (0 = until "stop")
const unsigned long WORD_GAP  = 120;    // a word ends after a newline or this pause

char heard[24];
byte len = 0;
unsigned long lastChar = 0;

char motion = 'S';                      // what the car is doing now
unsigned long turnStart = 0;

// ============================================================
void setup() {
  Serial.begin(9600);                   // HC-05 talks at 9600
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);
  Stop();
  Serial.println("=== Voice Car Ready ===");
}

void loop() {
  unsigned long now = millis();

  while (Serial.available()) {
    char c = Serial.read();
    lastChar = now;
    if (c == '\n' || c == '\r') endWord();
    else if (len < sizeof(heard) - 1) heard[len++] = tolower(c);
  }
  // the phone app sends no newline: the word ends after a short pause
  if (len > 0 && now - lastChar > WORD_GAP) endWord();

  // turns only last TURN_TIME
  if ((motion == 'L' || motion == 'R') && TURN_TIME > 0 && now - turnStart >= TURN_TIME) {
    Stop();
  }
}

// ============================================================
// WORDS
// ============================================================
void endWord() {
  heard[len] = 0;
  if (len == 0) return;
  len = 0;

  if      (strstr(heard, "stop"))                       { Stop();    answer("stop"); }
  else if (strstr(heard, "forw") || strstr(heard, "go"))  { forward(); answer("forward"); }
  else if (strstr(heard, "back"))                       { back();    answer("back"); }
  else if (strstr(heard, "left"))                       { left();    answer("left"); }
  else if (strstr(heard, "right"))                      { right();   answer("right"); }
  else { Serial.print("VOICE:? "); Serial.println(heard); }
}

void answer(const char *w) {
  Serial.print("VOICE:");
  Serial.println(w);
}

// ============================================================
// MOTORS (the book's direction table)
// ============================================================
void drive(int l1, int l2, int r1, int r2, int speedL, int speedR, char m) {
  digitalWrite(IN1, l1); digitalWrite(IN2, l2);
  digitalWrite(IN3, r1); digitalWrite(IN4, r2);
  analogWrite(ENA, speedL);
  analogWrite(ENB, speedR);
  motion = m;
  turnStart = millis();
}

void forward() { drive(HIGH, LOW, HIGH, LOW, SPEED, SPEED, 'F'); }
void back()    { drive(LOW, HIGH, LOW, HIGH, SPEED, SPEED, 'B'); }
void right()   { drive(HIGH, LOW, LOW, LOW, SPEED, 0, 'R'); }    // only the left wheel moves
void left()    { drive(LOW, LOW, HIGH, LOW, 0, SPEED, 'L'); }    // only the right wheel moves
void Stop()    { drive(LOW, LOW, LOW, LOW, 0, 0, 'S'); }
