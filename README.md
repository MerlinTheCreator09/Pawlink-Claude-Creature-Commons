# PawLink

A three-button pet communication board built for the Claude Creature Commons hackathon. Each button shows a word on a 16x2 LCD, and a local web dashboard mirrors the display live and counts every press.

## Hardware

- PCBCupid **Glyph H2** (ESP32-H2)
- 16x2 I2C LCD (PCF8574 backpack)
- 3 push buttons

### Wiring

| Part       | Glyph H2 pin |
|------------|--------------|
| LCD VCC    | 3.3V         |
| LCD GND    | GND          |
| LCD SDA    | IO4          |
| LCD SCL    | IO5          |
| Button 1   | IO10 → button → GND |
| Button 2   | IO11 → button → GND |
| Button 3   | IO12 → button → GND |

Buttons use the internal pull-ups (pressed = LOW). Avoid IO8/IO9 (strapping/BOOT), IO0 (onboard LED), IO23/24 (UART) and IO26/27 (USB). Pinout reference: [PCBCupid Glyph H2](https://learn.pcbcupid.com/documentation/modules/glyph/glyph-esp32h2/pinouts-h2).

## Repository layout

```
pawlink/                  Main firmware: buttons -> "cancer" / "diabetes" / "treats"
glyph_h2_lcd_buttons/     Hardware test sketch: LEFT/OK/RIGHT counter on the LCD
pawlink_web/              Local dashboard (Python server + HTML)
```

## Firmware

1. Install the ESP32 board package in the Arduino IDE and select the ESP32-H2 board.
2. Install the library **LiquidCrystal_PCF8574** (mathertel) for `pawlink.ino`. The test sketch uses **LiquidCrystal_I2C**.
3. Open `pawlink/pawlink.ino` and upload.

The sketch auto-detects the LCD's I2C address. Each word stays on screen for 3 seconds, then the display returns to "Press a button". Every LCD update is also printed to serial as `LCD:<text>` at 115200 baud, which the dashboard reads.

## Web dashboard

Requires Python 3.

```
cd pawlink_web
pip install -r requirements.txt
python server.py              # auto-detects the ESP32's COM port
python server.py --port COM8  # or pick it explicitly
```

Then open http://localhost:8000. On Windows you can double-click `start_pawlink.bat` instead.

Close the Arduino IDE Serial Monitor first, since only one program can hold the COM port. The server reconnects on its own if the board is unplugged.

Options: `--baud` (default 115200), `--http` (default 8000).
