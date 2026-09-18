/*
 * ==============================================================================
 * Project: WS2815 16x14 LED Matrix - Production Receiver Firmware
 * Target:  Arduino Uno R3 (ATmega328P), 16 MHz, 2 KB SRAM
 * Pin:     D6 -> 330 Ohm resistor -> First LED DI
 * Ground:  First LED BI to GND; Uno GND tied to LED 12V Supply GND
 * ==============================================================================
 * SERIAL PROTOCOL SPECIFICATION (115200 Baud, 8N1):
 *
 * Packet Framing:
 *   [0..3] Magic Header: 0xAA 0x55 0x4D 0x58 (ASCII: "\xAA\x55MX")
 *   [4]    Command Byte:
 *            0x01: CMD_FRAME      (Payload: 672 bytes RGB data)
 *            0x02: CMD_CLEAR      (Payload: 0 bytes, clears matrix)
 *            0x03: CMD_PING       (Payload: 0 bytes, keepalive)
 *            0x04: CMD_BRIGHTNESS (Payload: 1 byte, 0..255)
 *   [5..6] Payload Length: uint16_t MSB first (big-endian)
 *   [7..]  Payload Data: [Length bytes]
 *   [N..]  Checksum: uint16_t Fletcher-16 (MSB first) computed over
 *          [Command, Length_MSB, Length_LSB, Payload...]
 *
 * Flow Control & AVR Interrupt Safety:
 *   - FastLED disables AVR interrupts during WS2815 transmission (~7.0 ms).
 *   - To prevent UART RX buffer overflow (ATmega328P buffer is only 64 bytes),
 *     the host MUST use strict half-duplex request-response:
 *       Host sends 1 frame -> Uno validates -> Uno calls show() -> Uno replies 'K'.
 *     Host ONLY sends the next frame after receiving 'K'.
 *   - Replies:
 *       'K' = ACK (Success / Displayed)
 *       'N' = NAK (Checksum mismatch)
 *       'L' = Invalid Length error
 *       'T' = Packet timeout / framing error
 *
 * SRAM Footprint:
 *   - leds array: 224 * 3 = 672 bytes.
 *   - Payload received directly into leds memory (Zero-Copy Architecture).
 *   - Total SRAM consumed: ~880 bytes (< 44% of 2048 B), leaving > 1.1 KB
 *     free stack space. No dynamic memory allocation.
 * ==============================================================================
 */

#include <FastLED.h>

#define LED_PIN          6
#define MATRIX_WIDTH     16
#define MATRIX_HEIGHT    14
#define NUM_LEDS         (MATRIX_WIDTH * MATRIX_HEIGHT) // 224 LEDs
#define COLOR_ORDER      GRB
#define CHIPSET          WS2815
#define BAUD_RATE        115200

#define DEFAULT_BRIGHTNESS 40 // ~15% power on boot. User adjustable via host.
#define COMM_TIMEOUT_MS    5000 // Blackout display after 5s of no communication
#define INTER_BYTE_TIMEOUT 150  // Reset receiver state machine if packet stalls

// Magic synchronization bytes: 0xAA, 0x55, 'M', 'X'
const uint8_t MAGIC_HEADER[4] = { 0xAA, 0x55, 0x4D, 0x58 };

// Supported Protocol Commands
enum Command : uint8_t {
  CMD_FRAME      = 0x01,
  CMD_CLEAR      = 0x02,
  CMD_PING       = 0x03,
  CMD_BRIGHTNESS = 0x04
};

// Receiver State Machine States
enum RxState : uint8_t {
  STATE_WAIT_HEADER,
  STATE_READ_CMD,
  STATE_READ_LEN_MSB,
  STATE_READ_LEN_LSB,
  STATE_READ_PAYLOAD,
  STATE_READ_CHK_MSB,
  STATE_READ_CHK_LSB
};

// Hardware Framebuffer
CRGB leds[NUM_LEDS]; // 672 bytes contiguous memory

// State Machine Variables
RxState rx_state = STATE_WAIT_HEADER;
uint8_t header_matched = 0;
uint8_t rx_cmd = 0;
uint16_t rx_expected_len = 0;
uint16_t rx_payload_bytes = 0;
uint8_t temp_payload_byte = 0; // For 1-byte payloads (e.g. brightness)

// Fletcher-16 Checksum Accumulators
uint8_t chk_c0 = 0;
uint8_t chk_c1 = 0;
uint8_t rx_chk_msb = 0;

// Timing Monitors
unsigned long last_byte_time = 0;
unsigned long last_valid_frame_time = 0;
bool is_blacked_out = false;

// Fletcher-16 update helper
inline void fletcher16_update(uint8_t b) {
  chk_c0 = (chk_c0 + b) % 255;
  chk_c1 = (chk_c1 + chk_c0) % 255;
}

