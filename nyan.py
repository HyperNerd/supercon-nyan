# nyan.py - a pop-tart cat that rides your backpack, leaving a rainbow behind.
#
# A little 3D scene: the cat flies through space, its rainbow is a trail of
# points left behind in the world, and you steer it by tilting the panel.
#   held level         -> it flies straight at you: you see its face, with a
#                         rainbow cone shrinking off into the distance behind
#   lean the top back  -> it flies away: you see its back and the rainbow
#                         streams out toward you
#   tilt left/right    -> classic side view, flying that way
#   walking            -> every step bounces the cat; the rainbow records it
#   a sharp jolt       -> sparkle burst and a burst of speed
# Neutral slowly follows however the panel is hanging, so after a while it
# settles back to flying at you.
# Buttons (optional):
#   A                  -> cycle brightness (full / medium / low)
#   B                  -> sparkle burst
#
# Run it on its own:   mpremote run nyan.py
# or from other code:  import nyan; nyan.run(i75)
import math
import random
import time

try:
    from micropython import native
except ImportError:          # running on a computer (tools/sim_nyan.py)
    def native(f):
        return f

TILT_SIGN = 1        # flip to -1 if tilting right makes the cat fly left
DEPTH_SIGN = 1       # flip to -1 if leaning back makes it fly toward you
LEVEL_HEADING = -90  # degrees: where it flies when level. -90 = at you,
                     # 0 = right (classic side view), 90 = away
TURN_TILT = 0.15     # how far to tilt/lean before it changes direction
TURN_RATE = 2.5      # rad/s it can swing around
RECENTER = 20.0      # s for 'level' to settle to however it's hanging
BOUNCE = 2800.0      # how hard each step kicks the cat (px/s^2 per g)
SPEED = 38.0         # how fast it flies (world units per second)
BOOST = 110.0
JOLT = 0.9           # g of sudden acceleration that counts as a jolt
LEVELS = (1.0, 0.55, 0.3)   # brightness steps, A cycles through them
FRAME_MS = 33        # ~30 fps

BG = (4, 18, 46)
COLORS = {
    "K": (0, 0, 0),          # outline
    "T": (255, 196, 140),    # crust
    "P": (255, 120, 220),    # frosting
    "S": (255, 20, 120),     # sprinkles
    "G": (150, 150, 160),    # fur
    "W": (255, 255, 255),    # eye shine
    "C": (255, 110, 120),    # cheeks
}
RAINBOW = ((255, 0, 0), (255, 120, 0), (255, 230, 0),
           (40, 255, 0), (0, 140, 255), (110, 40, 255))

_BODY = (
    ".KKKKKKKKKKKKK.",
    "KTTTTTTTTTTTTTK",
    "KTTPPPPPPPPPTTK",
    "KTPPSPPPPPSPPTK",
    "KTPPPPPPSPPPPTK",
    "KTPSPPPPPPPPPTK",
    "KTPPPPSPPPPSPTK",
    "KTPPPPPPPPPPPTK",
    "KTPPSPPPPPPPPTK",
    "KTTPPPPPPPPPTTK",
    "KTTTTTTTTTTTTTK",
    ".KKKKKKKKKKKKK.",
)
_HEAD = (
    ".KK.....KK.",
    "KGGK...KGGK",
    "KGGGKKKGGGK",
    "KGGGGGGGGGK",
    "KGWKGGGWKGK",
    "KGKKGGGKKGK",
    "KCCGGGGGCCK",
    "KGGKGKGKGGK",
    ".KGGKGKGGK.",
    "..KKKKKKK..",
)
_LEG = ("KGGK", "KGGK", ".KK.")
_TAIL_UP = ("KK...", "KGK..", ".KGKK", "..KGG", "...KK")
_TAIL_DOWN = ("...KK", "KKKGG", "KGGKK", "KK...")
# The pop-tart seen end-on (from the front or back).
_TART_END = (
    ".KKKKKKK.",
    "KTTTTTTTK",
    "KTPPPPPTK",
    "KTPSPPPTK",
    "KTPPPPSTK",
    "KTPPPPPTK",
    "KTPSPPPTK",
    "KTPPPPPTK",
    "KTPPSPPTK",
    "KTPPPPPTK",
    "KTTTTTTTK",
    ".KKKKKKK.",
)
_TAIL_BACK = ("KKK", "KGK", "KGK", ".K.")

