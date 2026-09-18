# WS2815 16x14 LED Matrix (224 LEDs) Control & Diagnostic Suite

Complete, robust implementation for driving a 16x14 WS2815 addressable RGB LED matrix using an Arduino Uno R3 (ATmega328P) and a Linux host (Raspberry Pi / Orange Pi 5).

## Directory Contents

* **`WS2815_LED_Matrix_Instructions.pdf`**: Complete PDF engineering guide with root-cause analysis, wiring diagrams, diagnostic flowchart, and reference manual.
* **`uno_diagnostic_chase/uno_diagnostic_chase.ino`**: Standalone Arduino chase sketch. Requires no host computer and no matrix mapping. Decisively isolates hardware faults (solder bridges, bad ICs) from software issues.
* **`uno_matrix_receiver/uno_matrix_receiver.ino`**: Production Arduino receiver firmware. Features zero-copy direct-to-framebuffer streaming, Fletcher-16 checksum, half-duplex flow control (immune to AVR interrupt blocking during WS2815 output), and 5-second communication loss auto-blackout.
* **`matrix_controller.py`**: Production Python host controller. Supports 5x7 and 10x14 crisp bitmap font rendering, smooth horizontal scrolling, stationary text, corner diagnostics, row/column grid scans, single-pixel tests, and ANSI 24-bit TrueColor terminal preview.
* **`test_matrix_suite.py`**: Automated test suite for coordinate mapping math, historical bug reproduction, and packet encoding.
* **`test_protocol_simulator.py`**: Software-in-the-loop (SIL) protocol simulation test verifying error injection, checksum failure handling, framing recovery, and timeout handling.

## Quick Start

### 1. Standalone Hardware Chase Test
1. Open `uno_diagnostic_chase/uno_diagnostic_chase.ino` in Arduino IDE.
2. Select **Board: Arduino Uno**, install **FastLED**, and upload.
3. Observe LEDs: exactly ONE LED should light at each step (Index 0 is White, strip starts are Green, strip ends are Red).

### 2. Production Receiver Firmware
1. Open `uno_matrix_receiver/uno_matrix_receiver.ino` in Arduino IDE and upload to the Uno.

### 3. Linux Host Setup & Commands
```bash
pip install -r requirements.txt
sudo usermod -a -G dialout $USER

# Run Corner Test
python3 matrix_controller.py --port /dev/ttyACM0 corners

# Scroll Text (10x14 Full Height Font)
python3 matrix_controller.py --port /dev/ttyACM0 text "HELLO FISHERS" --scale 2 --speed 14

# Terminal ANSI Visual Preview (No hardware required)
python3 matrix_controller.py --no-serial --preview text "OK" --scale 2 --stationary
```
