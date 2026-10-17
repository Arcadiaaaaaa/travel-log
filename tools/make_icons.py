#!/usr/bin/env python3
"""用纯 Python 生成应用图标（蓝底白色列车正面），无需第三方库。"""
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "icons"
TOP, BOTTOM = (59, 130, 246), (29, 78, 216)
WHITE = (255, 255, 255)
SS = 3  # 每个像素 3x3 超采样，用于抗锯齿


def in_round_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def near_segment(x, y, ax, ay, bx, by, w):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    px, py = ax + t * dx, ay + t * dy
    return (x - px) ** 2 + (y - py) ** 2 <= w * w


def color_at(x, y):
    """x、y 取值 0~1，返回该点颜色。"""
    bg = tuple(round(a + (b - a) * y) for a, b in zip(TOP, BOTTOM))
    for ax, bx in ((0.42, 0.34), (0.58, 0.66)):
        if near_segment(x, y, ax, 0.70, bx, 0.82, 0.022):
            return WHITE
    if in_round_rect(x, y, 0.29, 0.20, 0.71, 0.72, 0.09):
        if in_round_rect(x, y, 0.35, 0.29, 0.65, 0.47, 0.03):
            return bg
        for cx in (0.385, 0.615):
            if (x - cx) ** 2 + (y - 0.60) ** 2 <= 0.032 ** 2:
                return bg
        return WHITE
    return bg


def render(size):
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    c = color_at((px + (sx + 0.5) / SS) / size, (py + (sy + 0.5) / SS) / size)
                    for i in range(3):
                        acc[i] += c[i]
            row += bytes(round(v / (SS * SS)) for v in acc)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        (OUT / f"icon-{size}.png").write_bytes(render(size))
        print(f"icon-{size}.png")
