"""Faster check for Test images that have a near-identical twin in Train.

Uses all CPU cores and caches the Train hashes, so a re-run takes seconds.
Compares a small 'difference hash' (dHash) and also tries mirrored/flipped
versions of each Test image. It cannot catch arbitrary-angle rotations or crops,
so a clean result means "no evidence of leakage", not proof.

Run from the ml folder:  python disease/check_leakage.py
"""
import argparse
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

ML_DIR = Path(__file__).resolve().parents[1]
EXT = {".jpg", ".jpeg", ".png"}
POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def collect(data_dir):
    train, test = [], []
    other = Counter()
    skipped = 0
    for f in data_dir.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in EXT:
            continue
        if ".ipynb_checkpoints" in f.parts:
            skipped += 1
            continue
        rel = f.relative_to(data_dir).parts
        if len(rel) != 4:
            other["(unexpected folder depth)"] += 1
            continue
        split = rel[1].lower()
        if split == "train":
            train.append(f)
        elif split == "test":
            test.append(f)
        else:
            other[rel[1]] += 1
    return sorted(train), sorted(test), other, skipped


def _dhash(small):
    arr = np.asarray(small, dtype=np.int16)  # 8 rows x 9 columns
    return np.packbits((arr[:, 1:] > arr[:, :-1]).flatten())  # 8 bytes


def hash_train(path):
    try:
        with Image.open(path) as img:
            img.draft("L", (64, 64))  # fast low-resolution JPEG decoding
            small = img.convert("L").resize((9, 8))
        return _dhash(small)
    except Exception:
        return None


def hash_test(path):
    try:
        with Image.open(path) as img:
            img.draft("L", (64, 64))
            small = img.convert("L").resize((9, 8))
        variants = [
            small,
            small.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
            small.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
            small.transpose(Image.Transpose.ROTATE_180),
        ]
        return [_dhash(v) for v in variants]
    except Exception:
        return None


def hash_all_train(train, workers):
    cache = ML_DIR / "artifacts" / "disease" / "train_hashes.npz"
    if cache.exists():
        data = np.load(cache, allow_pickle=False)
        if int(data["count"]) == len(train):
            print("Using cached Train hashes (delete train_hashes.npz to recompute).")
            return data["hashes"], [str(p) for p in data["paths"]]

    print(f"Hashing {len(train)} Train images using {workers} workers...")
    start = time.time()
    hashes, paths = [], []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, h in enumerate(ex.map(hash_train, [str(p) for p in train], chunksize=64), 1):
            if h is not None:
                hashes.append(h)
                paths.append(str(train[i - 1]))
            if i % 5000 == 0:
                elapsed = time.time() - start
                left = elapsed / i * (len(train) - i)
                print(f"  {i}/{len(train)}  elapsed {elapsed/60:.1f} min, about {left/60:.1f} min left")

    hashes = np.array(hashes, dtype=np.uint8)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, hashes=hashes, paths=np.array(paths), count=len(train))
    print(f"Done in {(time.time() - start)/60:.1f} minutes. Saved cache.")
    return hashes, paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ML_DIR / "data" / "plantvillage" / "archive (1)"))
    ap.add_argument("--threshold", type=int, default=4, help="max differing bits out of 64")
    args = ap.parse_args()

    workers = max(1, (os.cpu_count() or 2) - 1)
    train, test, other, skipped = collect(Path(args.data_dir))
    print(f"Train images: {len(train)}   Test images: {len(test)}")
    print(f"Skipped .ipynb_checkpoints files: {skipped}")
    print(f"Other splits or odd paths: {dict(other) if other else 'none'}\n")
    if not train or not test:
        print("Could not find Train and Test images. Check --data-dir.")
        return

    train_hashes, train_paths = hash_all_train(train, workers)

    print("Comparing Test images against Train...")
    flagged, checked = [], 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for p, variants in zip(test, ex.map(hash_test, [str(t) for t in test], chunksize=16)):
            if variants is None:
                continue
            checked += 1
            best_dist, best_idx = 65, -1
            for h in variants:
                dist = POPCOUNT[train_hashes ^ h].sum(axis=1)
                j = int(dist.argmin())
                if int(dist[j]) < best_dist:
                    best_dist, best_idx = int(dist[j]), j
            if best_dist <= args.threshold:
                flagged.append((p, train_paths[best_idx], best_dist))

    pct = 100 * len(flagged) / max(checked, 1)
    identical = sum(1 for _, _, d in flagged if d == 0)
    print("\n===== RESULT =====")
    print(f"Test images checked: {checked}")
    print(f"Test images with a near-twin in Train: {len(flagged)} ({pct:.1f}%)")
    print(f"  of which hash-identical            : {identical}")

    for test_p, train_p, d in flagged[:8]:
        print(f"\n  distance {d}")
        print(f"   test : {test_p}")
        print(f"   train: {train_p}")

    out_file = ML_DIR / "artifacts" / "disease" / "leakage_flagged_test.txt"
    out_file.write_text("\n".join(str(p) for p, _, _ in flagged), encoding="utf-8")
    print(f"\nFlagged Test files saved to: {out_file}")
    print("These are POSSIBLE duplicates. Open a few pairs to confirm by eye.")


if __name__ == "__main__":
    main()