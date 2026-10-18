"""Which grouping rule merges too much?

For each class, groups the images using ONE rule at a time and prints
'number of groups / size of the biggest group'.
Run from the ml folder:  python disease/diagnose_groups.py
"""
import json

import numpy as np
from PIL import Image

from v2_common import ART, OUT, POPCOUNT, block_key, timestamp


def components(n, edges):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    sizes = {}
    for i in range(n):
        r = find(i)
        sizes[r] = sizes.get(r, 0) + 1
    return f"{len(sizes)}/{max(sizes.values())}"


def dhash(path):
    img = Image.open(path).convert("L").resize((9, 8), Image.BILINEAR)
    a = np.asarray(img, dtype=np.int16)
    return np.packbits((a[:, 1:] > a[:, :-1]).flatten())


def main():
    manifest = json.loads((ART / "manifest_indian.json").read_text(encoding="utf-8"))
    by_class = {}
    for m in manifest:
        by_class.setdefault(m["cls"], []).append(m)

    print("Each cell is: groups / size of biggest group (smaller 'biggest' = safer)\n")
    print(f"{'class':<30}{'files':>6}{'blocks':>10}{'time60s':>10}{'time5s':>10}{'hash0':>10}{'hash2':>10}{'hash4':>10}")
    for cls in sorted(by_class):
        items = by_class[cls]
        n = len(items)

        first, e_block = {}, []
        for i, it in enumerate(items):
            k = block_key(it["name"])
            if k is None:
                continue
            if k in first:
                e_block.append((i, first[k]))
            else:
                first[k] = i

        stamped = sorted((timestamp(it["name"]), i) for i, it in enumerate(items) if timestamp(it["name"]) is not None)

        def time_edges(gap):
            return [(i1, i2) for (t1, i1), (t2, i2) in zip(stamped, stamped[1:]) if t2 - t1 <= gap]

        hashes = np.array([dhash(OUT / it["rel"]) for it in items])

        def hash_edges(th):
            edges = []
            for i in range(n):
                dist = POPCOUNT[hashes ^ hashes[i]].sum(axis=1)
                edges += [(i, int(j)) for j in np.where(dist <= th)[0] if j > i]
            return edges

        row = [
            components(n, e_block),
            components(n, time_edges(60)),
            components(n, time_edges(5)),
            components(n, hash_edges(0)),
            components(n, hash_edges(2)),
            components(n, hash_edges(4)),
        ]
        print(f"{cls:<30}{n:>6}" + "".join(f"{c:>10}" for c in row))


if __name__ == "__main__":
    main()