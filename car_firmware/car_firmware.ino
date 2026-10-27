/*
 * ============================================================
 * BOLT RC CAR - ARDUINO FIRMWARE
 * ============================================================
 * Same wiring as the Robotics Club book (Chapters 7-9), so the
 * phone "Car Controller" app and car_control.py both work.
 *
 * WIRING
 *   L298N:   ENA=10(PWM)  IN1=9  IN2=8    -> LEFT motor
 *            IN3=7  IN4=6  ENB=5(PWM)     -> RIGHT motor
 *   HC-05:   RX -> TX(1) ,  TX -> RX(0) ,  GND -> GND ,  VCC -> 5V
 *            Unplug RX/TX while uploading. While the HC-05 is plugged
 *            in, USB commands can't reach the Arduino: drive over Bluetooth.
 *   Lights:  LED (+ resistor) on pin 13
 *   Horn:    buzzer on pin 12 (active or passive, both work with tone())
 *
 * COMMANDS (single char, same letters as the phone Car Controller app):
 *   F forward     B back        L left        R right       S stop
 *   G fwd-left    I fwd-right   H back-left   J back-right
 *   0..9 speed    X lights on   x lights off
 *   Y horn        (one Y = short beep, keep sending Y to keep honking)
 *   D handbrake on (drift)      d handbrake off
 *   # keep-alive from car_control.py (arms the failsafe)
 *
 * STATUS LINE (every 0.5s):
 *   DIR:<c> | SPD:<0-9> | HB:<0/1> | LT:<0/1> | HN:<0/1> | LM:<pwm> | RM:<pwm>
 * ============================================================
 */

// ---------- pins ----------
#define ENA        10   // left motor speed (PWM)
#define IN1         9   // left motor +
#define IN2         8   // left motor -
#define IN3         7   // right motor +
#define IN4         6   // right motor -
#define ENB         5   // right motor speed (PWM)
#define LIGHT_PIN  13
#define HORN_PIN   12   // tone() uses Timer2 -> only PWM on pins 3/11 is affected, not 10/5

// ---------- tuning ----------
const int SPEED_MIN   = 100;    // PWM at speed 0 (lower and the motors just hum)
const int SPEED_MAX   = 255;    // PWM at speed 9
const int START_LEVEL = 3;      // speed 3 = ~150 PWM, the book's medium speed

// curves (G/I/H/J): the inner wheel turns at this % of the outer one
const int TURN_INNER  = 40;

// handbrake: lock the wheels for DRIFT_KICK ms, then spin at DRIFT_PWM so the car slides
const int DRIFT_PWM   = 255;
const unsigned long DRIFT_KICK = 120;

const int HORN_FREQ   = 440;    // Hz (only matters for a passive buzzer)
const unsigned long HORN_BEEP = 250;  // one Y = 250 ms of horn

const unsigned long FAILSAFE  = 400;  // car_control.py went quiet this long -> stop
const unsigned long SEND_GAP  = 500;  // status line every 0.5s

// ---------- state ----------
char dir       = 'S';           // current direction letter
int  level     = START_LEVEL;   // speed 0..9
int  speedPwm  = 0;             // PWM for that level (set in setLevel)
bool handbrake = false;
bool lights    = false;
bool horn      = false;
bool failsafeArmed = false;     // only car_control.py sends '#', phone apps never do

int  leftOut  = 0;              // what the motors are doing now (-255..255)
int  rightOut = 0;
bool braking  = false;          // wheels locked by the handbrake

unsigned long kickStart = 0;
unsigned long hornStart = 0;
unsigned long lastByte  = 0;
unsigned long lastSend  = 0;

// ============================================================
void setup() {
  Serial.begin(9600);           // HC-05 talks at 9600 too

  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(LIGHT_PIN, OUTPUT);
  pinMode(HORN_PIN, OUTPUT);

  motor(IN1, IN2, ENA, 0);      // car starts stopped
  motor(IN3, IN4, ENB, 0);
  digitalWrite(LIGHT_PIN, LOW);
  setLevel(START_LEVEL);

  Serial.println("=== Bolt Car Ready ===");
}

// ============================================================
void loop() {
  unsigned long now = millis();

  readCommands(now);
  updateHorn(now);
  updateFailsafe(now);
  drive(now);
  sendStatus(now);
}

// ============================================================
// COMMANDS
// ============================================================
void readCommands(unsigned long now) {
  while (Serial.available()) {
    lastByte = now;
    handleCmd((char)Serial.read(), now);
  }
}

