"""Evaluate a trained model on the held-out TEST split.

Run from the ml folder:  python disease/evaluate.py --version v1

Reports accuracy three ways, because the Test set contains several augmented
copies of each original photo:
  1. all Test files
  2. original-looking files only (no rotation/flip/copy suffix in the name)
  3. all Test files except those flagged as near-twins of Train images
It also reports macro precision/recall/F1, a confidence interval that resamples
whole photos (not files), confidence-threshold behaviour, and inference time.

Images are loaded with PIL, the same way the web app will load uploads.
"""
import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from make_splits import COPY, SUFFIX, UUID_PATTERN

ML_DIR = Path(__file__).resolve().parents[1]
ART = ML_DIR / "artifacts" / "disease"


def load_image(path, size):
    with Image.open(path) as img:
        img = img.convert("RGB").resize((size, size), Image.BILINEAR)
        return np.asarray(img, dtype=np.float32)


def stem_parts(path):
    stem = Path(path).stem
    m = UUID_PATTERN.match(stem)
    return (m.group(1).lower(), m.group(2)) if m else (stem, stem)


def is_original(path):
    _, rest = stem_parts(path)
    return SUFFIX.search(rest) is None and COPY.search(rest) is None


def acc(mask, correct):
    return float(correct[mask].mean()) if mask.sum() else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="evaluate only N images (for a quick test)")
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args()

    import tensorflow as tf

    ver_dir = ART / args.version
    spl = json.loads((ART / "splits.json").read_text(encoding="utf-8"))
    class_names = json.loads((ver_dir / "class_names.json").read_text(encoding="utf-8"))
    if class_names != spl["class_names"]:
        print("class_names.json does not match splits.json. Retrain or rerun make_splits.py.")
        return
    meta = json.loads((ver_dir / "metadata.json").read_text(encoding="utf-8"))
    size = meta["image_size"]
    root = Path(spl["data_dir"])

    items = spl["test"]
    if args.limit:
        rng = np.random.default_rng(0)
        items = [items[i] for i in rng.permutation(len(items))[: args.limit]]
    paths = [str(root.joinpath(*rel.split("/"))) for rel, _ in items]
    y_true = np.array([int(y) for _, y in items])

    model = tf.keras.models.load_model(ver_dir / "model.keras")
    print(f"Model {args.version} loaded. Evaluating {len(paths)} Test images...")

    probs, ok = [], []
    start = time.time()
    for i in range(0, len(paths), args.batch_size):
        chunk, good = [], []
        for j, p in enumerate(paths[i : i + args.batch_size]):
            try:
                chunk.append(load_image(p, size))
                good.append(i + j)
            except Exception:
                pass
        if chunk:
            probs.append(model.predict(np.stack(chunk), verbose=0))
            ok += good
        if (i // args.batch_size) % 20 == 0:
            print(f"  {min(i + args.batch_size, len(paths))}/{len(paths)}")
    probs = np.concatenate(probs)
    y_true = y_true[ok]
    paths = [paths[k] for k in ok]
    n_failed = len(items) - len(ok)
    total_secs = time.time() - start

    y_pred = probs.argmax(1)
    conf = probs.max(1)
    correct = (y_pred == y_true).astype(float)
    top3 = float(np.mean([y_true[i] in np.argsort(probs[i])[-3:] for i in range(len(y_true))]))
    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=range(len(class_names)), average="macro", zero_division=0
    )

    # Subsets
    original = np.array([is_original(q) for q in paths])
    flagged = set()
    flag_file = ART / "leakage_flagged_new_split.txt"
    if flag_file.exists():
        for line in flag_file.read_text(encoding="utf-8").splitlines():
            cols = line.split("\t")
            if len(cols) >= 2 and cols[0] == "test":
                flagged.add(cols[1])
    not_flagged = np.array([q not in flagged for q in paths])

    # Confidence interval: resample whole photos, not files
    keys = np.array([stem_parts(q)[0] for q in paths])
    uniq, inv = np.unique(keys, return_inverse=True)
    correct_by, size_by = np.bincount(inv, weights=correct), np.bincount(inv)
    brng = np.random.default_rng(0)
    boots = []
    for _ in range(args.bootstrap):
        idx = brng.integers(0, len(uniq), len(uniq))
        boots.append(correct_by[idx].sum() / size_by[idx].sum())
    lo, hi = np.percentile(boots, [2.5, 97.5])

    # Per-crop accuracy
    crops = np.array([class_names[y].split("___")[0] for y in y_true])
    per_crop = {c: float(correct[crops == c].mean()) for c in sorted(set(crops))}

    # Confidence thresholds
    thresholds = {}
    for t in (0.5, 0.7, 0.8, 0.9, 0.95):
        m = conf >= t
        thresholds[str(t)] = {
            "coverage": float(m.mean()),
            "accuracy_when_answered": acc(m, correct),
        }

    # Latency for ONE image: load + preprocess + predict
    sample = paths[:33]
    times = []
    for q in sample:
        t0 = time.perf_counter()
        x = load_image(q, size)[None]
        model(x, training=False).numpy()
        times.append((time.perf_counter() - t0) * 1000)
    latency_ms = float(np.median(times[3:]))  # ignore warm-up

    results = {
        "version": args.version,
        "test_files_evaluated": len(paths),
        "test_files_failed_to_load": n_failed,
        "distinct_photos_in_test": int(len(uniq)),
        "accuracy_all_files": float(correct.mean()),
        "accuracy_95ci_resampling_photos": [float(lo), float(hi)],
        "accuracy_original_looking_files": acc(original, correct),
        "n_original_looking_files": int(original.sum()),
        "accuracy_excluding_flagged_twins": acc(not_flagged, correct),
        "n_flagged_twins_excluded": int((~not_flagged).sum()),
        "top3_accuracy": top3,
        "macro_precision": float(p),
        "macro_recall": float(r),
        "macro_f1": float(f1),
        "per_crop_accuracy": per_crop,
        "confidence_thresholds": thresholds,
        "single_image_latency_ms_cpu": latency_ms,
        "batch_total_seconds": round(total_secs, 1),
        "preprocessing": "PIL, RGB, 224x224 bilinear, raw 0-255",
    }
    (ver_dir / "evaluation_test.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    report = classification_report(
        y_true, y_pred, labels=range(len(class_names)), target_names=class_names,
        digits=3, zero_division=0,
    )
    (ver_dir / "classification_report_test.txt").write_text(report, encoding="utf-8")

    cm = confusion_matrix(y_true, y_pred, labels=range(len(class_names)))
    np.savetxt(ver_dir / "confusion_matrix_test.csv", cm, fmt="%d", delimiter=",")
    norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(14, 12))
    ax.imshow(norm, cmap="Greens")
    short = [n.replace("___", ": ")[:28] for n in class_names]
    ax.set_xticks(range(len(short)))
    ax.set_xticklabels(short, rotation=90, fontsize=6)
    ax.set_yticks(range(len(short)))
    ax.set_yticklabels(short, fontsize=6)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"Confusion matrix (Test, row-normalised) - {args.version}")
    fig.tight_layout()
    fig.savefig(ver_dir / "confusion_matrix_test.png", dpi=150)

    # Printed summary
    print("\n===== TEST RESULTS =====")
    print(f"Files evaluated: {len(paths)} (failed to load: {n_failed}), distinct photos: {len(uniq)}")
    print(f"Accuracy, all files                  : {results['accuracy_all_files']:.3f}   95% CI (resampling photos): {lo:.3f} to {hi:.3f}")
    print(f"Accuracy, original-looking files only: {results['accuracy_original_looking_files']:.3f}   (n={int(original.sum())})")
    print(f"Accuracy, excluding flagged twins    : {results['accuracy_excluding_flagged_twins']:.3f}   ({int((~not_flagged).sum())} excluded)")
    print(f"Top-3 accuracy                       : {top3:.3f}")
    print(f"Macro precision / recall / F1        : {p:.3f} / {r:.3f} / {f1:.3f}")
    print(f"Single-image latency (CPU, median)   : {latency_ms:.0f} ms")
    print("\nAccuracy by crop:")
    for c, v in per_crop.items():
        print(f"  {v:.3f}  {c}")
    print("\nIf the app only answers above a confidence threshold:")
    for t, v in thresholds.items():
        print(f"  >= {t}: answers {v['coverage']*100:.0f}% of images, accuracy when answered {v['accuracy_when_answered']:.3f}")
    off = [(cm[i, j], i, j) for i in range(len(cm)) for j in range(len(cm)) if i != j and cm[i, j] > 0]
    print("\nMost common mistakes (true -> predicted):")
    for n, i, j in sorted(off, reverse=True)[:8]:
        print(f"  {n:4d}  {short[i]}  ->  {short[j]}")
    print(f"\nSaved report, confusion matrix and evaluation_test.json to: {ver_dir}")


if __name__ == "__main__":
    main()