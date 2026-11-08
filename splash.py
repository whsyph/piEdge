#!/usr/bin/env python3
"""Generate a dependency-free binary PPM (P6) splash image for the Pi DRM output."""

import argparse
from pathlib import Path

WIDTH, HEIGHT = 1920, 1080
RGB = tuple[int, int, int]
FONT = {
    "c": ["01110", "10000", "10000", "10000", "10000", "10000", "01110"],
    "a": ["00000", "01110", "00001", "01111", "10001", "10011", "01101"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "b": ["10000", "10000", "10110", "11001", "10001", "10001", "11110"],
    "r": ["00000", "10110", "11001", "10000", "10000", "10000", "10000"],
    "" : ["0"],
}


def put_pixel(pixels: bytearray, x: int, y: int, color: RGB):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        offset = (y * WIDTH + x) * 3
        pixels[offset:offset + 3] = bytes(color)


def put_text(pixels: bytearray, text: str, x: int, y: int, scale: int, color: RGB):
    cursor = x
    for char in text:
        glyph = FONT.get(char, ["00000"] * 7)
        for row, line in enumerate(glyph):
            for col, bit in enumerate(line):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            put_pixel(pixels, cursor + col * scale + dx, y + row * scale + dy, color)
        cursor += 6 * scale


def generate(path):
    bg = (10, 18, 31)
    accent = (64, 210, 190)
    white = (235, 245, 250)
    pixels = bytearray(bytes(bg) * (WIDTH * HEIGHT))
    # Simple centered accent bar and caPIbarra wordmark.
    for y in range(HEIGHT // 2 - 4, HEIGHT // 2 + 5):
        for x in range(360, 1560):
            put_pixel(pixels, x, y, accent)
    text = "caPIbarra"
    scale = 24
    text_width = len(text) * 6 * scale
    put_text(pixels, text, (WIDTH - text_width) // 2, HEIGHT // 2 - 70, scale, white)

    with Path(path).open("wb") as handle:
        handle.write(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii"))
        handle.write(pixels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)
