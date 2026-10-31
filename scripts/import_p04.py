"""Package approved v0.4 drawings with authored foot anchors. No pose synthesis."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from import_sheets import decode, encode
from src.native_model import resample


def main():
    recipes = {
        "sitTransition": {"split": 560, "scale": .91,
            "feet": [(268, 533), (242, 540), (226, 538), (287, 434), (207, 440), (200, 446)]},
        "adjustGlasses": {"split": 512, "scale": 1,
            "feet": [(282, 484), (236, 484), (204, 484), (292, 480), (248, 480), (208, 480)]},
    }
    report = {}
    for action, recipe in recipes.items():
        source = ROOT / "assets/sheets" / f"{action}.png"
        w, h, pixels = decode(source)
        assert (w, h) == (1536, 1024)
        folder = ROOT / "assets" / action
        folder.mkdir(exist_ok=True)
        records = []
        for i, (fx, fy) in enumerate(recipe["feet"]):
            left, top = i % 3 * 512, 0 if i < 3 else recipe["split"]
            bottom = recipe["split"] if i < 3 else h
            points = [(x, y) for y in range(top, bottom) for x in range(left, left + 512)
                      if pixels[(y * w + x) * 4 + 3] >= 128]
            x0, y0 = max(left, min(x for x, y in points) - 3), max(top, min(y for x, y in points) - 3)
            x1, y1 = min(left + 512, max(x for x, y in points) + 4), min(bottom, max(y for x, y in points) + 4)
            cw, ch = x1 - x0, y1 - y0
            raw = b"".join(pixels[(y * w + x0) * 4:(y * w + x1) * 4] for y in range(y0, y1))
            ow, oh, scaled = resample((cw, ch, raw), recipe["scale"], False)
            dx, dy = round(256 - (left + fx - x0) * ow / cw), round(496 - (top + fy - y0) * oh / ch)
            assert 0 <= dx and dx + ow <= 512 and 0 <= dy and dy + oh <= 512, (action, i, dx, dy, ow, oh)
            out = bytearray(512 * 512 * 4)
            for y in range(oh):
                out[((dy + y) * 512 + dx) * 4:((dy + y) * 512 + dx + ow) * 4] = scaled[y * ow * 4:(y + 1) * ow * 4]
            file = folder / f"{action}_{i + 1:02}.png"
            encode(file, 512, 512, out)
            records.append({"file": file.relative_to(ROOT).as_posix(), "source_foot": [fx, fy],
                "anchor": [256, 496], "source_box": [x0, y0, x1, y1], "scale": recipe["scale"],
                "pixel_sha256": hashlib.sha256(out).hexdigest()})
        report[action] = records
    path = ROOT / "assets/frame_meta.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    for action, frames in meta.items():
        count = len(list((ROOT / "assets" / action).glob(f"{action}_*.png")))
        if count:
            frames["anchors"] = [[256, 496]] * count
    meta["adjustGlasses"] = {"duration_ms": 160, "frame_durations_ms": [100, 150, 180, 360, 160, 180],
        "loop": False, "next": "idle", "anchors": [[256, 496]] * 6}
    meta["sleepEnter"] = {"frame_files": ["idle/idle_01.png", *[f"sitTransition/sitTransition_{i:02}.png" for i in (2, 3, 4, 5)], "sleep/sleep_01.png"],
        "duration_ms": 160, "frame_durations_ms": [100, 160, 180, 200, 180, 150], "loop": False, "next": "sleep", "anchors": [[256, 496]] * 6}
    meta["sleepExit"] = {"frame_files": list(reversed(meta["sleepEnter"]["frame_files"])),
        "duration_ms": 160, "frame_durations_ms": [120, 160, 180, 180, 170, 160], "loop": False, "next": "idle", "anchors": [[256, 496]] * 6}
    meta["sleep"].update(enter="sleepEnter", exit="sleepExit", loop_start=2)
    meta["walkEnter"] = {"frame_files": ["idle/idle_01.png", "walk/walk_02.png"], "duration_ms": 110, "loop": False, "next": "walk"}
    meta["walkExit"] = {"frame_files": ["walk/walk_02.png", "idle/idle_01.png"], "duration_ms": 140, "loop": False, "next": "idle"}
    meta["walk"].update(enter="walkEnter", exit="walkExit", cycle_distance=80)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "docs/asset_report_v0.4.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Packaged 12 GPT poses; added anchored sleep enter/exit, glasses, and walk transitions.")


if __name__ == "__main__":
    main()
