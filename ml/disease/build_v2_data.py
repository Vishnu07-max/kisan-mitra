"""Build the Indian-crop part of the v2 dataset.

1. Standardise images (EXIF rotate, RGB, short side 256, centre crop, JPEG q90,
   no metadata) into data/standardized/<class>/NNNNN.jpg
2. Group photos that are probably the same leaf.
3. Split BY GROUP into train/val/test (70/15/15) per class.

Run from the ml folder:  python disease/build_v2_data.py
"""
import argparse
import json
import os
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from v2_common import ART, BASE, CLASS_MAP, EXT, OUT, SKIP, group_class, process


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    workers = args.workers or max(1, (os.cpu_count() or 2) - 1)

    # 1. Collect source files
    jobs, meta = [], []
    for crop, mapping in CLASS_MAP.items():
        for f in sorted((BASE / crop).rglob("*")):
            if not f.is_file() or f.suffix.lower() not in EXT or any(s in str(f) for s in SKIP):
                continue
            cls = mapping.get(f.parent.name)
            if cls is None:
                continue
            idx = len(jobs)
            rel = f"{cls}/{idx:05d}.jpg"
            jobs.append((str(f), str(OUT / rel)))
            meta.append({"src": str(f), "rel": rel, "cls": cls, "name": f.stem})
    print(f"Source images found: {len(jobs)}  (standardising with {workers} workers)")
    if not jobs:
        print("Nothing found. Check the folder names under data/indian.")
        return

    # 2. Standardise + hash
    start = time.time()
    hashes = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (src, h) in enumerate(ex.map(process, jobs, chunksize=16), 1):
            hashes[src] = h
            if n % 500 == 0:
                print(f"  {n}/{len(jobs)}  ({(time.time() - start) / 60:.1f} min)")
    failed = [m["src"] for m in meta if hashes.get(m["src"]) is None]
    items_all = [dict(m, hash=hashes[m["src"]]) for m in meta if hashes.get(m["src"]) is not None]
    print(f"Done in {(time.time() - start) / 60:.1f} min. Failed to process: {len(failed)}")

    # 3. Group and split per class
    rng = random.Random(args.seed)
    by_class = {}
    for it in items_all:
        by_class.setdefault(it["cls"], []).append(it)

    splits = {"train": [], "val": [], "test": []}
    print(f"\n{'class':<34}{'files':>6}{'groups':>7}{'biggest':>8}{'train':>7}{'val':>5}{'test':>5}")
    for cls in sorted(by_class):
        items = by_class[cls]
        gid = group_class(items)
        groups = {}
        for it, g in zip(items, gid):
            groups.setdefault(g, []).append(it)
        keys = sorted(groups)
        rng.shuffle(keys)
        total = len(items)
        want_test, want_val = total * args.test_frac, total * args.val_frac
        got = Counter()
        for k in keys:
            part = "test" if got["test"] < want_test else ("val" if got["val"] < want_val else "train")
            for it in groups[k]:
                splits[part].append([it["rel"], cls])
            got[part] += len(groups[k])
        biggest = max(len(g) for g in groups.values())
        print(f"{cls:<34}{total:>6}{len(groups):>7}{biggest:>8}{got['train']:>7}{got['val']:>5}{got['test']:>5}")

    class_names = sorted(by_class)
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "splits_indian.json").write_text(
        json.dumps({"std_dir": str(OUT), "class_names": class_names, **splits}), encoding="utf-8"
    )
    (ART / "manifest_indian.json").write_text(
        json.dumps([{k: v for k, v in m.items() if k != "hash"} for m in meta], indent=1), encoding="utf-8"
    )
    print(f"\nSaved splits_indian.json and manifest_indian.json to {ART}")
    print(f"Totals: train {len(splits['train'])}, val {len(splits['val'])}, test {len(splits['test'])}")
    if failed:
        print("Files that failed to process (first 5):", failed[:5])


if __name__ == "__main__":
    main()