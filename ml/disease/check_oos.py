"""Score photos of UNSUPPORTED things and report how often the app would wrongly answer.

Put photos in subfolders of one folder, e.g. C:\\oos\\scenery, C:\\oos\\leaves, C:\\oos\\other.
Run from the ml folder:  python disease/check_oos.py --dir "C:\\oos"

Proposed serving rule tested here:
  disease result needs confidence >= 0.90, Healthy result needs >= 0.95,
  rice classes are withheld (never answered).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import tensorflow as tf

from evaluate_v2 import image_files, predict, standardise_files
from v2_common import ART, ML_DIR

DISEASE_MIN, HEALTHY_MIN = 0.90, 0.95


def answered(pred, conf, class_names):
    out = []
    for p, c in zip(pred, conf):
        name = class_names[p]
        if name.startswith("Rice___"):
            out.append(False)
        elif name.endswith("___Healthy"):
            out.append(c >= HEALTHY_MIN)
        else:
            out.append(c >= DISEASE_MIN)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", default="v2")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"Folder not found: {root}")
        return
    groups = {d.name: image_files(d) for d in sorted(root.iterdir()) if d.is_dir()}
    loose = image_files(root) if not groups else []
    if loose:
        groups = {root.name: loose}
    groups = {k: v for k, v in groups.items() if v}
    if not groups:
        print("No images found. Put photos in subfolders of that folder, for example scenery and leaves.")
        return

    ver = ART / args.version
    class_names = json.loads((ver / "class_names.json").read_text(encoding="utf-8"))
    model = tf.keras.models.load_model(ver / "model.keras", compile=False)

    results = {}
    total_n = total_wrong = 0
    for name, files in groups.items():
        std = standardise_files(files, ML_DIR / "data" / "standardized_oos" / name, args.workers)
        if not std:
            print(f"\n== {name}: no readable images")
            continue
        probs = predict(model, std)
        pred, conf = probs.argmax(1), probs.max(1)
        wrong = answered(pred, conf, class_names)
        total_n += len(pred)
        total_wrong += int(wrong.sum())
        print(f"\n== {name}: {len(pred)} photos")
        print(f"   Predicted as: {Counter(class_names[p] for p in pred).most_common(5)}")
        for t in (0.5, 0.7, 0.8, 0.9, 0.95):
            print(f"   confidence >= {t}: would be answered for {np.mean(conf >= t) * 100:.0f}%")
        print(f"   PROPOSED RULE: wrongly answered for {wrong.mean() * 100:.0f}% ({int(wrong.sum())} of {len(pred)}), "
              f"correctly 'not found' for {100 - wrong.mean() * 100:.0f}%")
        if wrong.any():
            shown = [(class_names[p], round(float(c), 2)) for p, c, w in zip(pred, conf, wrong) if w][:6]
            print(f"   Examples of wrong answers (label, confidence): {shown}")
        results[name] = {"n": len(pred), "wrongly_answered": float(wrong.mean())}

    print(f"\nALL FOLDERS: wrongly answered for {100 * total_wrong / max(total_n, 1):.0f}% ({total_wrong} of {total_n})")
    (ver / "oos_check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()