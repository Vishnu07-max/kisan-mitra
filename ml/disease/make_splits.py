"""Build a leak-free train / validation / test split.

The split is by ORIGINAL PHOTO, not by file. This dataset has many augmented
copies of each photo, and some photos appear twice under different UUIDs.
Two files are treated as the same photo if they share a UUID OR share the same
source name + number (e.g. 'RS_HL 6270'); links are followed transitively.

Run from the ml folder:  python disease/make_splits.py
Reads only file names, so it takes a few seconds.
"""
import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]
EXT = {".jpg", ".jpeg", ".png"}

UUID_PATTERN = re.compile(
    r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})___(.*)$"
)
SUFFIX = re.compile(
    r"(?:_(?:\d+deg|flip\w*|rotate\w*|mirror\w*|contrast\w*|bright\w*|noise\w*"
    r"|blur\w*|zoom\w*|shear\w*|aug\w*|new\w*|pixel\w*|gauss\w*))+$",
    re.IGNORECASE,
)
COPY = re.compile(r"\s*copy(?:\s*\d+)?\s*$", re.IGNORECASE)

_parent = {}


def find(x):
    while _parent.setdefault(x, x) != x:
        _parent[x] = _parent[_parent[x]]
        x = _parent[x]
    return x


def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        _parent[ra] = rb


def keys_for(stem):
    """Return (uuid_or_None, base_name) with augmentation tails removed."""
    m = UUID_PATTERN.match(stem)
    uuid = m.group(1).lower() if m else None
    rest = m.group(2) if m else stem
    base = SUFFIX.sub("", rest)
    base = COPY.sub("", base).strip().lower()
    return uuid, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ML_DIR / "data" / "plantvillage" / "archive (1)"))
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    data_dir = Path(args.data_dir)

    # Pass 1: read file names and link files that belong to the same photo
    records = []  # (class_name, provided_split, name_node, relative_path, uuid)
    for f in data_dir.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in EXT or ".ipynb_checkpoints" in f.parts:
            continue
        rel = f.relative_to(data_dir).parts
        if len(rel) != 4 or rel[1].lower() not in ("train", "test"):
            continue
        cls = f"{rel[0]}___{rel[2]}"
        uuid, base = keys_for(f.stem)
        name_node = f"N|{cls}|{base}"
        find(name_node)
        if uuid:
            union(name_node, f"U|{uuid}")
        records.append((cls, rel[1].lower(), name_node, "/".join(rel), uuid))

    if not records:
        print("No images found. Check --data-dir.")
        return

    # Pass 2: now that all links exist, look up each file's final group
    files = []
    uuids_in_root = defaultdict(set)
    classes_in_root = defaultdict(set)
    for cls, prov, node, rel, uuid in records:
        root = find(node)
        files.append((cls, prov, root, rel))
        classes_in_root[root].add(cls)
        if uuid:
            uuids_in_root[root].add(uuid)

    merged = sum(1 for s in uuids_in_root.values() if len(s) > 1)
    cross_class = sum(1 for s in classes_in_root.values() if len(s) > 1)

    print(f"Files found: {len(files)}")
    print(f"Photos that appear under 2+ different UUIDs (merged by name): {merged}")
    print(f"Groups spanning more than one class (should be 0): {cross_class}")

    train_roots = {r for _, s, r, _ in files if s == "train"}
    provided_test = [x for x in files if x[1] == "test"]
    leaked = sum(1 for _, _, r, _ in provided_test if r in train_roots)
    print(
        f"Provided Test files whose original photo is also in Train: "
        f"{leaked} of {len(provided_test)} ({100 * leaked / len(provided_test):.1f}%)"
    )

    groups = defaultdict(lambda: defaultdict(list))  # class -> group -> [paths]
    for cls, _, root, rel in files:
        groups[cls][root].append(rel)
    sizes = Counter(len(v) for g in groups.values() for v in g.values())
    biggest = sorted((len(v) for g in groups.values() for v in g.values()), reverse=True)[:5]
    print(f"Original photos (groups): {sum(sizes.values())}")
    print(f"Largest groups (files): {biggest}")

    class_names = sorted(groups)
    idx = {n: i for i, n in enumerate(class_names)}
    rng = random.Random(args.seed)
    splits = {"train": [], "val": [], "test": []}
    sources = {"train": 0, "val": 0, "test": 0}
    keys_in = {"train": set(), "val": set(), "test": set()}
    test_per_class = {}

    for cls in class_names:
        keys = sorted(groups[cls])
        rng.shuffle(keys)
        total = sum(len(groups[cls][k]) for k in keys)
        want_test, want_val = total * args.test_frac, total * args.val_frac
        got = {"test": 0, "val": 0, "train": 0}
        for k in keys:
            if got["test"] < want_test:
                part = "test"
            elif got["val"] < want_val:
                part = "val"
            else:
                part = "train"
            for rel in groups[cls][k]:
                splits[part].append([rel, idx[cls]])
            got[part] += len(groups[cls][k])
            sources[part] += 1
            keys_in[part].add(k)
        test_per_class[cls] = got["test"]

    # Safety check: no original photo may appear in two parts
    assert not (keys_in["train"] & keys_in["val"]), "train/val overlap"
    assert not (keys_in["train"] & keys_in["test"]), "train/test overlap"
    assert not (keys_in["val"] & keys_in["test"]), "val/test overlap"

    out = ML_DIR / "artifacts" / "disease" / "splits.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "data_dir": str(data_dir),
                "seed": args.seed,
                "class_names": class_names,
                "train": splits["train"],
                "val": splits["val"],
                "test": splits["test"],
            }
        ),
        encoding="utf-8",
    )

    print("\n===== NEW SPLIT (no original photo appears in two parts) =====")
    for part in ("train", "val", "test"):
        print(f"{part:>5}: {len(splits[part]):6d} files from {sources[part]:5d} original photos")
    print(f"Classes: {len(class_names)}")
    print(f"Smallest test class: {min(test_per_class.values())} files")
    print(f"\nSaved to: {out}")


if __name__ == "__main__":
    main()