#!/usr/bin/env python3
"""
==============================================================================
Project: WS2815 16x14 LED Matrix - Host Controller & Diagnostic Suite
==============================================================================
Provides complete matrix control, configuration, font rendering, test patterns,
and half-duplex serial protocol communication with the Arduino Uno R3.
Supports terminal ANSI visual preview without requiring physical hardware.
==============================================================================
"""

import sys
import time
import argparse
import signal
from typing import List, Tuple, Optional

# Optional PySerial import with clean fallback
try:
    import serial
    import serial.tools.list_ports
    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False


# ============================================================================
# 1. 5x7 BITMAP FONT DEFINITIONS (ASCII 32 to 126)
# Each character is defined by 5 column bytes (LSB at top, bit 0 to bit 6).
# ============================================================================
FONT_5X7 = {
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    '!': [0x00, 0x00, 0x5F, 0x00, 0x00],
    '"': [0x00, 0x07, 0x00, 0x07, 0x00],
    '#': [0x14, 0x7F, 0x14, 0x7F, 0x14],
    '$': [0x24, 0x2A, 0x7F, 0x2A, 0x12],
    '%': [0x23, 0x13, 0x08, 0x64, 0x62],
    '&': [0x36, 0x49, 0x55, 0x22, 0x50],
    "'": [0x00, 0x05, 0x03, 0x00, 0x00],
    '(': [0x00, 0x1C, 0x22, 0x41, 0x00],
    ')': [0x00, 0x41, 0x22, 0x1C, 0x00],
    '*': [0x14, 0x08, 0x3E, 0x08, 0x14],
    '+': [0x08, 0x08, 0x3E, 0x08, 0x08],
    ',': [0x00, 0x50, 0x30, 0x00, 0x00],
    '-': [0x08, 0x08, 0x08, 0x08, 0x08],
    '.': [0x00, 0x60, 0x60, 0x00, 0x00],
    '/': [0x20, 0x10, 0x08, 0x04, 0x02],
    '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
    '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
    '2': [0x42, 0x61, 0x51, 0x49, 0x46],
    '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
    '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
    '5': [0x27, 0x45, 0x45, 0x45, 0x39],
    '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
    '7': [0x01, 0x71, 0x09, 0x05, 0x03],
    '8': [0x36, 0x49, 0x49, 0x49, 0x36],
    '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
    ':': [0x00, 0x36, 0x36, 0x00, 0x00],
    ';': [0x00, 0x56, 0x36, 0x00, 0x00],
    '<': [0x08, 0x14, 0x22, 0x41, 0x00],
    '=': [0x14, 0x14, 0x14, 0x14, 0x14],
    '>': [0x00, 0x41, 0x22, 0x14, 0x08],
    '?': [0x02, 0x01, 0x51, 0x09, 0x06],
    '@': [0x32, 0x49, 0x79, 0x41, 0x3E],
    'A': [0x7E, 0x11, 0x11, 0x11, 0x7E],
    'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
    'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
    'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
    'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
    'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
    'G': [0x3E, 0x41, 0x49, 0x49, 0x7A],
    'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
    'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
    'J': [0x20, 0x40, 0x41, 0x3F, 0x01],
    'K': [0x7F, 0x08, 0x14, 0x22, 0x41],
    'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
    'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F],
    'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
    'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
    'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
    'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E],
    'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
    'S': [0x46, 0x49, 0x49, 0x49, 0x31],
    'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
    'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
    'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],
    'W': [0x7F, 0x20, 0x18, 0x20, 0x7F],
    'X': [0x63, 0x14, 0x08, 0x14, 0x63],
    'Y': [0x07, 0x08, 0x70, 0x08, 0x07],
    'Z': [0x61, 0x51, 0x49, 0x45, 0x43],
    '[': [0x00, 0x7F, 0x41, 0x41, 0x00],
    '\\': [0x02, 0x04, 0x08, 0x10, 0x20],
    ']': [0x00, 0x41, 0x41, 0x7F, 0x00],
    '^': [0x04, 0x02, 0x01, 0x02, 0x04],
    '_': [0x40, 0x40, 0x40, 0x40, 0x40],
    '`': [0x00, 0x01, 0x02, 0x04, 0x00],
    'a': [0x20, 0x54, 0x54, 0x54, 0x78],
    'b': [0x7F, 0x48, 0x44, 0x44, 0x38],
    'c': [0x38, 0x44, 0x44, 0x44, 0x20],
    'd': [0x38, 0x44, 0x44, 0x48, 0x7F],
    'e': [0x38, 0x54, 0x54, 0x54, 0x18],
    'f': [0x08, 0x7E, 0x09, 0x01, 0x02],
    'g': [0x0C, 0x52, 0x52, 0x52, 0x3E],
    'h': [0x7F, 0x08, 0x04, 0x04, 0x78],
    'i': [0x00, 0x44, 0x7D, 0x40, 0x00],
    'j': [0x20, 0x40, 0x44, 0x3D, 0x00],
    'k': [0x7F, 0x10, 0x28, 0x44, 0x00],
    'l': [0x00, 0x41, 0x7F, 0x40, 0x00],
    'm': [0x7C, 0x04, 0x18, 0x04, 0x78],
    'n': [0x7C, 0x08, 0x04, 0x04, 0x78],
    'o': [0x38, 0x44, 0x44, 0x44, 0x38],
    'p': [0x7C, 0x14, 0x14, 0x14, 0x08],
    'q': [0x08, 0x14, 0x14, 0x18, 0x7C],
    'r': [0x7C, 0x08, 0x04, 0x04, 0x08],
    's': [0x48, 0x54, 0x54, 0x54, 0x20],
    't': [0x04, 0x3F, 0x44, 0x40, 0x20],
    'u': [0x3C, 0x40, 0x40, 0x20, 0x7C],
    'v': [0x1C, 0x20, 0x40, 0x20, 0x1C],
    'w': [0x3C, 0x40, 0x30, 0x40, 0x3C],
    'x': [0x44, 0x28, 0x10, 0x28, 0x44],
    'y': [0x0C, 0x50, 0x50, 0x50, 0x3C],
    'z': [0x44, 0x64, 0x54, 0x4C, 0x44],
}


