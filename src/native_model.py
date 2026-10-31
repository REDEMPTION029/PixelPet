"""Assets, animation and validated settings for the native desktop pet."""
from collections import OrderedDict
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ["PIXELPET_DATA_DIR"]) if os.environ.get("PIXELPET_DATA_DIR") else (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PixelPet"
    if getattr(sys, "frozen", False) else ROOT / "runtime")


def validate_config(raw):
    cfg = {"x": None, "y": None, "scale": 0.5, "topmost": True, "auto_move": False,
           "idle_chat": True, "auto_sleep": True, "chat_interval": 75,
           "edge_peek": True, "clock_sound": True, "drag_inertia": True,
           "focus_minutes": 25, "break_minutes": 5}
    if not isinstance(raw, dict):
        return cfg
    for key in ("x", "y"):
        value = raw.get(key)
        if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
            cfg[key] = max(-100000, min(100000, int(value)))
    value = raw.get("scale", 0.5)
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        cfg["scale"] = max(0.5, min(2.0, round(value * 4) / 4))
    for key in ("topmost", "auto_move", "idle_chat", "auto_sleep", "edge_peek", "clock_sound", "drag_inertia"):
        if isinstance(raw.get(key), bool):
            cfg[key] = raw[key]
    if type(raw.get("chat_interval")) is int and raw["chat_interval"] in (45, 75, 150):
        cfg["chat_interval"] = raw["chat_interval"]
    for key, choices in (("focus_minutes", (15,25,45,60)), ("break_minutes", (5,10,15))):
        if type(raw.get(key)) is int and raw[key] in choices:
            cfg[key] = raw[key]
    return cfg


def load_config(path=None):
    path = path or DATA_DIR / "config.json"
    try:
        return validate_config(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        return validate_config({})


def save_config(cfg, path=None):
    path = path or DATA_DIR / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(validate_config(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def save_session(session, path=None):
    path=path or DATA_DIR/'session.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(session.snapshot(),ensure_ascii=False),encoding='utf-8')
    os.replace(temporary,path)


def load_session(session, path=None):
    path=path or DATA_DIR/'session.json'
    try:
        return session.restore(json.loads(path.read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,TypeError):
        return False


def resample(frame, scale, flip):
    """Nearest-neighbour sampling preserves the reference's pixel-like texture."""
    sw, sh, data = frame
    w, h = max(1, round(sw * scale)), max(1, round(sh * scale))
    xs = [min(sw - 1, int((x + 0.5) * sw / w)) for x in range(w)]
    if flip:
        xs = [sw - 1 - x for x in xs]
    rows = {}
    out = []
    for y in range(h):
        sy = min(sh - 1, int((y + 0.5) * sh / h))
        if sy not in rows:
            row = data[sy * sw * 4:(sy + 1) * sw * 4]
            rows[sy] = b"".join(row[x * 4:x * 4 + 4] for x in xs)
        out.append(rows[sy])
    return w, h, b"".join(out)


class Library:
    def __init__(self, imaging, root=None):
        root = Path(root) if root else ROOT / "assets"
        self.frames, self.meta = {}, {}
        decoded={}
        specs = json.loads((root / "frame_meta.json").read_text(encoding="utf-8-sig"))
        for action, spec in specs.items():
            if "frame_files" in spec:
                paths = []
                for name in spec["frame_files"]:
                    path = (root / name).resolve()
                    if not path.is_relative_to(root.resolve()) or not path.is_file():
                        raise ValueError(f"Invalid frame reference: {name}")
                    paths.append(path)
            else:
                paths = sorted((root / action).glob(f"{action}_[0-9][0-9].png"))
            if not paths:
                continue
            frames=[]
            for path in paths:
                name=path.resolve()
                if name not in decoded:decoded[name]=imaging.decode(path)
                frames.append(decoded[name])
            if any(f[:2] != (512, 512) for f in frames):
                raise ValueError(f"Unexpected frame size in {action}")
            duration = spec.get("duration_ms", 200)
            if not isinstance(duration, (int, float)) or not 10 <= duration <= 10000:
                raise ValueError(f"Invalid frame duration in {action}")
            self.frames[action] = frames
            self.meta[action] = spec
            durations = spec.get("frame_durations_ms")
            if durations is not None and (len(durations) != len(frames) or
                    any(not isinstance(d, (int, float)) or not 10 <= d <= 10000 for d in durations)):
                raise ValueError(f"Invalid per-frame timing in {action}")
            if not 0 <= spec.get("loop_start", 0) < len(frames):
                raise ValueError(f"Invalid loop start in {action}")
            anchors = spec.get("anchors")
            if anchors and (len(anchors) != len(frames) or any(len(a) != 2 or
                    any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 512 for v in a) for a in anchors)):
                raise ValueError(f"Invalid frame anchors in {action}")
        if not self.frames.get("idle"):
            raise ValueError("Missing idle frames")
        self.canvas = self.frames["idle"][0][:2]
        for action, spec in self.meta.items():
            if spec.get("base_facing","left") not in ("left","right"):
                raise ValueError(f"Invalid base facing in {action}")
            for key in ("enter", "exit", "next"):
                if spec.get(key) and spec[key] not in self.frames:
                    raise ValueError(f"Missing {key} animation in {action}")


class Player:
    def __init__(self, library):
        self.library = library
        self.action = ""
        self.index = 0
        self.elapsed = 0.0
        self.play("idle")

    def play(self, action, once=False):
        action = action if action in self.library.frames else "idle"
        self.action, self.index, self.elapsed = action, 0, 0.0
        self.once = once or not self.library.meta[action].get("loop", True)

    def advance(self, seconds):
        self.elapsed += max(0, seconds) * 1000
        finished = None
        # Bound pathological elapsed times without accumulating an unbounded loop.
        for _ in range(1000):
            spec = self.library.meta[self.action]
            durations = spec.get("frame_durations_ms")
            duration = durations[self.index] if durations else spec.get("duration_ms", 200)
            if self.elapsed < duration:
                break
            self.elapsed -= duration
            self.index += 1
            if self.index == len(self.library.frames[self.action]):
                if self.once:
                    finished = self.action
                    carry = self.elapsed
                    self.play(spec.get("next") or "idle")
                    self.elapsed = carry
                    break
                self.index = spec.get("loop_start", 0)
        return finished

    @property
    def frame(self):
        return self.library.frames[self.action][self.index]

    @property
    def anchor(self):
        anchors = self.library.meta[self.action].get("anchors")
        return anchors[self.index] if anchors else (256, 496)


class SurfaceCache:
    def __init__(self, create, limit=64, byte_budget=32*1024*1024):
        self.create, self.limit, self.items = create, limit, OrderedDict()
        self.byte_budget,self.bytes=max(4*1024*1024,byte_budget),0

    def get(self, player, scale, flip):
        key = (player.action, player.index, scale, flip)
        if key not in self.items:
            frame=resample(player.frame, scale, flip)
            size=frame[0]*frame[1]*4
            while self.items and (self.bytes+size>self.byte_budget or len(self.items)>=self.limit):
                _, value = self.items.popitem(last=False)
                self.bytes-=value.width*value.height*4
                value.close()
            self.items[key] = self.create(*frame)
            self.bytes+=size
        self.items.move_to_end(key)
        return self.items[key]

    def clear(self):
        for item in self.items.values():
            item.close()
        self.items.clear()
        self.bytes=0
