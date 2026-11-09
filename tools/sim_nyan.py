"""Run board/nyan.py under CPython with a fake display and fake walking motion.

    python3 tools/sim_nyan.py [out.png]   (needs Pillow)

Saves a strip of frames (standing still, walking, tilted, jolt) scaled up 6x.
"""
import math
import os
import random
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import nyan  # noqa: E402


class FakeDisplay:
    def __init__(self, w=64, h=64):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w, h))
        self.px = self.img.load()
        self.pen = (0, 0, 0)

    def get_bounds(self):
        return self.w, self.h

    def create_pen(self, r, g, b):
        return (r, g, b)

    def set_pen(self, p):
        self.pen = p

    def clear(self):
        self.img.paste(self.pen, (0, 0, self.w, self.h))

    def pixel(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = self.pen

    def rectangle(self, x, y, w, h):
        x0, y0, x1, y1 = max(0, x), max(0, y), min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            self.img.paste(self.pen, (x0, y0, x1, y1))


def accel_at(t):
    """Upright panel (gravity on sensor -x), walking from 1 s.
    0-3 s level (flies at you), 3-5.5 s right side down, 5.5-9 s top leaned
    back (flies away), 9-11 s left side down, jolt at 11.3 s."""
    roll = pitch = 0.0
    if 3.0 < t < 5.5:
        roll = 0.3
    elif 5.5 < t < 9.0:
        pitch = 0.3
    elif 9.0 < t < 11.0:
        roll = -0.3
    x = -math.cos(roll) * math.cos(pitch)
    y = -math.sin(roll)
    z = math.sin(pitch) * math.cos(roll)
    if t > 1.0:
        x -= 0.3 * math.sin(2 * math.pi * 1.8 * t)
    if 11.3 < t < 11.35:
        x -= 1.4
    return x, y, z


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "preview.png")
    random.seed(3)
    d = FakeDisplay()
    cat = nyan.Nyan()
    pal = nyan.Palette(d, 1.0)
    shots = [1.5, 2.2, 2.9, 4.6, 6.6, 7.4, 8.4, 10.8]
    frames = []
    dt = 1 / 30
    t = 0.0
    while shots:
        t += dt
        cat.step(dt, accel_at(t))
        if t >= shots[0]:
            shots.pop(0)
            cat.draw(d, pal)
            frames.append(d.img.copy())
    s = 6
    strip = Image.new("RGB", (len(frames) * (64 * s + 8), 64 * s), (40, 40, 40))
    for i, f in enumerate(frames):
        strip.paste(f.resize((64 * s, 64 * s), Image.NEAREST), (i * (64 * s + 8), 0))
    strip.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
