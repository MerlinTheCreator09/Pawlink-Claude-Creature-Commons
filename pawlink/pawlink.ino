// PawLink - Glyph H2 (ESP32-H2) + 16x2 I2C LCD + 3 push buttons
// Button 1 -> "cancer", Button 2 -> "diabetes", Button 3 -> "treats"
// Each word stays on screen for SHOW_MS, then the LCD returns to "Press a button".
//
// Wiring (see PCBCupid Glyph H2 pinout):
//   LCD VCC -> 3.3V, GND -> GND, SDA -> IO4, SCL -> IO5
//   Button 1: IO10 -> button -> GND
//   Button 2: IO11 -> button -> GND
//   Button 3: IO12 -> button -> GND
//
// Avoid: IO8/IO9 (strapping/BOOT), IO0 (onboard LED), IO23/24 (UART), IO26/27 (USB)

#include <Wire.h>
#include <LiquidCrystal_PCF8574.h>  // https://github.com/mathertel/LiquidCrystal_PCF8574

#define PIN_SDA 4
#define PIN_SCL 5

const uint8_t BTN_PINS[3] = {10, 11, 12};
const char *BTN_TEXT[3] = {"cancer", "diabetes", "treats"};
const char *IDLE_TEXT = "Press a button";

const unsigned long DEBOUNCE_MS = 30;
const unsigned long SHOW_MS = 3000;  // how long a word stays before returning to IDLE_TEXT

LiquidCrystal_PCF8574 *lcd;

bool lastStable[3] = {HIGH, HIGH, HIGH};
bool lastRead[3] = {HIGH, HIGH, HIGH};
unsigned long lastChange[3] = {0, 0, 0};

bool showingWord = false;
unsigned long shownAt = 0;

// Returns the first I2C device address found (the LCD backpack, usually 0x27 or 0x3F)
uint8_t findLcdAddress() {
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("LCD found at 0x%02X\n", addr);
      return addr;
    }
  }
  Serial.println("No I2C device found - check SDA/SCL/VCC/GND wiring");
  return 0x27;
}

// Updates the LCD and mirrors it to serial as "LCD:<text>" for the PawLink web dashboard
void showText(const char *text) {
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(text);
  Serial.printf("LCD:%s\n", text);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  for (uint8_t i = 0; i < 3; i++) {
    pinMode(BTN_PINS[i], INPUT_PULLUP);
  }

  // Idle state should be HIGH (1) for every button; a 0 here means that button
  // reads as pressed with nothing touched -> check its wiring / leg orientation.
  for (uint8_t i = 0; i < 3; i++) {
    lastRead[i] = lastStable[i] = digitalRead(BTN_PINS[i]);
    Serial.printf("Button %d (IO%d) idle state: %d\n", i + 1, BTN_PINS[i], lastStable[i]);
  }

  Wire.begin(PIN_SDA, PIN_SCL);
  lcd = new LiquidCrystal_PCF8574(findLcdAddress());
  lcd->begin(16, 2, Wire);
  lcd->setBacklight(255);
  showText(IDLE_TEXT);
}

void loop() {
  unsigned long now = millis();

  for (uint8_t i = 0; i < 3; i++) {
    bool reading = digitalRead(BTN_PINS[i]);
    if (reading != lastRead[i]) {
      lastRead[i] = reading;
      lastChange[i] = now;
    }
    if (now - lastChange[i] > DEBOUNCE_MS && reading != lastStable[i]) {
      lastStable[i] = reading;
      Serial.printf("Button %d (IO%d) -> %s\n", i + 1, BTN_PINS[i], reading == LOW ? "pressed" : "released");
      if (reading == LOW) {
        showText(BTN_TEXT[i]);
        showingWord = true;
        shownAt = now;
      }
    }
  }

  if (showingWord && now - shownAt >= SHOW_MS) {
    showingWord = false;
    showText(IDLE_TEXT);
  }
}
