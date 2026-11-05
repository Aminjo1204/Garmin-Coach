"""Erzeugt die App-Icons (PNG) ohne externe Bibliotheken.  Aufruf: python tools/make_icons.py"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"
BG = (200, 245, 96)      # Akzentfarbe
FG = (13, 15, 19)        # dunkle Linie
# Zickzack-Linie im 32er-Raster (wie das Favicon)
LINE = [(7, 20), (12, 12), (16, 18), (19, 14), (25, 22)]


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rounded_rect_alpha(x, y, size, radius):
    # Abstand zum abgerundeten Rechteck (positiv = außen)
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    d = math.hypot(x - cx, y - cy) - radius if (x < radius or x > size - radius) and (y < radius or y > size - radius) else -1
    return max(0.0, min(1.0, 0.5 - d))


def render(size: int, maskable: bool) -> bytes:
    # maskable: volle Fläche, Motiv in der inneren 70-%-Zone; sonst abgerundetes Quadrat
    scale = size / 32 * (0.7 if maskable else 1.0)
    off = size * 0.15 if maskable else 0.0
    pts = [(off + x * scale, off + y * scale) for x, y in LINE]
    half = 1.6 * scale  # Linienstärke ~3.2 Rastereinheiten
    radius = size * 0.22
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            a_bg = 1.0 if maskable else _rounded_rect_alpha(px, py, size, radius)
            d = min(_seg_dist(px, py, *pts[i], *pts[i + 1]) for i in range(len(pts) - 1))
            a_fg = max(0.0, min(1.0, half + 0.5 - d))
            r = round(BG[0] * (1 - a_fg) + FG[0] * a_fg)
            g = round(BG[1] * (1 - a_fg) + FG[1] * a_fg)
            b = round(BG[2] * (1 - a_fg) + FG[2] * a_fg)
            row += bytes((r, g, b, round(255 * a_bg)))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, mask in [("icon-192.png", 192, False), ("icon-512.png", 512, False),
                             ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)]:
        (OUT / name).write_bytes(render(size, mask))
        print("geschrieben:", OUT / name)
