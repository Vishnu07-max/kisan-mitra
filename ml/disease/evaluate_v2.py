"""Evaluate v2 on held-out data. Run from the ml folder:

    python disease/evaluate_v2.py --version v2
    python disease/evaluate_v2.py --version v2 --oos-dir "C:\\path\\to\\unsupported\\photos"

Measures: PlantVillage test, Indian test, an EXTERNAL rice dataset never used in
training, and (optionally) your own photos of things the app does not support.
"""
import argparse
import json
import os
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import precision_recall_fscore_support

from v2_common import ART, EXT, ML_DIR, process

IMG = 224
THRESHOLDS = (0.5, 0.7, 0.8, 0.9, 0.95)
EXTERNAL = {
    "bacterialblight": "Rice___Bacterial Leaf Blight",
    "brownspot": "Rice___Brown Spot",
    "tungro": "Rice___Tungro",
    "blast": None,  # a real rice disease that v2 was NEVER taught
}


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def predict(model, paths, batch=64):
    def load(p):
        img = tf.io.decode_jpeg(tf.io.read_file(p), channels=3)
        return tf.image.resize(img, (IMG, IMG), antialias=True)

    ds = (
        tf.data.Dataset.from_tensor_slices(np.array(paths))
        .map(load, num_parallel_calls=tf.data.AUTOTUNE)
        .batch(batch)
        .prefetch(tf.data.AUTOTUNE)
    )
    return model.predict(ds, verbose=0)


def standardise_files(files, out_dir, workers):
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(str(f), str(out_dir / f"{i:06d}.jpg")) for i, f in enumerate(files)]
    ok = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for (_, dst), (_, h) in zip(jobs, ex.map(process, jobs, chunksize=16)):
            if h is not None:
                ok.append(dst)
    return ok


def image_files(folder):
    return sorted(f for f in Path(folder).rglob("*") if f.is_file() and f.suffix.lower() in EXT)


