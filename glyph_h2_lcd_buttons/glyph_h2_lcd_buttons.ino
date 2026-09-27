// Glyph H2 (ESP32-H2) + 16x2 I2C LCD (PCF8574 backpack) + 3 push buttons
// Pin choices follow the PCBCupid Glyph H2 pinout:
// https://learn.pcbcupid.com/documentation/modules/glyph/glyph-esp32h2/pinouts-h2

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// I2C (board default: SDA = IO4, SCL = IO5)
#define PIN_SDA 4
#define PIN_SCL 5

// Buttons: wired GPIO -> button -> GND, using internal pull-ups (pressed = LOW)
// Avoids IO8/IO9 (strapping/BOOT), IO0 (onboard LED), IO23/24 (UART), IO26/27 (USB)
const uint8_t BTN_PINS[3] = {10, 11, 12};
const char *BTN_NAMES[3] = {"LEFT", "OK", "RIGHT"};

const unsigned long DEBOUNCE_MS = 30;

uint8_t lcdAddr = 0x27;  // Overwritten by the scan below if the LCD answers at 0x3F etc.
LiquidCrystal_I2C *lcd;

bool lastStable[3] = {HIGH, HIGH, HIGH};
bool lastRead[3] = {HIGH, HIGH, HIGH};
unsigned long lastChange[3] = {0, 0, 0};
int counter = 0;

uint8_t findLcdAddress() {
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("I2C device found at 0x%02X\n", addr);
      return addr;
    }
  }
  Serial.println("No I2C device found - check SDA/SCL/VCC/GND wiring");
  return 0x27;
}

void showState(const char *event) {
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(event);
  lcd->setCursor(0, 1);
  lcd->print("Count: ");
  lcd->print(counter);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  for (uint8_t i = 0; i < 3; i++) {
    pinMode(BTN_PINS[i], INPUT_PULLUP);
  }

  Wire.begin(PIN_SDA, PIN_SCL);
  lcdAddr = findLcdAddress();

  lcd = new LiquidCrystal_I2C(lcdAddr, 16, 2);
  lcd->init();
  lcd->backlight();
  showState("Ready");
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
      if (reading == LOW) {  // pressed
        if (i == 0) counter--;
        if (i == 1) counter = 0;
        if (i == 2) counter++;
        Serial.printf("%s pressed, count = %d\n", BTN_NAMES[i], counter);
        showState(BTN_NAMES[i]);
      }
    }
  }
}