# ============================================================================
# 2. CONFIGURABLE MATRIX GEOMETRY
# ============================================================================
class MatrixGeometry:
    """
    Handles coordinate mapping between 2D logical (x, y) space and the 1D physical
    strip indices. Supports configurable width, height, origin corner, strip
    orientation, and serpentine routing without modifying code constants.
    """
    def __init__(
        self,
        width: int = 16,
        height: int = 14,
        first_corner: str = "TOP_LEFT",
        strip_orientation: str = "VERTICAL",
        serpentine: bool = True
    ):
        self.width = width
        self.height = height
        self.num_leds = width * height
        self.first_corner = first_corner.upper()
        self.strip_orientation = strip_orientation.upper()
        self.serpentine = serpentine

        if self.first_corner not in ("TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"):
            raise ValueError(f"Invalid first_corner: {first_corner}")
        if self.strip_orientation not in ("VERTICAL", "HORIZONTAL"):
            raise ValueError(f"Invalid strip_orientation: {strip_orientation}")

    def xy_to_index(self, x: int, y: int) -> int:
        """Map logical coordinate (x, y) to physical 1D LED index (0..num_leds-1)."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Coordinate ({x}, {y}) out of range for {self.width}x{self.height}")

        col = x
        row = y

        if self.strip_orientation == "VERTICAL":
            # Vertical strips run along the columns
            if self.first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
                col = (self.width - 1) - col
            if self.first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
                row = (self.height - 1) - row

            if self.serpentine:
                # Even columns run top-to-bottom, odd columns run bottom-to-top
                if col % 2 == 0:
                    return col * self.height + row
                else:
                    return col * self.height + (self.height - 1 - row)
            else:
                return col * self.height + row

        else: # HORIZONTAL
            # Horizontal strips run along the rows
            if self.first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
                row = (self.height - 1) - row
            if self.first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
                col = (self.width - 1) - col

            if self.serpentine:
                if row % 2 == 0:
                    return row * self.width + col
                else:
                    return row * self.width + (self.width - 1 - col)
            else:
                return row * self.width + col

    def index_to_xy(self, index: int) -> Tuple[int, int]:
        """Reverse map physical index to logical (x, y) coordinate."""
        if not (0 <= index < self.num_leds):
            raise IndexError(f"Index {index} out of range (0..{self.num_leds-1})")

        if self.strip_orientation == "VERTICAL":
            col = index // self.height
            rem = index % self.height
            if self.serpentine and (col % 2 != 0):
                row = (self.height - 1) - rem
            else:
                row = rem

            if self.first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
                col = (self.width - 1) - col
            if self.first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
                row = (self.height - 1) - row
            return (col, row)

        else: # HORIZONTAL
            row = index // self.width
            rem = index % self.width
            if self.serpentine and (row % 2 != 0):
                col = (self.width - 1) - rem
            else:
                col = rem

            if self.first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
                row = (self.height - 1) - row
            if self.first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
                col = (self.width - 1) - col
            return (col, row)

    def create_framebuffer(self) -> List[List[Tuple[int, int, int]]]:
        """Create an empty 2D framebuffer [y][x] initialized to black (0, 0, 0)."""
        return [[(0, 0, 0) for _ in range(self.width)] for _ in range(self.height)]

    def framebuffer_to_payload(
        self,
        fb: List[List[Tuple[int, int, int]]],
        brightness: float = 0.2
    ) -> bytes:
        """
        Convert a 2D logical framebuffer to a 1D physical stream ordered by LED index.
        Applies a safe software brightness scaling (0.0 to 1.0).
        """
        brightness = max(0.0, min(1.0, brightness))
        raw_leds = [(0, 0, 0)] * self.num_leds

        for y in range(self.height):
            for x in range(self.width):
                phys_idx = self.xy_to_index(x, y)
                r, g, b = fb[y][x]
                raw_leds[phys_idx] = (
                    int(r * brightness),
                    int(g * brightness),
                    int(b * brightness)
                )

        # Flatten into byte stream (RGB order per LED)
        payload = bytearray(self.num_leds * 3)
        for i, (r, g, b) in enumerate(raw_leds):
            payload[i * 3 + 0] = r & 0xFF
            payload[i * 3 + 1] = g & 0xFF
            payload[i * 3 + 2] = b & 0xFF
        return bytes(payload)


# ============================================================================
# 3. PROTOCOL & SERIAL DRIVER
# ============================================================================
def fletcher16(data: bytes) -> int:
    """Computes a 16-bit Fletcher checksum over data."""
    c0 = 0
    c1 = 0
    for b in data:
        c0 = (c0 + b) % 255
        c1 = (c1 + c0) % 255
    return (c1 << 8) | c0


class MatrixProtocol:
    MAGIC_HEADER = b"\xAA\x55MX"
    CMD_FRAME = 0x01
    CMD_CLEAR = 0x02
    CMD_PING = 0x03
    CMD_BRIGHTNESS = 0x04

    @classmethod
    def build_packet(cls, cmd: int, payload: bytes = b"") -> bytes:
        length = len(payload)
        header = cls.MAGIC_HEADER
        meta = bytes([cmd, (length >> 8) & 0xFF, length & 0xFF])
        chk = fletcher16(meta + payload)
        chk_bytes = bytes([(chk >> 8) & 0xFF, chk & 0xFF])
        return header + meta + payload + chk_bytes


class SerialMatrixClient:
    """
    Communicates with Arduino Uno R3 over USB Serial at 115200 baud.
    Implements half-duplex request-response flow control to prevent UART
    overflow during FastLED.show() interrupt disables.
    """
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.5):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None

    def connect(self):
        if not HAVE_SERIAL:
            raise RuntimeError("PySerial is not installed. Run 'pip install pyserial' or use --preview.")

        print(f"[Serial] Opening {self.port} at {self.baud} baud...")
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

        # Uno R3 resets via DTR pulse when port opens.
        # Wait up to 3 seconds for Uno to boot and output "READY\n".
        print("[Serial] Waiting for Arduino bootloader & ready signal...")
        start_t = time.time()
        ready_found = False
        while time.time() - start_t < 3.0:
            line = self.ser.readline().decode("latin-1", errors="ignore").strip()
            if "READY" in line:
                ready_found = True
                print("[Serial] Received READY from Arduino.")
                break
            time.sleep(0.05)

        if not ready_found:
            print("[Serial] Warning: READY signal not detected; flushing port buffer.")

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def close(self):
        if self.ser and self.ser.is_open:
            try:
                self.clear_display()
            except Exception:
                pass
            self.ser.close()
            print("[Serial] Port closed.")

    def send_packet(self, packet: bytes, max_retries: int = 3) -> bool:
        if not self.ser or not self.ser.is_open:
            return False

        for attempt in range(max_retries):
            # Flush any stale inbound noise before transmission
            self.ser.reset_input_buffer()
            self.ser.write(packet)
            self.ser.flush()

            # Wait for single-byte ACK from Uno ('K', 'N', 'L', 'T')
            reply = self.ser.read(1)
            if reply == b'K':
                return True
            elif reply == b'N':
                print(f"[Serial] NAK received (checksum error), retry {attempt + 1}/{max_retries}...")
            elif reply == b'L':
                print(f"[Serial] Error: Length rejected by Arduino, retry {attempt + 1}/{max_retries}...")
            elif reply == b'T':
                print(f"[Serial] Error: Timeout reported by Arduino, retry {attempt + 1}/{max_retries}...")
            elif len(reply) == 0:
                print(f"[Serial] Timeout waiting for ACK, retry {attempt + 1}/{max_retries}...")
            else:
                print(f"[Serial] Unexpected reply {reply}, retry {attempt + 1}/{max_retries}...")
            time.sleep(0.05)

        print("[Serial] Failed to transmit packet after retries.")
        return False

    def send_frame(self, payload: bytes) -> bool:
        pkt = MatrixProtocol.build_packet(MatrixProtocol.CMD_FRAME, payload)
        return self.send_packet(pkt)

    def clear_display(self) -> bool:
        pkt = MatrixProtocol.build_packet(MatrixProtocol.CMD_CLEAR)
        return self.send_packet(pkt)


# ============================================================================
# 4. TERMINAL ANSI VISUAL PREVIEW
# ============================================================================
def render_terminal_preview(fb: List[List[Tuple[int, int, int]]], width: int = 16, height: int = 14):
    """
    Renders the exact 2D framebuffer in the terminal using 24-bit TrueColor ANSI
    escape codes. Allows instant visual verification of layout and text.
    """
    lines = []
    header = "   +" + "--" * width + "+"
    lines.append(header)
    for y in range(height):
        row_str = f"{y:2d} |"
        for x in range(width):
            r, g, b = fb[y][x]
            if r == 0 and g == 0 and b == 0:
                row_str += "  " # Dark pixel
            else:
                # ANSI TrueColor 48;2;R;G;B
                row_str += f"\033[48;2;{r};{g};{b}m  \033[0m"
        row_str += "|"
        lines.append(row_str)
    lines.append(header)
    # Print column index indicators at bottom
    col_str = "    "
    for x in range(width):
        col_str += f"{x%10} "
    lines.append(col_str)

    # ANSI home cursor to overwrite preview smoothly
    sys.stdout.write("\033[H" + "\n".join(lines) + "\n")
    sys.stdout.flush()


# ============================================================================
# 5. TEXT & GRAPHICS RENDERING
# ============================================================================
def draw_char_5x7(
    fb: List[List[Tuple[int, int, int]]],
    char: str,
    top_left_x: int,
    top_left_y: int,
    color: Tuple[int, int, int],
    scale: int = 1,
    width: int = 16,
    height: int = 14
):
    cols = FONT_5X7.get(char, FONT_5X7.get('?'))
    for col_idx, col_byte in enumerate(cols):
        for bit_idx in range(7):
            if (col_byte >> bit_idx) & 1:
                for sx in range(scale):
                    for sy in range(scale):
                        px = top_left_x + col_idx * scale + sx
                        py = top_left_y + bit_idx * scale + sy
                        if 0 <= px < width and 0 <= py < height:
                            fb[py][px] = color


def render_text_frame(
    text: str,
    x_offset: int,
    y_offset: int = 0,
    color: Tuple[int, int, int] = (255, 180, 0),
    scale: int = 2,
    spacing: int = 1,
    width: int = 16,
    height: int = 14
) -> List[List[Tuple[int, int, int]]]:
    """Renders text with horizontal offset into a 16x14 framebuffer."""
    fb = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]
    curr_x = x_offset
    char_w = 5 * scale
    char_gap = spacing * scale

    for char in text:
        if curr_x + char_w > 0 and curr_x < width:
            draw_char_5x7(fb, char, curr_x, y_offset, color, scale, width, height)
        curr_x += char_w + char_gap

    return fb


# ============================================================================
# 6. OPERATIONAL MODES & DIAGNOSTICS
# ============================================================================
def run_corner_test(geometry: MatrixGeometry, client: Optional[SerialMatrixClient], brightness: float, preview: bool):
    """
    Diagnostic Corner Test:
    Lights the 4 matrix corners with distinct colors:
      - Top-Left     (0, 0):    RED
      - Top-Right    (15, 0):   GREEN
      - Bottom-Left  (0, 13):   BLUE
      - Bottom-Right (15, 13):  WHITE
    Prints exact physical indices and expected locations.
    """
    print("\n========================================================")
    print("  CORNER TEST DIAGNOSTIC")
    print("========================================================")
    tl_idx = geometry.xy_to_index(0, 0)
    tr_idx = geometry.xy_to_index(geometry.width - 1, 0)
    bl_idx = geometry.xy_to_index(0, geometry.height - 1)
    br_idx = geometry.xy_to_index(geometry.width - 1, geometry.height - 1)

    print(f"Top-Left     (0, 0):              Physical Index {tl_idx:>3} -> RED   (255, 0, 0)")
    print(f"Top-Right    ({geometry.width-1}, 0):             Physical Index {tr_idx:>3} -> GREEN (0, 255, 0)")
    print(f"Bottom-Left  (0, {geometry.height-1}):             Physical Index {bl_idx:>3} -> BLUE  (0, 0, 255)")
    print(f"Bottom-Right ({geometry.width-1}, {geometry.height-1}):             Physical Index {br_idx:>3} -> WHITE (255, 255, 255)")
    print("========================================================\n")

    fb = geometry.create_framebuffer()
    fb[0][0] = (255, 0, 0)
    fb[0][geometry.width - 1] = (0, 255, 0)
    fb[geometry.height - 1][0] = (0, 0, 255)
    fb[geometry.height - 1][geometry.width - 1] = (255, 255, 255)

    if preview:
        render_terminal_preview(fb, geometry.width, geometry.height)

    if client:
        payload = geometry.framebuffer_to_payload(fb, brightness)
        client.send_frame(payload)
        print("Corner frame sent to Uno. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            client.clear_display()


def run_grid_scan(
    geometry: MatrixGeometry,
    client: Optional[SerialMatrixClient],
    mode: str,
    delay_s: float,
    brightness: float,
    preview: bool
):
    """Scans individual rows or columns to verify strip boundaries and orientation."""
    print(f"\n[Grid Scan] Mode: {mode.upper()} | Delay: {delay_s}s")
    try:
        if mode == "row":
            for y in range(geometry.height):
                fb = geometry.create_framebuffer()
                for x in range(geometry.width):
                    fb[y][x] = (0, 255, 255)
                print(f"Displaying Row {y} of {geometry.height-1}...")
                if preview:
                    render_terminal_preview(fb, geometry.width, geometry.height)
                if client:
                    client.send_frame(geometry.framebuffer_to_payload(fb, brightness))
                time.sleep(delay_s)
        else: # col
            for x in range(geometry.width):
                fb = geometry.create_framebuffer()
                for y in range(geometry.height):
                    fb[y][x] = (255, 255, 0)
                print(f"Displaying Column (Strip) {x} of {geometry.width-1}...")
                if preview:
                    render_terminal_preview(fb, geometry.width, geometry.height)
                if client:
                    client.send_frame(geometry.framebuffer_to_payload(fb, brightness))
                time.sleep(delay_s)
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.clear_display()


def run_pixel_test(
    geometry: MatrixGeometry,
    client: Optional[SerialMatrixClient],
    target_x: Optional[int],
    target_y: Optional[int],
    target_idx: Optional[int],
    brightness: float,
    preview: bool
):
    """Lights a single pixel specified by (x, y) or physical index."""
    if target_idx is not None:
        px, py = geometry.index_to_xy(target_idx)
        pidx = target_idx
    else:
        px = target_x if target_x is not None else 0
        py = target_y if target_y is not None else 0
        pidx = geometry.xy_to_index(px, py)

    print(f"\n[Pixel Test] Logical: ({px}, {py}) <---> Physical Index: {pidx}")
    fb = geometry.create_framebuffer()
    fb[py][px] = (255, 255, 255)

    if preview:
        render_terminal_preview(fb, geometry.width, geometry.height)
    if client:
        client.send_frame(geometry.framebuffer_to_payload(fb, brightness))
        print("Pixel displayed. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            client.clear_display()


def run_text_scroller(
    geometry: MatrixGeometry,
    client: Optional[SerialMatrixClient],
    text: str,
    scroll: bool,
    speed_pps: float,
    color: Tuple[int, int, int],
    scale: int,
    brightness: float,
    preview: bool
):
    """Renders stationary or scrolling text with smooth 1-pixel steps."""
    char_w = 5 * scale
    char_gap = 1 * scale
    total_text_width = len(text) * char_w + max(0, len(text) - 1) * char_gap
    y_offset = (geometry.height - (7 * scale)) // 2  # Centered vertically

    print(f"\n[Text Engine] Text: '{text}' | Scale: {scale}x | Total Width: {total_text_width}px")

    if not scroll:
        # Stationary text centered horizontally
        x_offset = max(0, (geometry.width - total_text_width) // 2)
        fb = render_text_frame(text, x_offset, y_offset, color, scale, spacing=1)
        if preview:
            render_terminal_preview(fb, geometry.width, geometry.height)
        if client:
            client.send_frame(geometry.framebuffer_to_payload(fb, brightness))
            print("Stationary text displayed. Press Ctrl+C to exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                client.clear_display()
        return

    # Continuous horizontal scrolling
    frame_delay = 1.0 / speed_pps if speed_pps > 0 else 0.05
    start_x = geometry.width
    end_x = -total_text_width

    print("Scrolling text... Press Ctrl+C to stop.")
    try:
        while True:
            curr_x = start_x
            while curr_x >= end_x:
                t0 = time.time()
                fb = render_text_frame(text, curr_x, y_offset, color, scale, spacing=1)

                if preview:
                    render_terminal_preview(fb, geometry.width, geometry.height)
                if client:
                    client.send_frame(geometry.framebuffer_to_payload(fb, brightness))

                elapsed = time.time() - t0
                sleep_time = max(0.0, frame_delay - elapsed)
                time.sleep(sleep_time)
                curr_x -= 1
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.clear_display()


# ============================================================================
# 7. MAIN CLI & ARGUMENT PARSING
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="WS2815 16x14 LED Matrix Host Controller & Test Suite"
    )

    # Matrix Geometry Options
    parser.add_argument("--width", type=int, default=16, help="Matrix width in LEDs (default: 16)")
    parser.add_argument("--height", type=int, default=14, help="Matrix height in LEDs (default: 14)")
    parser.add_argument("--first-corner", default="TOP_LEFT",
                        choices=["TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"],
                        help="Physical position of LED index 0 (default: TOP_LEFT)")
    parser.add_argument("--strip-orientation", default="VERTICAL",
                        choices=["VERTICAL", "HORIZONTAL"],
                        help="Orientation of strips (default: VERTICAL)")
    parser.add_argument("--no-serpentine", action="store_true",
                        help="Disable serpentine zigzag chain")

    # Serial & Hardware Options
    parser.add_argument("--port", type=str, default="/dev/ttyACM0",
                        help="Serial port for Uno R3 (default: /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--brightness", type=int, default=20,
                        help="Safe brightness percentage 1..100 (default: 20%%)")
    parser.add_argument("--preview", action="store_true",
                        help="Render terminal ANSI visual preview")
    parser.add_argument("--no-serial", action="store_true",
                        help="Simulate only: skip physical serial transmission")

    # Subcommands / Modes
    subparsers = parser.add_subparsers(dest="command", help="Operational mode")

    # Mode: Text
    p_text = subparsers.add_parser("text", help="Render stationary or scrolling text")
    p_text.add_argument("string", type=str, help="Text to display")
    p_text.add_argument("--stationary", action="store_true", help="Display stationary centered text")
    p_text.add_argument("--speed", type=float, default=15.0, help="Scroll speed in pixels/sec (default: 15)")
    p_text.add_argument("--color", type=str, default="255,180,0", help="RGB color R,G,B (default: 255,180,0)")
    p_text.add_argument("--scale", type=int, default=2, choices=[1, 2],
                        help="Font scale: 1 (5x7) or 2 (10x14 full-height) (default: 2)")

    # Mode: Corners
    subparsers.add_parser("corners", help="Corner LED diagnostic test")

    # Mode: Grid
    p_grid = subparsers.add_parser("grid", help="Scan rows or columns")
    p_grid.add_argument("--mode", default="col", choices=["row", "col"], help="Scan row or col")
    p_grid.add_argument("--delay", type=float, default=0.5, help="Step delay in seconds (default: 0.5)")

    # Mode: Pixel
    p_pixel = subparsers.add_parser("pixel", help="Light a single pixel")
    p_pixel.add_argument("--x", type=int, help="Logical X coordinate (0..width-1)")
    p_pixel.add_argument("--y", type=int, help="Logical Y coordinate (0..height-1)")
    p_pixel.add_argument("--index", type=int, help="Physical 1D LED index (0..num_leds-1)")

    # Mode: Clear
    subparsers.add_parser("clear", help="Clear all LEDs")

    args = parser.parse_args()

    # Default to 'corners' test if no subcommand provided
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialize geometry
    geometry = MatrixGeometry(
        width=args.width,
        height=args.height,
        first_corner=args.first_corner,
        strip_orientation=args.strip_orientation,
        serpentine=not args.no_serpentine
    )

    brightness_scale = max(0.01, min(1.0, args.brightness / 100.0))

    # Connect serial client if requested
    client = None
    if not args.no_serial:
        try:
            client = SerialMatrixClient(args.port, args.baud)
            client.connect()
        except Exception as e:
            print(f"[Serial Warning] Could not open serial port {args.port}: {e}")
            if not args.preview:
                print("Enabling --preview mode so you can see output on the terminal.")
                args.preview = True

    # Register clean signal handler for exit
    def sig_handler(sig, frame):
        if client:
            client.close()
        sys.exit(0)
    signal.signal(signal.SIGINT, sig_handler)

    try:
        if args.command == "corners":
            run_corner_test(geometry, client, brightness_scale, args.preview)

        elif args.command == "grid":
            run_grid_scan(geometry, client, args.mode, args.delay, brightness_scale, args.preview)

        elif args.command == "pixel":
            run_pixel_test(geometry, client, args.x, args.y, args.index, brightness_scale, args.preview)

        elif args.command == "text":
            color_parts = [int(c.strip()) for c in args.color.split(",")]
            rgb_color = (color_parts[0], color_parts[1], color_parts[2])
            run_text_scroller(
                geometry,
                client,
                args.string,
                scroll=not args.stationary,
                speed_pps=args.speed,
                color=rgb_color,
                scale=args.scale,
                brightness=brightness_scale,
                preview=args.preview
            )

        elif args.command == "clear":
            if client:
                client.clear_display()
                print("Display cleared.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
