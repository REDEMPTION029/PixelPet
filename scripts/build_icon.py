"""Create a multi-resolution Windows ICO from the original character's face."""
from pathlib import Path
import struct

from import_sheets import decode, encode

ROOT = Path(__file__).resolve().parents[1]


def main():
    w, h, image = decode(ROOT / "reference_original.png")
    x0, y0, side = 116, 39, 280
    out = ROOT / "build/icons"
    out.mkdir(parents=True, exist_ok=True)
    blobs = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixels = bytearray(size * size * 4)
        for y in range(size):
            sy = y0 + min(side - 1, int((y + 0.5) * side / size))
            for x in range(size):
                sx = x0 + min(side - 1, int((x + 0.5) * side / size))
                source, dest = (sy * w + sx) * 4, (y * size + x) * 4
                pixels[dest:dest + 4] = image[source:source + 4]
        path = out / f"icon-{size}.png"
        encode(path, size, size, pixels)
        blobs.append((size, path.read_bytes()))
    offset = 6 + 16 * len(blobs)
    entries = []
    for size, data in blobs:
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (ROOT / "assets/app.ico").write_bytes(struct.pack("<HHH", 0, 1, len(blobs)) + b"".join(entries) + b"".join(b for _, b in blobs))
    (ROOT / "assets/app-icon.png").write_bytes(blobs[-1][1])
    print("Created app.ico with 7 resolutions (16–256 px) from the original reference.")


if __name__ == "__main__":
    main()
