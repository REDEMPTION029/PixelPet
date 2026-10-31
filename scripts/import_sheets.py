"""Package GPT-drawn sprite cells as PNG frames; never synthesize character poses.

Standard library only. Crop, align whole cells and preserve source RGBA pixels.
"""
from pathlib import Path
import binascii
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {
    "idle": [1600, 240, 90, 110, 130, 700],
    "walk": [140, 100, 120, 140, 100, 120],
    "headClick": [140, 160, 180, 450, 200, 160],
    "bodyClick": [120, 160, 180, 450, 200, 180],
    "sleep": [450, 500, 800, 1000, 900, 900],
    "happy": [130, 180, 110, 200, 180, 260],
}


def decode(path):
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")
    pos, blocks = 8, []
    while pos < len(raw):
        length = struct.unpack_from(">I", raw, pos)[0]
        kind, payload = raw[pos + 4:pos + 8], raw[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            w, h, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise ValueError("Expected non-interlaced RGBA8 source")
        elif kind == b"IDAT":
            blocks.append(payload)
        pos += length + 12
    data = zlib.decompress(b"".join(blocks))
    stride, output = w * 4, bytearray(w * h * 4)
    for y in range(h):
        kind = data[y * (stride + 1)]
        row = data[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
        for x, value in enumerate(row):
            i = y * stride + x
            a = output[i - 4] if x >= 4 else 0
            b = output[i - stride] if y else 0
            c = output[i - stride - 4] if y and x >= 4 else 0
            if kind == 1:
                value += a
            elif kind == 2:
                value += b
            elif kind == 3:
                value += (a + b) // 2
            elif kind == 4:
                p = a + b - c
                differences = (abs(p - a), abs(p - b), abs(p - c))
                value += (a, b, c)[differences.index(min(differences))]
            elif kind != 0:
                raise ValueError("Unknown PNG filter")
            output[i] = value & 255
    return w, h, output


def encode(path, w, h, pixels):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xffffffff)
    scan = b"".join(b"\0" + pixels[y * w * 4:(y + 1) * w * 4] for y in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(scan, 6)) + chunk(b"IEND", b""))


def main():
    report, meta = {}, {}
    for action, timing in ACTIONS.items():
        source = ROOT / "assets/sheets" / f"{action}.png"
        w, h, sheet = decode(source)
        if (w, h) != (1536, 1024):
            raise ValueError(f"Unexpected atlas dimensions: {source}: {(w,h)}")
        folder = ROOT / "assets" / action
        folder.mkdir(exist_ok=True)
        frames = []
        for index in range(6):
            cx, cy = (index % 3) * 512, (index // 3) * 512
            xs, ys = [], []
            for y in range(512):
                for x in range(512):
                    if sheet[((cy + y) * w + cx + x) * 4 + 3] >= 128:
                        xs.append(x)
                        ys.append(y)
            if not xs:
                raise ValueError("Empty sprite cell")
            x0, y0, x1, y1 = max(0, min(xs) - 3), max(0, min(ys) - 3), min(512, max(xs) + 4), min(512, max(ys) + 4)
            # Align independent generated drawings to a common ground/centre.
            # These are packaging offsets, not generated animation poses.
            baseline = [496, 496, 496, 440, 496, 496][index] if action == "happy" else 496
            dx = round(256 - (x0 + x1) / 2)
            dy = baseline - y1
            if x0 + dx < 0 or x1 + dx > 512 or y0 + dy < 0 or y1 + dy > 512:
                raise ValueError(f"Sprite would clip: {action} {index + 1}, bbox={x0,y0,x1,y1}, offset={dx,dy}")
            pixels = bytearray(512 * 512 * 4)
            for y in range(y0, y1):
                start = ((cy + y) * w + cx + x0) * 4
                end = ((y + dy) * 512 + x0 + dx) * 4
                pixels[end:end + (x1 - x0) * 4] = sheet[start:start + (x1 - x0) * 4]
            name = f"{action}_{index + 1:02}.png"
            encode(folder / name, 512, 512, pixels)
            frames.append({"file": name, "source_cell": index, "content_bbox": [x0, y0, x1, y1],
                           "packaging_offset": [dx, dy], "pixel_sha256": hashlib.sha256(pixels).hexdigest()})
        report[action] = {"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "frames": frames}
        meta[action] = {"duration_ms": 160, "frame_durations_ms": timing,
                        "loop": action in ("idle", "walk", "sleep"),
                        "next": None if action in ("idle", "walk", "sleep") else "idle",
                        "loop_start": 2 if action == "sleep" else 0}
    (ROOT / "assets/frame_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (ROOT / "docs/asset_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Imported 6 GPT sprite sheets / 36 redrawn frames, 512x512 RGBA.")


if __name__ == "__main__":
    main()
