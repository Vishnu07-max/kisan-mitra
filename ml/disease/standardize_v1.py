"""Standardise the PlantVillage images with the SAME function used for the Indian crops.

Reads artifacts/disease/splits.json (the leak-free v1 split) and writes
data/standardized_v1/<label>/NNNNNN.jpg plus artifacts/disease/splits_v1_std.json
Run from the ml folder:  python disease/standardize_v1.py
"""
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from v2_common import ART, ML_DIR, process

OUT = ML_DIR / "data" / "standardized_v1"


def main():
    spl = json.loads((ART / "splits.json").read_text(encoding="utf-8"))
    root = Path(spl["data_dir"])
    jobs, meta = [], []
    for part in ("train", "val", "test"):
        for rel, y in spl[part]:
            new_rel = f"{int(y):02d}/{len(jobs):06d}.jpg"
            src = str(root.joinpath(*rel.split("/")))
            jobs.append((src, str(OUT / new_rel)))
            meta.append((part, new_rel, int(y), src))

    workers = max(1, (os.cpu_count() or 2) - 1)
    print(f"Standardising {len(jobs)} images with {workers} workers...")
    ok, start = set(), time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (src, h) in enumerate(ex.map(process, jobs, chunksize=64), 1):
            if h is not None:
                ok.add(src)
            if n % 5000 == 0:
                print(f"  {n}/{len(jobs)}  ({(time.time() - start) / 60:.1f} min)")

    out = {"std_dir": str(OUT), "class_names": spl["class_names"], "train": [], "val": [], "test": []}
    failed = 0
    for part, new_rel, y, src in meta:
        if src in ok:
            out[part].append([new_rel, y])
        else:
            failed += 1
    (ART / "splits_v1_std.json").write_text(json.dumps(out), encoding="utf-8")
    print(f"Done in {(time.time() - start) / 60:.1f} min. Failed: {failed}")
    print({k: len(v) for k, v in out.items() if k in ("train", "val", "test")})


if __name__ == "__main__":
    main()