# Twinkling star, 6 phases of (dx, dy) pixels.
_STAR = (
    ((0, 0),),
    ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)),
    ((0, -2), (0, -1), (0, 1), (0, 2), (-2, 0), (-1, 0), (1, 0), (2, 0)),
    ((0, 0), (0, -3), (0, -2), (0, 2), (0, 3), (-3, 0), (-2, 0), (2, 0), (3, 0)),
    ((0, -3), (0, 3), (-3, 0), (3, 0), (-2, -2), (2, -2), (-2, 2), (2, 2)),
    ((0, -3), (0, 3), (-3, 0), (3, 0)),
)


def _stamp(px, art, ox, oy):
    for j, row in enumerate(art):
        for i, ch in enumerate(row):
            if ch != ".":
                px[(ox + i, oy + j)] = ch


def _runs(px):
    """Pixels -> [(colour, [(x, y, w), ...]), ...]: one rectangle per
    horizontal run of same-coloured pixels."""
    xs = [k[0] for k in px]
    ys = [k[1] for k in px]
    runs = {}
    for y in range(min(ys), max(ys) + 1):
        x = min(xs)
        while x <= max(xs):
            ch = px.get((x, y))
            if ch is None:
                x += 1
                continue
            x0 = x
            while px.get((x + 1, y)) == ch:
                x += 1
            runs.setdefault(ch, []).append((x0, y, x - x0 + 1))
            x += 1
    return list(runs.items())


def _build_frames():
    """Three views x four animation frames. Each view also has the sprite
    point that sits at the cat's position (its centre)."""
    side, front, back = [], [], []
    for p in range(4):
        d = 1 if p in (1, 2) else 0          # legs paddle / body bobs / tail wags
        px = {}
        if p < 2:
            _stamp(px, _TAIL_UP, -5, 4)
        else:
            _stamp(px, _TAIL_DOWN, -5, 6)
        for lx in (1, 4):
            _stamp(px, _LEG, lx + d, 11)
        for lx in (10, 15):
            _stamp(px, _LEG, lx - d, 12)
        _stamp(px, _BODY, 0, d)
        _stamp(px, _HEAD, 9, 3 + d)
        side.append(_runs(px))

        px = {}                              # coming at you: face and paws
        _stamp(px, _LEG, 0, 8 + d)
        _stamp(px, _LEG, 7, 9 - d)
        _stamp(px, _HEAD, 0, 0)
        front.append(_runs(px))

        px = {}                              # flying away: ears, tart, tail
        _stamp(px, _HEAD, -1, -3 + d)
        _stamp(px, _LEG, 0, 11 + d)
        _stamp(px, _LEG, 5, 12 - d)
        _stamp(px, _TART_END, 0, 0)
        _stamp(px, _TAIL_BACK, 3 + (1 if p < 2 else -1), 4)
        back.append(_runs(px))
    return {"side": (side, 7.5, 6.5), "front": (front, 5.5, 6.0), "back": (back, 4.5, 5.0)}


class Palette:
    def __init__(self, display, level):
        def pen(c):
            return display.create_pen(int(c[0] * level), int(c[1] * level), int(c[2] * level))
        self.bg = pen(BG)
        self.star = pen((255, 255, 255))
        self.pen = {ch: pen(c) for ch, c in COLORS.items()}
        self.rainbow = [pen(c) for c in RAINBOW]