void handleCmd(char c, unsigned long now) {
  switch (c) {
    case 'F': case 'B': case 'L': case 'R': case 'S':
    case 'G': case 'I': case 'H': case 'J':
      dir = c; break;

    case 'X': lights = true;  digitalWrite(LIGHT_PIN, HIGH); break;
    case 'x': lights = false; digitalWrite(LIGHT_PIN, LOW);  break;

    case 'Y': hornOn(now); break;

    case 'D':
      if (!handbrake) { handbrake = true; kickStart = now; }  // repeats don't restart the kick
      break;
    case 'd': handbrake = false; break;

    case '#': failsafeArmed = true; break;

    default:
      if (c >= '0' && c <= '9') setLevel(c - '0');
      break;
  }
}

void setLevel(int lvl) {
  level = lvl;
  speedPwm = SPEED_MIN + (long)level * (SPEED_MAX - SPEED_MIN) / 9;
}

// ============================================================
// DRIVING
// ============================================================
// direction letter -> wheel power in % (-100..100), same table as car_control.py
void mix(char d, int &l, int &r) {
  switch (d) {
    case 'F': l =  100;        r =  100;        break;
    case 'B': l = -100;        r = -100;        break;
    case 'R': l =  100;        r =    0;        break;  // book: only the left wheel moves
    case 'L': l =    0;        r =  100;        break;  // book: only the right wheel moves
    case 'I': l =  100;        r =  TURN_INNER; break;  // forward-right curve
    case 'G': l =  TURN_INNER; r =  100;        break;  // forward-left curve
    case 'J': l = -100;        r = -TURN_INNER; break;  // back-right
    case 'H': l = -TURN_INNER; r = -100;        break;  // back-left
    default:  l =    0;        r =    0;        break;  // S
  }
}

void drive(unsigned long now) {
  int l, r;
  mix(dir, l, r);

  if (handbrake) {
    int spin = l - r;   // > 0 turning right, < 0 turning left, 0 = straight/stopped
    // straight + handbrake = lock the wheels; turning = short lock, then drift
    if (spin == 0 || now - kickStart < DRIFT_KICK) { brakeMotors(); return; }
    // wheels turn opposite ways at full power -> the car swings its tail around
    int s = (spin > 0) ? 1 : -1;
    setMotors(s * DRIFT_PWM, -s * DRIFT_PWM);
    return;
  }

  setMotors((long)l * speedPwm / 100, (long)r * speedPwm / 100);
}

void setMotors(int left, int right) {
  if (!braking && left == leftOut && right == rightOut) return;  // nothing changed
  braking  = false;
  leftOut  = left;
  rightOut = right;
  motor(IN1, IN2, ENA, left);
  motor(IN3, IN4, ENB, right);
}

// power > 0 forward, < 0 backward, 0 stop (free wheel)
void motor(int pinPlus, int pinMinus, int pinSpeed, int power) {
  digitalWrite(pinPlus,  power > 0 ? HIGH : LOW);
  digitalWrite(pinMinus, power < 0 ? HIGH : LOW);
  analogWrite(pinSpeed, abs(power));
}

// both inputs HIGH with the enable on = L298N shorts the motor -> wheels lock fast
void brakeMotors() {
  if (braking) return;
  braking  = true;
  leftOut  = 0;
  rightOut = 0;
  digitalWrite(IN1, HIGH); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, HIGH);
  analogWrite(ENA, 255);   analogWrite(ENB, 255);
}

// ============================================================
// HORN
// ============================================================
void hornOn(unsigned long now) {
  hornStart = now;                       // every Y keeps the horn going
  if (!horn) { horn = true; tone(HORN_PIN, HORN_FREQ); }
}

void updateHorn(unsigned long now) {
  if (horn && now - hornStart >= HORN_BEEP) {
    horn = false;
    noTone(HORN_PIN);
  }
}

// ============================================================
// FAILSAFE: car_control.py resends every 100ms. If it goes quiet
// (Bluetooth dropped, laptop closed) the car stops by itself.
// ============================================================
void updateFailsafe(unsigned long now) {
  if (failsafeArmed && now - lastByte > FAILSAFE) {
    failsafeArmed = false;               // disarm so the phone app still works after
    dir = 'S';
    handbrake = false;
    Serial.println("FAILSAFE:STOP");
  }
}

// ============================================================
// STATUS OUTPUT
// ============================================================
void sendStatus(unsigned long now) {
  if (now - lastSend < SEND_GAP) return;
  lastSend = now;

  Serial.print("DIR:");    Serial.print(dir);
  Serial.print(" | SPD:"); Serial.print(level);
  Serial.print(" | HB:");  Serial.print(handbrake ? 1 : 0);
  Serial.print(" | LT:");  Serial.print(lights ? 1 : 0);
  Serial.print(" | HN:");  Serial.print(horn ? 1 : 0);
  Serial.print(" | LM:");  Serial.print(leftOut);
  Serial.print(" | RM:");  Serial.println(rightOut);
}
