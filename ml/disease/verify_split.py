"""Verify the leak-free split with image hashes.

Do any Test (or Validation) images have a near-identical twin in Train?
Run from the ml folder:  python disease/verify_split.py
Reuses the Train-hash cache made by check_leakage.py, so it is much faster.
"""
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from check_leakage import POPCOUNT, hash_test, hash_train

ML_DIR = Path(__file__).resolve().parents[1]
ART = ML_DIR / "artifacts" / "disease"
THRESHOLD = 4  # max differing bits out of 64


def main():
    spl = json.loads((ART / "splits.json").read_text(encoding="utf-8"))
    root = Path(spl["data_dir"])

    def full(rel):
        return str(root.joinpath(*rel.split("/")))

    cache = {}
    cache_file = ART / "train_hashes.npz"
    if cache_file.exists():
        d = np.load(cache_file, allow_pickle=False)
        cache = {str(p): h for p, h in zip(d["paths"], d["hashes"])}
        print(f"Loaded {len(cache)} cached hashes.")

    parts = {k: [full(r) for r, _ in spl[k]] for k in ("train", "val", "test")}
    needed = {p for v in parts.values() for p in v}
    missing = sorted(p for p in needed if p not in cache)
    workers = max(1, (os.cpu_count() or 2) - 1)

    if missing:
        print(f"Hashing {len(missing)} files that were not in the cache...")
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for p, h in zip(missing, ex.map(hash_train, missing, chunksize=64)):
                if h is not None:
                    cache[p] = h

    train_paths = [p for p in parts["train"] if p in cache]
    train_hashes = np.array([cache[p] for p in train_paths], dtype=np.uint8)
    print(f"Train reference set: {len(train_paths)} images\n")

    flagged_all = []
    for name in ("test", "val"):
        paths = parts[name]
        print(f"Comparing {name} ({len(paths)} images) against Train...")
        flagged, checked = [], 0
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for p, variants in zip(paths, ex.map(hash_test, paths, chunksize=16)):
                if variants is None:
                    continue
                checked += 1
                best_d, best_i = 65, -1
                for h in variants:
                    dist = POPCOUNT[train_hashes ^ h].sum(axis=1)
                    j = int(dist.argmin())
                    if int(dist[j]) < best_d:
                        best_d, best_i = int(dist[j]), j
                if best_d <= THRESHOLD:
                    flagged.append((p, train_paths[best_i], best_d))

        identical = sum(1 for _, _, d in flagged if d == 0)
        print(f"  {name}: near-twin in Train: {len(flagged)} of {checked} "
              f"({100 * len(flagged) / max(checked, 1):.2f}%), hash-identical: {identical}")
        flagged_all += [(name, *f) for f in flagged]

    print("\nClosest pairs (open a few in File Explorer and compare by eye):")
    for name, tp, trp, d in sorted(flagged_all, key=lambda x: x[3])[:6]:
        print(f"  [{name}] distance {d}\n     {tp}\n     {trp}")

    out = ART / "leakage_flagged_new_split.txt"
    out.write_text("\n".join(f"{n}\t{a}\t{b}\t{d}" for n, a, b, d in flagged_all), encoding="utf-8")
    print(f"\nSaved to: {out}")


if __name__ == "__main__":
    main()