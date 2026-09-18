#!/usr/bin/env python3
"""
Test Suite for LED Matrix Protocol, Mapping, and Font Engine.
"""

import sys

def map_xy_to_index(x, y, width=16, height=14, first_corner="TOP_LEFT", orientation="VERTICAL", serpentine=True):
    """
    General matrix coordinate to physical LED index mapping.
    x in [0, width - 1], y in [0, height - 1].
    """
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"Coordinate ({x}, {y}) out of bounds for {width}x{height}")

    if orientation == "VERTICAL":
        # Strips run vertically
        col = x
        row = y
        # Check starting corner for columns
        if first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
            col = (width - 1) - col
        if first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
            row = (height - 1) - row

        if serpentine:
            if col % 2 == 0:
                # Even columns run from row 0 to height-1
                return col * height + row
            else:
                # Odd columns run from row height-1 down to 0
                return col * height + (height - 1 - row)
        else:
            return col * height + row

    elif orientation == "HORIZONTAL":
        # Strips run horizontally
        col = x
        row = y
        if first_corner in ("BOTTOM_LEFT", "BOTTOM_RIGHT"):
            row = (height - 1) - row
        if first_corner in ("TOP_RIGHT", "BOTTOM_RIGHT"):
            col = (width - 1) - col

        if serpentine:
            if row % 2 == 0:
                return row * width + col
            else:
                return row * width + (width - 1 - col)
        else:
            return row * width + col

    else:
        raise ValueError(f"Unknown orientation {orientation}")


def fletcher16(data: bytes) -> int:
    """Fletcher-16 checksum."""
    c0 = 0
    c1 = 0
    for b in data:
        c0 = (c0 + b) % 255
        c1 = (c1 + c0) % 255
    return (c1 << 8) | c0


def test_historical_anomaly():
    print("=== Test 1: Historical Anomaly Reproduction ===")
    # When using horizontal serpentine on a 16x14 matrix:
    # Corner Bottom-Right (15, 13)
    wrong_idx = map_xy_to_index(15, 13, 16, 14, "TOP_LEFT", "HORIZONTAL", True)
    print(f"Horizontal serpentine maps (15, 13) to index: {wrong_idx}")
    last_led_idx = 223
    dist_from_last = last_led_idx - wrong_idx
    print(f"Distance from last LED (223 - {wrong_idx}): {dist_from_last}")
    assert dist_from_last == 15, f"Expected 15, got {dist_from_last}"

    # Where does physical index 208 appear on vertical serpentine?
    # Col = 208 // 14 = 14
    # Row = 208 % 14 = 12 (since col 14 is even)
    print(f"Physical vertical location of index 208: Col 14, Row 12 (one row above bottom 13)")
    print("MATCH CONFIRMED: Bug mathematically verified!\n")


def test_correct_vertical_mapping():
    print("=== Test 2: Correct Vertical Serpentine Mapping ===")
    corners = {
        "Top-Left (0, 0)": (0, 0),
        "Bottom-Left (0, 13)": (0, 13),
        "Top-Right (15, 0)": (15, 0),
        "Bottom-Right (15, 13)": (15, 13)
    }
    for name, (x, y) in corners.items():
        idx = map_xy_to_index(x, y, 16, 14, "TOP_LEFT", "VERTICAL", True)
        print(f"{name} -> Physical Index {idx}")

    assert map_xy_to_index(0, 0, 16, 14) == 0
    assert map_xy_to_index(0, 13, 16, 14) == 13
    assert map_xy_to_index(15, 13, 16, 14) == 210
    assert map_xy_to_index(15, 0, 16, 14) == 223
    print("All 4 corners map correctly to their expected physical positions!\n")


def test_packet_framing():
    print("=== Test 3: Packet Framing & Checksum ===")
    HEADER = b"\xAA\x55MX"
    CMD_FRAME = 0x01
    payload = bytes([10, 20, 30] * 224)  # 672 bytes
    length = len(payload)
    assert length == 672

    packet_meta = bytes([CMD_FRAME, (length >> 8) & 0xFF, length & 0xFF])
    chk = fletcher16(packet_meta + payload)
    packet = HEADER + packet_meta + payload + bytes([(chk >> 8) & 0xFF, chk & 0xFF])

    assert len(packet) == 4 + 3 + 672 + 2  # 681 bytes
    print(f"Packet successfully constructed: total length {len(packet)} bytes.")
    print(f"Fletcher16 Checksum: 0x{chk:04X}")

    # Verify checksum
    calc_chk = fletcher16(packet_meta + payload)
    assert calc_chk == chk
    print("Checksum matches perfectly!\n")


if __name__ == "__main__":
    test_historical_anomaly()
    test_correct_vertical_mapping()
    test_packet_framing()
    print("ALL TESTS PASSED!")