F = 64.0          # focal length: 1 world unit = 1 px at the cat's depth
Z0 = 64.0         # how far in front of the camera the cat flies
NEAR = 34.0       # closer than this and points are dropped
FAR = 260.0
SPACING = 3.5     # world units between rainbow points
TRAIL = 34        # rainbow points kept
TAIL = 6.0        # rainbow starts this far behind the cat's centre
THICK = 9.0       # rainbow thickness when seen end-on


class Nyan:
    """The cat stays at depth Z0 and moves on screen with a spring (x, y in
    pixels). Rainbow points and stars are in camera space (X, Y, Z) and the
    world slides past opposite to the cat's heading."""

    def __init__(self, w=64, h=64):
        self.w, self.h = w, h
        self.views = _build_frames()
        self.x, self.y = w / 2, h / 2
        self.vx = self.vy = 0.0
        self.th = math.radians(LEVEL_HEADING)   # heading in the x/z plane
        self.r0 = self.p0 = None                # 'level' tilt and lean
        self.trail = []                         # [X, Y, Z, n]
        self.n = 0
        self.dist = 0.0
        self.t = 0.0
        self.speed = SPEED
        self.g = None                           # slow-filtered gravity vector
        self.cool = 0.0
        self.stars = [self._star([0, 0, 0, 0], random.random() * (FAR - 40) + 40) for _ in range(12)]
        self.sparks = []

    def _star(self, st, z=None):
        z = z if z is not None else 40 + random.random() * (FAR - 40)
        st[0] = (random.random() - 0.5) * 70 * z / F
        st[1] = (random.random() - 0.5) * 70 * z / F
        st[2] = z
        st[3] = random.randrange(6)
        return st

    def burst(self):
        if self.cool > 0:
            return
        self.cool = 0.6
        self.speed = BOOST
        for i in range(14):
            a = random.random() * 6.2832
            v = 30 + random.random() * 45
            self.sparks.append([self.x, self.y, math.cos(a) * v, math.sin(a) * v,
                                0.4 + random.random() * 0.4, i % 6])

    def step(self, dt, a=None):
        self.t += dt
        self.cool -= dt
        fx = fy = 0.0
        target = math.radians(LEVEL_HEADING)
        if a:
            g = self.g
            if g is None:
                g = self.g = list(a)
            k = min(1.0, dt * 1.5)
            for i in range(3):
                g[i] += (a[i] - g[i]) * k
            dx, dy, dz = a[0] - g[0], a[1] - g[1], a[2] - g[2]
            # Panel upright: sensor +x points down the screen, y across it,
            # z out of it. The cat has inertia: when you lurch up it lags down.
            fy = -dx * BOUNCE
            fx = -dy * TILT_SIGN * BOUNCE * 0.6
            if math.sqrt(dx * dx + dy * dy + dz * dz) > JOLT:
                self.burst()
            n = math.sqrt(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]) or 1.0
            roll = -g[1] * TILT_SIGN / n                # + = right side down
            pitch = math.atan2(g[2], -g[0]) * DEPTH_SIGN  # + = top leaned back
            if self.r0 is None:
                self.r0, self.p0 = roll, pitch
            k = min(1.0, dt / RECENTER)
            self.r0 += (roll - self.r0) * k
            self.p0 += (pitch - self.p0) * k
            tx, tz = roll - self.r0, pitch - self.p0
            if tx * tx + tz * tz > TURN_TILT * TURN_TILT:
                target = math.atan2(tz, tx)
        else:
            # no accelerometer: tour all four directions
            target = math.radians(LEVEL_HEADING) + int(self.t / 8) * 1.5708
        d = (target - self.th + math.pi) % (2 * math.pi) - math.pi
        lim = TURN_RATE * dt
        self.th += max(-lim, min(lim, d))
        hx_, hz_ = math.cos(self.th), math.sin(self.th)
        self.speed += (SPEED - self.speed) * min(1.0, dt * 1.2)

        # Spring the cat toward home: ahead of centre when flying sideways.
        # Flying at/away from you it cruises low and weaves (a chase camera
        # above its path), so the rainbow runs up to the vanishing point
        # behind it, or pours down past the bottom edge toward you, instead
        # of hiding behind or covering the cat.
        w, h = self.w, self.h
        loop = 1 - abs(hx_)
        hx = w / 2 + hx_ * 8 + loop * 16 * math.sin(self.t * 0.8)
        hy = h / 2 + 2.5 * math.sin(self.t * 1.7) + loop * (12 + 3 * math.sin(self.t * 1.1 + 1))
        self.vx += (fx + (hx - self.x) * 300 - self.vx * 9) * dt
        self.vy += (fy + (hy - self.y) * 300 - self.vy * 9) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < 8 or self.x > w - 8:
            self.x = max(8.0, min(w - 8.0, self.x))
            self.vx = -self.vx * 0.3
        if self.y < 7 or self.y > h - 8:
            self.y = max(7.0, min(h - 8.0, self.y))
            self.vy = -self.vy * 0.3

        # The world slides past; drop a rainbow point every SPACING units.
        mx, mz = -hx_ * self.speed * dt, -hz_ * self.speed * dt
        tr = self.trail
        for p in tr:
            p[0] += mx
            p[2] += mz
        while tr and (tr[0][2] < NEAR or len(tr) > TRAIL):
            tr.pop(0)
        self.dist += self.speed * dt
        cx, cy = (self.x - w / 2) * Z0 / F, (self.y - h / 2) * Z0 / F
        while self.dist >= SPACING:
            self.dist -= SPACING
            back = TAIL + 6 * abs(hz_) + self.dist
            tr.append([cx - hx_ * back, cy, Z0 - hz_ * back, self.n])
            self.n += 1

        for st in self.stars:
            st[0] += mx * 2.5
            st[2] += mz * 2.5
            if st[2] < NEAR or st[2] > FAR or abs(st[0] * F / st[2]) > 40 or abs(st[1] * F / st[2]) > 40:
                # respawn: far away when coming toward us, anywhere otherwise
                self._star(st, FAR - 20 if hz_ < -0.5 else (40 if hz_ > 0.5 else None))
                if hz_ < -0.5 and random.random() < 0.5:
                    st[2] = 40 + random.random() * (FAR - 60)
        sp = self.sparks
        for i in range(len(sp) - 1, -1, -1):
            k = sp[i]
            k[4] -= dt
            if k[4] <= 0:
                sp.pop(i)
                continue
            k[0] += k[2] * dt
            k[1] += k[3] * dt

    @native
    def _draw_trail(self, d, pal, order):
        sp = d.set_pen
        rect = d.rectangle
        R = pal.rainbow
        w2, h2 = self.w / 2, self.h / 2
        tog = int(self.t * 5) & 1
        tr = self.trail
        prev = None
        for i in order:
            X, Y, Z, n = tr[i]
            if Z > 120 and n & 1:
                continue        # far away the points overlap: half is plenty
            k = F / Z
            sx = w2 + X * k
            sy = h2 + Y * k
            # width: reach the neighbouring point (side view), or the
            # ribbon's thickness (seen end-on)
            ww = THICK * k
            if prev is not None and abs(sx - prev) + 1.5 > ww:
                ww = abs(sx - prev) + 1.5
            prev = sx
            x0 = int(sx - ww / 2 + 64) - 64
            x1 = int(sx + ww / 2 + 64) - 64
            if x1 <= 0 or x0 >= self.w or x1 <= x0:
                continue
            band = 2 * k
            top = sy - 6 * k + ((((n >> 2) + tog) & 1) * max(1, int(k + 0.5)))
            for b in range(6):
                y0 = int(top + b * band + 64) - 64
                y1 = int(top + (b + 1) * band + 64) - 64
                if y1 > y0:
                    sp(R[b])
                    rect(x0, y0, x1 - x0, y1 - y0)

    @native
    def _draw_cat(self, d, pal):
        hx_, hz_ = math.cos(self.th), math.sin(self.th)
        if abs(hx_) >= 0.6:
            frames, cxc, cyc = self.views["side"]
            flip = hx_ < 0
        else:
            frames, cxc, cyc = self.views["front" if hz_ < 0 else "back"]
            flip = False
        ox = int(self.x - cxc + 0.5)
        oy = int(self.y - cyc + 0.5)
        m = int(2 * cxc)
        sp = d.set_pen
        rect = d.rectangle
        for ch, runs in frames[int(self.t * 10) & 3]:
            sp(pal.pen[ch])
            for x0, y0, n in runs:
                if flip:
                    x0 = m - x0 - n
                rect(ox + x0, oy + y0, n, 1)

    def draw(self, d, pal):
        sp = d.set_pen
        pix = d.pixel
        w, h = self.w, self.h
        sp(pal.bg)
        d.clear()

        sp(pal.star)
        tick = int(self.t * 8)
        for st in self.stars:
            sx = int(w / 2 + st[0] * F / st[2])
            sy = int(h / 2 + st[1] * F / st[2])
            for dx, dy in _STAR[(tick + st[3]) % 6]:
                x, y = sx + dx, sy + dy
                if 0 <= x < w and 0 <= y < h:
                    pix(x, y)

        # Rainbow far-to-near, then the cat. (Flying away, the rainbow is
        # really in front of the cat, but drawn honestly it hides it; on top,
        # the rainbow reads as pouring out from under the cat toward you.)
        n = len(self.trail)
        self._draw_trail(d, pal, range(n - 1, -1, -1) if math.sin(self.th) > 0.3 else range(n))
        self._draw_cat(d, pal)

        R = pal.rainbow
        for k in self.sparks:
            x, y = int(k[0]), int(k[1])
            if 0 <= x < w and 0 <= y < h:
                sp(R[k[5]])
                pix(x, y)


