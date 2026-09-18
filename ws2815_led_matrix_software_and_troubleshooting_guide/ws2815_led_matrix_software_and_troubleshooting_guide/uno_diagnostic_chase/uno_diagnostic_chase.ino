/*
 * ==============================================================================
 * Project: WS2815 16x14 LED Matrix - Hardware Diagnostic Chase
 * Target:  Arduino Uno R3 (ATmega328P), 2 KB SRAM
 * Pin:     D6 -> 330 Ohm resistor -> First LED DI
 * Ground:  First LED BI tied to GND; Uno GND tied to 12V Supply GND
 * ==============================================================================
 * PURPOSE:
 * Standalone diagnostic sketch that requires NO computer, NO Python script, and
 * NO coordinate mapping. It cycles through physical LED indices 0 to 223 one at
 * a time, explicitly clearing all other LEDs to black on every single step.
 *
 * DECISIVE TEST FOR HARDWARE VS. SOFTWARE:
 * 1. If exactly ONE LED illuminates at every step:
 *    - All WS2815 driver ICs, strip junctions (DO->DI, BO->BI), and power rails
 *      are electrically intact.
 *    - Any previously observed double-lighting or scrambled text was caused by
 *      host software mapping or serial stream corruption.
 * 2. If TWO LEDs illuminate simultaneously at any strip junction:
 *    - Indisputable physical fault at that junction (e.g., solder bridge
 *      between DI and DO, or DI and BI shorted, or a defective WS2815 IC).
 * 3. If the chase halts or flickers beyond index K:
 *    - Broken DI/DO joint, power drop, or disconnected GND at index K.
 *
 * SERIAL CONTROLS (115200 Baud):
 *   'p' - Pause / Resume chase
 *   'n' - Step forward one LED (when paused)
 *   'b' - Step backward one LED (when paused)
 *   '+' - Increase chase speed (decrease delay)
 *   '-' - Decrease chase speed (increase delay)
 *   'r' - Reset chase to index 0
 * ==============================================================================
 */

#include <FastLED.h>

#define LED_PIN          6
#define NUM_LEDS         224
#define STRIP_HEIGHT     14
#define NUM_STRIPS       16
#define COLOR_ORDER      GRB
#define CHIPSET          WS2815

// Initial safe low brightness (0-255). 30 is roughly 12% brightness.
// NOTE: Brightness setting reduces duty cycle; it does NOT replace proper power wiring.
#define INITIAL_BRIGHTNESS 30

CRGB leds[NUM_LEDS];

int current_idx = 0;
bool paused = false;
unsigned long step_delay_ms = 250; // Milliseconds per LED
unsigned long last_step_ms = 0;

void print_status(int idx) {
  int strip = idx / STRIP_HEIGHT;
  int pos_in_strip = idx % STRIP_HEIGHT;
  
  Serial.print(F("[CHASE] Index: "));
  if (idx < 10) Serial.print(F("  "));
  else if (idx < 100) Serial.print(F(" "));
  Serial.print(idx);

  Serial.print(F(" | Strip (Col): "));
  if (strip < 10) Serial.print(F(" "));
  Serial.print(strip);

  Serial.print(F(" | Pos: "));
  if (pos_in_strip < 10) Serial.print(F(" "));
  Serial.print(pos_in_strip);

  if (idx == 0) {
    Serial.println(F(" -> [ORIGIN / TOP-LEFT] (White)"));
  } else if (pos_in_strip == 0) {
    Serial.println(F(" -> [STRIP START / JUNCTION IN] (Green)"));
  } else if (pos_in_strip == STRIP_HEIGHT - 1) {
    Serial.println(F(" -> [STRIP END / JUNCTION OUT] (Red)"));
  } else {
    Serial.println(F(" -> [INTERMEDIATE] (Cyan)"));
  }
}

void show_single_led(int idx) {
  // Explicitly clear ALL LEDs in the buffer to true black (0, 0, 0)
  FastLED.clear();

  // Highlight specific physical positions with distinct diagnostic colors
  int pos_in_strip = idx % STRIP_HEIGHT;
  if (idx == 0) {
    leds[idx] = CRGB::White;  // Origin marker (first LED at data input)
  } else if (pos_in_strip == 0) {
    leds[idx] = CRGB::Green;  // First LED of each vertical strip
  } else if (pos_in_strip == STRIP_HEIGHT - 1) {
    leds[idx] = CRGB::Red;    // Last LED of each vertical strip
  } else {
    leds[idx] = CRGB::Cyan;   // Interior LEDs along each strip
  }

  FastLED.show();
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000) {
    // Wait briefly for serial on boards with native USB
  }

  FastLED.addLeds<CHIPSET, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(INITIAL_BRIGHTNESS);
  FastLED.clear();
  FastLED.show();

  Serial.println(F("\n========================================================"));
  Serial.println(F("  WS2815 16x14 Matrix - Standalone Diagnostic Chase"));
  Serial.println(F("========================================================"));
  Serial.println(F("Total LEDs: 224 (16 strips x 14 LEDs)"));
  Serial.println(F("Data Pin: D6 | Color Order: GRB | Safe Brightness: 30"));
  Serial.println(F("Controls: 'p'=pause/resume, 'n'=next, 'b'=back, '+'=faster, '-'=slower, 'r'=reset"));
  Serial.println(F("OBSERVE: Watch each strip junction. Only ONE LED should be lit."));
  Serial.println(F("========================================================\n"));

  show_single_led(current_idx);
  print_status(current_idx);
  last_step_ms = millis();
}

void loop() {
  // Handle user keyboard input over Serial Monitor
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'p' || c == 'P') {
      paused = !paused;
      Serial.print(F(">>> Chase "));
      Serial.println(paused ? F("PAUSED") : F("RESUMED"));
    } else if (c == 'n' || c == 'N') {
      current_idx = (current_idx + 1) % NUM_LEDS;
      show_single_led(current_idx);
      print_status(current_idx);
    } else if (c == 'b' || c == 'B') {
      current_idx = (current_idx - 1 + NUM_LEDS) % NUM_LEDS;
      show_single_led(current_idx);
      print_status(current_idx);
    } else if (c == '+' || c == '=') {
      if (step_delay_ms > 30) step_delay_ms -= 30;
      Serial.print(F(">>> Step delay: ")); Serial.print(step_delay_ms); Serial.println(F(" ms"));
    } else if (c == '-' || c == '_') {
      step_delay_ms += 50;
      Serial.print(F(">>> Step delay: ")); Serial.print(step_delay_ms); Serial.println(F(" ms"));
    } else if (c == 'r' || c == 'R') {
      current_idx = 0;
      show_single_led(current_idx);
      print_status(current_idx);
      last_step_ms = millis();
    }
  }

  // Step forward automatically if not paused
  if (!paused && (millis() - last_step_ms >= step_delay_ms)) {
    current_idx = (current_idx + 1) % NUM_LEDS;
    show_single_led(current_idx);
    print_status(current_idx);
    last_step_ms = millis();
  }
}