def threshold_table(conf, correct):
    out = {}
    for t in THRESHOLDS:
        m = conf >= t
        out[str(t)] = {
            "answered": float(m.mean()),
            "accuracy_when_answered": float(correct[m].mean()) if m.any() else float("nan"),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v2")
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--external-cap", type=int, default=600)
    ap.add_argument("--oos-dir", default="")
    ap.add_argument("--limit", type=int, default=0, help="only N PlantVillage test images (quick test)")
    args = ap.parse_args()
    workers = max(1, (os.cpu_count() or 2) - 1)

    ver = ART / args.version
    class_names = json.loads((ver / "class_names.json").read_text(encoding="utf-8"))
    to_idx = {n: i for i, n in enumerate(class_names)}
    v1 = json.loads((ART / "splits_v1_std.json").read_text(encoding="utf-8"))
    ind = json.loads((ART / "splits_indian.json").read_text(encoding="utf-8"))
    n_v1 = len(v1["class_names"])
    model = tf.keras.models.load_model(ver / "model.keras", compile=False)
    rng = random.Random(0)

    # ---------- PlantVillage + Indian test sets ----------
    pv_items = list(v1["test"])
    if args.limit:
        rng.shuffle(pv_items)
        pv_items = pv_items[: args.limit]
    pv_paths = [str(Path(v1["std_dir"]) / rel) for rel, _ in pv_items]
    pv_y = np.array([to_idx[v1["class_names"][int(y)]] for _, y in pv_items])
    in_paths = [str(Path(ind["std_dir"]) / rel) for rel, _ in ind["test"]]
    in_y = np.array([to_idx[c] for _, c in ind["test"]])

    print(f"Scoring {len(pv_paths)} PlantVillage and {len(in_paths)} Indian test images...")
    pv_p, in_p = predict(model, pv_paths), predict(model, in_paths)
    pv_pred, in_pred = pv_p.argmax(1), in_p.argmax(1)
    pv_ok, in_ok = (pv_pred == pv_y).astype(float), (in_pred == in_y).astype(float)

    y_all, p_all = np.concatenate([pv_y, in_y]), np.concatenate([pv_pred, in_pred])
    _, _, f1_all, _ = precision_recall_fscore_support(
        y_all, p_all, labels=range(len(class_names)), average="macro", zero_division=0
    )
    ind_labels = sorted({int(i) for i in in_y})
    _, _, f1_ind, _ = precision_recall_fscore_support(
        in_y, in_pred, labels=ind_labels, average="macro", zero_division=0
    )

    print("\n===== PLANTVILLAGE TEST (v1 scored 0.960 on its test split) =====")
    print(f"Files: {len(pv_paths)}   Accuracy: {pv_ok.mean():.3f}   Top-3: "
          f"{np.mean([pv_y[i] in np.argsort(pv_p[i])[-3:] for i in range(len(pv_y))]):.3f}")
    crops = np.array([class_names[y].split("___")[0] for y in pv_y])
    for c in sorted(set(crops)):
        print(f"  {pv_ok[crops == c].mean():.3f}  {c}")
    to_indian = int((in_pred < n_v1).sum())
    from_pv = int((pv_pred >= n_v1).sum())
    print(f"PlantVillage images predicted as an Indian-crop class: {from_pv} of {len(pv_pred)}")

    print("\n===== INDIAN TEST (small sets: 95% intervals treat images as independent, so they are too narrow) =====")
    print(f"Files: {len(in_paths)}   Accuracy: {in_ok.mean():.3f}   Macro F1 (12 Indian classes): {f1_ind:.3f}")
    print(f"Macro F1 over all {len(class_names)} classes (PlantVillage + Indian): {f1_all:.3f}")
    print(f"Indian images predicted as a PlantVillage crop: {to_indian} of {len(in_pred)}")
    per_class = {}
    for c in ind_labels:
        m = in_y == c
        k, n = int(in_ok[m].sum()), int(m.sum())
        lo, hi = wilson(k, n)
        per_class[class_names[c]] = {"recall": k / n, "n": n}
        print(f"  {k / n:.3f}  (n={n:3d}, optimistic 95%: {lo:.2f} to {hi:.2f})  {class_names[c]}")
    pairs = Counter((class_names[t], class_names[p]) for t, p in zip(in_y, in_pred) if t != p)
    print("Most common mistakes on the Indian test (true -> predicted):")
    for (t, p), n in pairs.most_common(8):
        print(f"  {n:3d}  {t}  ->  {p}")
    print("\nIf the app only answers above a confidence threshold (Indian test):")
    for t, v in threshold_table(in_p.max(1), in_ok).items():
        print(f"  >= {t}: answers {v['answered'] * 100:.0f}%, accuracy when answered {v['accuracy_when_answered']:.3f}")

    results = {
        "version": args.version,
        "plantvillage_test_files": len(pv_paths),
        "plantvillage_accuracy": float(pv_ok.mean()),
        "indian_test_files": len(in_paths),
        "indian_accuracy": float(in_ok.mean()),
        "indian_per_class": per_class,
        "macro_f1_indian_classes": float(f1_ind),
        "macro_f1_all_classes": float(f1_all),
        "indian_thresholds": threshold_table(in_p.max(1), in_ok),
    }

    # ---------- EXTERNAL rice set (never used for training or tuning) ----------
    ext_root = ML_DIR / "data" / "indian" / "rice_external"
    folders = {d.name.lower(): d for d in ext_root.rglob("*") if d.is_dir() and d.name.lower() in EXTERNAL}
    if folders:
        print("\n===== EXTERNAL RICE SET (different dataset; blast was never taught) =====")
        ext = {}
        for name, folder in sorted(folders.items()):
            files = image_files(folder)
            rng.shuffle(files)
            files = files[: args.external_cap]
            std = standardise_files(files, ML_DIR / "data" / "standardized_external" / name, workers)
            ext[name] = predict(model, std)
        supported_ok, supported_conf = [], []
        for name, probs in ext.items():
            pred, conf = probs.argmax(1), probs.max(1)
            if EXTERNAL[name] is not None:
                ok = (pred == to_idx[EXTERNAL[name]]).astype(float)
                supported_ok.append(ok)
                supported_conf.append(conf)
                top = Counter(class_names[p] for p in pred).most_common(3)
                print(f"  {ok.mean():.3f}  (n={len(pred)})  {name}   most common predictions: {top}")
        ok_all, conf_all = np.concatenate(supported_ok), np.concatenate(supported_conf)
        print(f"  Supported rice diseases, overall external accuracy: {ok_all.mean():.3f}")
        for t, v in threshold_table(conf_all, ok_all).items():
            print(f"    >= {t}: answers {v['answered'] * 100:.0f}%, accuracy when answered {v['accuracy_when_answered']:.3f}")
        bp = ext.get("blast")
        if bp is not None:
            bconf = bp.max(1)
            print(f"\n  BLAST (unsupported disease), n={len(bconf)}:")
            print(f"  Predicted as: {Counter(class_names[p] for p in bp.argmax(1)).most_common(4)}")
            for t in THRESHOLDS:
                print(f"    at threshold {t}: correctly 'not found' for {np.mean(bconf < t) * 100:.0f}%, "
                      f"wrongly answered for {np.mean(bconf >= t) * 100:.0f}%")
            results["external_blast_wrongly_answered_at_threshold"] = float(np.mean(bconf >= args.threshold))
        results["external_rice_supported_accuracy"] = float(ok_all.mean())
    else:
        print("\n(External rice folders not found: skipped)")

    # ---------- Optional: your own photos of unsupported things ----------
    if args.oos_dir and Path(args.oos_dir).exists():
        files = image_files(args.oos_dir)
        std = standardise_files(files, ML_DIR / "data" / "standardized_oos", workers)
        probs = predict(model, std)
        conf = probs.max(1)
        print(f"\n===== YOUR UNSUPPORTED PHOTOS (n={len(conf)}) =====")
        print(f"Predicted as: {Counter(class_names[p] for p in probs.argmax(1)).most_common(5)}")
        for t in THRESHOLDS:
            print(f"  at threshold {t}: correctly 'not found' for {np.mean(conf < t) * 100:.0f}%, "
                  f"wrongly answered for {np.mean(conf >= t) * 100:.0f}%")
        results["oos_n"] = len(conf)
        results["oos_wrongly_answered_at_threshold"] = float(np.mean(conf >= args.threshold))

    (ver / "evaluation_v2.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved to {ver / 'evaluation_v2.json'}")


if __name__ == "__main__":
    main()