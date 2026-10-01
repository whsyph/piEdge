#!/usr/bin/env python3
"""Generate a dependency-free PPM splash image for the Pi DRM output."""

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


def put_text(pixels: list[RGB], text: str, x: int, y: int, scale: int, color: RGB):
    cursor = x
    for char in text:
        glyph = FONT.get(char, ["00000"] * 7)
        for row, line in enumerate(glyph):
            for col, bit in enumerate(line):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            px, py = cursor + col * scale + dx, y + row * scale + dy
                            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                pixels[py * WIDTH + px] = color
        cursor += 6 * scale


def generate(path):
    bg = (10, 18, 31)
    accent = (64, 210, 190)
    white = (235, 245, 250)
    pixels: list[RGB] = [bg] * (WIDTH * HEIGHT)
    # Simple centered accent bar and caPIbarra wordmark.
    for y in range(HEIGHT // 2 - 100, HEIGHT // 2 + 100):
        for x in range(360, 1560):
            if abs(y - HEIGHT // 2) < 5:
                pixels[y * WIDTH + x] = accent
    text = "caPIbarra"
    scale = 24
    text_width = len(text) * 6 * scale
    put_text(pixels, text, (WIDTH - text_width) // 2, HEIGHT // 2 - 70, scale, white)

    with Path(path).open("w", encoding="ascii", newline="\n") as handle:
        handle.write(f"P3\n{WIDTH} {HEIGHT}\n255\n")
        for index in range(0, len(pixels), WIDTH):
            handle.write(" ".join(f"{r} {g} {b}" for r, g, b in pixels[index:index + WIDTH]) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)