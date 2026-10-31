"""Testable timing and geometry for the floating panel and edge peeking."""
import time
import math
from collections import deque


def fitted_scale(user_scale, area, dpi=96):
    """Keep the entire sprite recoverable, including on small/high-DPI work areas."""
    width,height=max(1,area[2]-area[0]),max(1,area[3]-area[1])
    return min(4.0,user_scale*max(96,min(384,dpi))/96,width/512,height/512)


def clamped_position(x,y,width,height,area):
    left,top,right,bottom=area
    return max(left,min(x,max(left,right-width))),max(top,min(y,max(top,bottom-height)))


def dragged_position(x,y,width,height,area,areas):
    if len(areas)<2:return clamped_position(x,y,width,height,area)
    union=(min(a[0] for a in areas),min(a[1] for a in areas),max(a[2] for a in areas),max(a[3] for a in areas))
    x,y=clamped_position(x,y,width,height,union)
    # Permit straddling internal edges, but retain a visible grab area on the pointer's screen.
    visible=min(32,width,height)
    x=max(area[0]-width+visible,min(x,area[2]-visible))
    y=max(area[1]-height+visible,min(y,area[3]-visible))
    return x,y


class DragInertia:
    """Estimate recent drag velocity, then integrate exponential friction in screen pixels."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.samples = deque()
        self.vx = self.vy = 0.0

    @property
    def active(self):
        return bool(self.vx or self.vy)

    def stop(self):
        self.vx = self.vy = 0.0
        self.samples.clear()

    def begin(self, x, y):
        self.stop()
        self.sample(x, y)

    def sample(self, x, y):
        now = self.clock()
        self.samples.append((now, x, y))
        while len(self.samples) > 1 and self.samples[0][0] < now - .12:
            self.samples.popleft()

    def release(self):
        now = self.clock()
        if len(self.samples) < 2 or now - self.samples[-1][0] > .1:
            self.stop()
            return False
        start, end = self.samples[0], self.samples[-1]
        elapsed = end[0] - start[0]
        if elapsed < .012:
            self.stop()
            return False
        self.vx, self.vy = (end[1]-start[1])/elapsed, (end[2]-start[2])/elapsed
        speed = math.hypot(self.vx, self.vy)
        factor = min(1.0, 900 / max(1, speed)) * math.exp(-7 * max(0, now-end[0]))
        self.vx *= factor
        self.vy *= factor
        self.samples.clear()
        if math.hypot(self.vx, self.vy) < 35:
            self.stop()
        return self.active

    def advance(self, dt):
        decay = math.exp(-7 * max(0, dt))
        distance = (1-decay) / 7
        dx, dy = self.vx * distance, self.vy * distance
        self.vx *= decay
        self.vy *= decay
        if math.hypot(self.vx, self.vy) < 18:
            self.stop()
        return dx, dy


def mirrored_for(direction, base_facing):
    if direction not in ("left", "right") or base_facing not in ("left", "right"):
        raise ValueError("Facing must be left or right")
    return direction != base_facing


def inward_direction(side):
    if side not in ("left", "right"):
        raise ValueError("Unknown screen edge")
    return "right" if side == "left" else "left"


class PanelFade:
    def __init__(self, clock=time.monotonic, hold=6, fade=1.2):
        self.clock, self.hold, self.fade = clock, hold, fade
        self.last_touch = clock()

    def touch(self):
        self.last_touch = self.clock()

    @property
    def strength(self):
        return max(0.0, min(1.0, 1 - (self.clock() - self.last_touch - self.hold) / self.fade))


class EdgeDock:
    def __init__(self):
        self.side = None
        self.area = None
        self.restore = None
        self.elapsed = 0

    @staticmethod
    def choose(x, width, area, margin=14):
        left, _, right, _ = area
        if x <= left + margin:
            return "left"
        if x + width >= right - margin:
            return "right"
        return None

    def begin(self, side, area, x, y, width, scale):
        self.side, self.area, self.restore = side, area, (x, y)
        self.start, self.elapsed = x, 0.0
        self.goal = area[0] - 160 * scale if side == "left" else area[2] - (512 - 160) * scale

    def advance(self, dt):
        self.elapsed = min(.28, self.elapsed + max(0, dt))
        t = self.elapsed / .28
        t = 1 - (1 - t) ** 3
        return self.start + (self.goal - self.start) * t

    def clear(self):
        position = self.restore
        self.side, self.area, self.restore = None, None, None
        return position


def horizontal_clip(x, width, area):
    return max(0, round(area[0] - x)), min(width, round(area[2] - x))