def _accel():
    try:
        import machine
        import msa311
        return msa311.MSA311(machine.I2C(0, sda=machine.Pin(20), scl=machine.Pin(21), freq=400000), 0x62)
    except Exception as e:
        print("nyan: no accelerometer, just floating", e)
        return None


def run(i75, seconds=None):
    """Runs forever, or returns after `seconds` (used by the boot rotation)."""
    d = i75.display
    w, h = d.get_bounds()
    accel = _accel()
    cat = Nyan(w, h)
    lvl = 0
    pal = Palette(d, LEVELS[lvl])
    i75.set_led(30, 0, 20)
    a_was = i75.switch_pressed(0)   # still held from the boot menu
    last = start = time.ticks_ms()
    while seconds is None or time.ticks_diff(last, start) < seconds * 1000:
        now = time.ticks_ms()
        dt = time.ticks_diff(now, last) / 1000
        last = now
        if dt <= 0 or dt > 0.1:
            dt = 0.033

        a = None
        if accel:
            try:
                a = accel.read()
            except OSError:
                pass
        a_now = i75.switch_pressed(0)
        if a_now and not a_was:
            lvl = (lvl + 1) % len(LEVELS)
            pal = Palette(d, LEVELS[lvl])
        a_was = a_now
        if i75.switch_pressed(1) and not a_now:
            cat.burst()

        cat.step(dt, a)
        cat.draw(d, pal)
        i75.update()

        el = time.ticks_diff(time.ticks_ms(), now)
        time.sleep_ms(max(1, FRAME_MS - el))   # always yield, or USB serial suffers


if __name__ == "__main__":
    import picographics
    from interstate75 import Interstate75, DISPLAY_INTERSTATE75_64X64
    i75 = Interstate75(display=DISPLAY_INTERSTATE75_64X64, stb_invert=False,
                       panel_type=Interstate75.PANEL_GENERIC, pen_type=picographics.PEN_RGB888)
    run(i75)
