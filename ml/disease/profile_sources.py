"""Profile image sources per class to detect shortcuts a model could learn.

If file size, dimensions, format or EXIF presence predict the class, the model can
'cheat' without looking at the disease.
Run from the ml folder:  python disease/profile_sources.py
"""
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier

BASE = Path(__file__).resolve().parents[1] / "data" / "indian"
EXT = {".jpg", ".jpeg", ".png"}
CROPS = ["sugarcane", "rice", "wheat"]
SKIP = ("rice_healthy", "WheatLeafRust")


def class_folders(crop_dir):
    found = defaultdict(list)
    for f in crop_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in EXT and not any(s in str(f) for s in SKIP):
            found[f.parent].append(f)
    return found


def main():
    for crop in CROPS:
        folders = class_folders(BASE / crop)
        if not folders:
            print(f"\n##### {crop}: no images found")
            continue
        print(f"\n##### {crop}")
        print(f"{'class':<26}{'n':>5}{'bad':>5}{'median WxH':>14}{'median KB':>11}{'EXIF%':>7}{'PNG%':>6}")
        X, y = [], []
        for label, (folder, files) in enumerate(sorted(folders.items(), key=lambda kv: kv[0].name)):
            ws, hs, kbs, exif, png, bad = [], [], [], 0, 0, 0
            for f in files:
                try:
                    with Image.open(f) as img:
                        w, h = img.size
                        has_exif = len(img.getexif()) > 0
                        is_png = (img.format or "").upper() == "PNG"
                except Exception:
                    bad += 1
                    continue
                size = f.stat().st_size
                ws.append(w); hs.append(h); kbs.append(size / 1024)
                exif += has_exif; png += is_png
                X.append([w, h, w * h, size, int(has_exif), int(is_png)])
                y.append(label)
            n = len(ws)
            if n == 0:
                continue
            print(f"{folder.name[:25]:<26}{n:>5}{bad:>5}"
                  f"{int(np.median(ws)):>8}x{int(np.median(hs)):<5}{int(np.median(kbs)):>11}"
                  f"{100 * exif / n:>7.0f}{100 * png / n:>6.0f}")

        y = np.array(y)
        counts = np.bincount(y)
        if len(counts) >= 2 and counts.min() >= 5:
            cv = StratifiedKFold(5, shuffle=True, random_state=0)
            acc = cross_val_score(DecisionTreeClassifier(max_depth=6, random_state=0), np.array(X), y, cv=cv).mean()
            print(f"\n  Predicting the class from size/format/EXIF ALONE (no pixels): {acc:.1%}")
            print(f"  Always guessing the biggest class would give:                 {counts.max() / counts.sum():.1%}")


if __name__ == "__main__":
    main()