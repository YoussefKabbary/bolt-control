/*
 * ============================================================
 * RGB LED - ARDUINO FIRMWARE  (Robotics Club)
 * ============================================================
 * Works with the RGB page in Bolt Control. You can also type a
 * color in the Serial Monitor or a phone Bluetooth terminal.
 *
 * WIRING  (RGB LED = 4 legs, the longest one is the common leg)
 *   R leg -> 220 ohm -> pin 9      (PWM ~)
 *   G leg -> 220 ohm -> pin 10     (PWM ~)
 *   B leg -> 220 ohm -> pin 11     (PWM ~)
 *   long leg -> GND  (common cathode)   or  5V (common anode: set COMMON_ANODE below)
 *   HC-05:   RX -> TX(1) ,  TX -> RX(0) ,  GND -> GND ,  VCC -> 5V
 *            Unplug RX/TX while uploading.
 *
 * COMMANDS (one per line)
 *   #RRGGBB      hex color, e.g.  #FF8000  = orange
 *   r,g,b        numbers 0-255, e.g.  255,128,0
 *   ?            ask for the current color
 *
 * ANSWER (after every command):  RGB:r,g,b
 * ============================================================
 */

#define R_PIN  9
#define G_PIN 10
#define B_PIN 11

const bool COMMON_ANODE = false;        // true if the long leg goes to 5V
const unsigned long LINE_GAP = 100;     // a line also ends after this much silence (ms)

int red = 0, green = 0, blue = 0;

char line[16];
byte len = 0;
unsigned long lastChar = 0;

void setup() {
  Serial.begin(9600);                   // HC-05 talks at 9600
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  setColor(0, 0, 0);
  Serial.println("=== RGB Ready ===");
  report();
}

void loop() {
  unsigned long now = millis();

  while (Serial.available()) {
    char c = Serial.read();
    lastChar = now;
    if (c == '\n' || c == '\r') {
      endLine();
    } else if (c == '?' && len == 0) {
      report();
    } else if (len < sizeof(line) - 1) {
      line[len++] = c;
    }
  }

  // terminals that don't send a newline: the line ends after a short pause
  if (len > 0 && now - lastChar > LINE_GAP) endLine();
}

void endLine() {
  line[len] = 0;
  if (len == 0) return;
  len = 0;

  if (line[0] == '#' && strlen(line) == 7) {          // #RRGGBB
    long v = strtol(line + 1, NULL, 16);
    setColor((v >> 16) & 255, (v >> 8) & 255, v & 255);
  } else if (strchr(line, ',')) {                     // r,g,b
    char *g = strchr(line, ',') + 1;
    char *b = strchr(g, ',');
    if (!b) return;
    setColor(atoi(line), atoi(g), atoi(b + 1));
  } else {
    return;                                           // not a color, ignore it
  }
  report();
}

void setColor(int r, int g, int b) {
  red   = constrain(r, 0, 255);
  green = constrain(g, 0, 255);
  blue  = constrain(b, 0, 255);
  analogWrite(R_PIN, COMMON_ANODE ? 255 - red   : red);
  analogWrite(G_PIN, COMMON_ANODE ? 255 - green : green);
  analogWrite(B_PIN, COMMON_ANODE ? 255 - blue  : blue);
}

void report() {
  Serial.print("RGB:");
  Serial.print(red);   Serial.print(',');
  Serial.print(green); Serial.print(',');
  Serial.println(blue);
}