void reset_rx_state() {
  rx_state = STATE_WAIT_HEADER;
  header_matched = 0;
  chk_c0 = 0;
  chk_c1 = 0;
  rx_payload_bytes = 0;
}

void setup() {
  Serial.begin(BAUD_RATE);

  // Initialize FastLED for WS2815
  FastLED.addLeds<CHIPSET, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(DEFAULT_BRIGHTNESS);
  FastLED.clear();
  FastLED.show();

  last_valid_frame_time = millis();
  is_blacked_out = false;

  // Signal to the host computer that Uno has completed reset and is ready
  Serial.print(F("READY\n"));
}

void loop() {
  unsigned long now = millis();

  // 1. Packet Inter-Byte Timeout Check
  if (rx_state != STATE_WAIT_HEADER && (now - last_byte_time > INTER_BYTE_TIMEOUT)) {
    Serial.write('T'); // Inform host of timeout/framing reset
    reset_rx_state();
  }

  // 2. Communication Loss Auto-Blackout Check
  if (!is_blacked_out && (now - last_valid_frame_time > COMM_TIMEOUT_MS)) {
    FastLED.clear();
    FastLED.show();
    is_blacked_out = true;
  }

  // 3. Process incoming Serial bytes
  while (Serial.available() > 0) {
    uint8_t b = Serial.read();
    last_byte_time = millis();

    switch (rx_state) {
      case STATE_WAIT_HEADER:
        if (b == MAGIC_HEADER[header_matched]) {
          header_matched++;
          if (header_matched == 4) {
            rx_state = STATE_READ_CMD;
            chk_c0 = 0;
            chk_c1 = 0;
          }
        } else {
          // Restart match check against first header byte
          header_matched = (b == MAGIC_HEADER[0]) ? 1 : 0;
        }
        break;

      case STATE_READ_CMD:
        rx_cmd = b;
        fletcher16_update(b);
        rx_state = STATE_READ_LEN_MSB;
        break;

      case STATE_READ_LEN_MSB:
        rx_expected_len = ((uint16_t)b) << 8;
        fletcher16_update(b);
        rx_state = STATE_READ_LEN_LSB;
        break;

      case STATE_READ_LEN_LSB:
        rx_expected_len |= b;
        fletcher16_update(b);

        // Validate expected payload length for command
        if (rx_cmd == CMD_FRAME && rx_expected_len != (NUM_LEDS * 3)) {
          Serial.write('L'); // Invalid length
          reset_rx_state();
          break;
        } else if ((rx_cmd == CMD_CLEAR || rx_cmd == CMD_PING) && rx_expected_len != 0) {
          Serial.write('L');
          reset_rx_state();
          break;
        } else if (rx_cmd == CMD_BRIGHTNESS && rx_expected_len != 1) {
          Serial.write('L');
          reset_rx_state();
          break;
        }

        rx_payload_bytes = 0;
        if (rx_expected_len == 0) {
          rx_state = STATE_READ_CHK_MSB;
        } else {
          rx_state = STATE_READ_PAYLOAD;
        }
        break;

      case STATE_READ_PAYLOAD:
        fletcher16_update(b);
        if (rx_cmd == CMD_FRAME) {
          // Direct zero-copy reception into hardware framebuffer
          ((uint8_t*)leds)[rx_payload_bytes] = b;
        } else if (rx_cmd == CMD_BRIGHTNESS) {
          temp_payload_byte = b;
        }
        rx_payload_bytes++;

        if (rx_payload_bytes >= rx_expected_len) {
          rx_state = STATE_READ_CHK_MSB;
        }
        break;

      case STATE_READ_CHK_MSB:
        rx_chk_msb = b;
        rx_state = STATE_READ_CHK_LSB;
        break;

      case STATE_READ_CHK_LSB: {
        uint16_t received_chk = (((uint16_t)rx_chk_msb) << 8) | b;
        uint16_t calculated_chk = (((uint16_t)chk_c1) << 8) | chk_c0;

        if (received_chk == calculated_chk) {
          // Checksum valid: execute command
          if (rx_cmd == CMD_FRAME) {
            FastLED.show();
          } else if (rx_cmd == CMD_CLEAR) {
            FastLED.clear();
            FastLED.show();
          } else if (rx_cmd == CMD_PING) {
            // Keepalive only
          } else if (rx_cmd == CMD_BRIGHTNESS) {
            FastLED.setBrightness(temp_payload_byte);
            FastLED.show();
          }

          last_valid_frame_time = millis();
          is_blacked_out = false;
          Serial.write('K'); // Send ACK after display is safely completed
        } else {
          // Checksum mismatch: do NOT update display
          Serial.write('N'); // Send NAK
        }

        reset_rx_state();
        break;
      }
    }
  }
}
