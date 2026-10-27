/*
 * ============================================================
 * LED ON / OFF - ARDUINO FIRMWARE  (Robotics Club, Lecture 8)
 * ============================================================
 * Works with the LED page in Bolt Control AND the phone app's
 * LED/Lamp screen (Arduino Bluetooth Controller by Giristudio).
 *
 * WIRING
 *   LED:    pin 13 -> 220 ohm resistor -> LED long leg (+) ; short leg (-) -> GND
 *   HC-05:  RX -> TX(1) ,  TX -> RX(0) ,  GND -> GND ,  VCC -> 5V
 *           Unplug RX/TX while uploading.
 *
 * COMMANDS (single char)
 *   1  LED on      (ASCII 49)
 *   0  LED off     (ASCII 48)
 *   ?  ask what the LED is doing
 *
 * ANSWER (after every command):  LED:1  or  LED:0
 * ============================================================
 */

#define LED_PIN 13

bool ledOn = false;

void setup() {
  Serial.begin(9600);            // HC-05 talks at 9600
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.println("=== LED Ready ===");
  report();
}

void loop() {
  while (Serial.available()) {
    char data = Serial.read();
    if (data == '1')      setLed(true);
    else if (data == '0') setLed(false);
    else if (data == '?') report();
  }
}

void setLed(bool on) {
  ledOn = on;
  digitalWrite(LED_PIN, on ? HIGH : LOW);
  report();
}

void report() {
  Serial.println(ledOn ? "LED:1" : "LED:0");
}
