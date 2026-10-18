"""Shared helpers for building the Indian-crop part of the v2 dataset."""
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

ML_DIR = Path(__file__).resolve().parents[1]
BASE = ML_DIR / "data" / "indian"
OUT = ML_DIR / "data" / "standardized"
ART = ML_DIR / "artifacts" / "disease"
EXT = {".jpg", ".jpeg", ".png"}
SIZE = 256
BLOCK = 8        # consecutive numbered files within a block are linked
TIME_GAP = 5     # seconds between phone photos that are linked
HASH_DIST = 2    # max differing bits (of 64) for "near-identical"
GROUP_CAP = 16   # no group may grow beyond this many files
POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

CLASS_MAP = {
    "sugarcane": {
        "Healthy": "Sugarcane___Healthy",
        "Mosaic": "Sugarcane___Mosaic",
        "RedRot": "Sugarcane___Red Rot",
        "Rust": "Sugarcane___Rust",
        "Yellow": "Sugarcane___Yellow Disease",
    },
    "rice": {
        "Healthy Leaf": "Rice___Healthy",
        "Brown Spot": "Rice___Brown Spot",
        "Bacterial Leaf Blight": "Rice___Bacterial Leaf Blight",
        "Tungro Virus": "Rice___Tungro",
    },
    "wheat": {
        "Healthy": "Wheat___Healthy",
        "septoria": "Wheat___Septoria",
        "stripe_rust": "Wheat___Stripe Rust",
    },
}
SKIP = ("WheatLeafRust", "Ndeficient")  # cut-out backgrounds / not a disease class

TS_PATTERNS = [
    re.compile(r"IMG(20\d{6})(\d{6})"),
    re.compile(r"(?<!\d)(20\d{6})[_-](\d{6})(?!\d)"),
]
NUM_PATTERN = re.compile(r"^([A-Za-z_]+)\s*\((\d+)\)")


def timestamp(name):
    for p in TS_PATTERNS:
        m = p.search(name)
        if m:
            try:
                return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").timestamp()
            except ValueError:
                pass
    return None


def block_key(name):
    m = NUM_PATTERN.match(name)
    return (m.group(1).lower(), int(m.group(2)) // BLOCK) if m else None


def process(job):
    """Standardise one image. Returns (source path, 8-byte difference hash or None)."""
    src, dst = job
    try:
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as opened:
            opened.draft("RGB", (SIZE * 2, SIZE * 2))  # fast decode of huge JPEGs
            img = ImageOps.exif_transpose(opened).convert("RGB")
        w, h = img.size
        scale = SIZE / min(w, h)
        img = img.resize((max(SIZE, round(w * scale)), max(SIZE, round(h * scale))), Image.LANCZOS)
        w, h = img.size
        left, top = (w - SIZE) // 2, (h - SIZE) // 2
        img = img.crop((left, top, left + SIZE, top + SIZE))
        img.save(dst, "JPEG", quality=90)  # saved without metadata
        small = np.asarray(img.convert("L").resize((9, 8), Image.BILINEAR), dtype=np.int16)
        return str(src), np.packbits((small[:, 1:] > small[:, :-1]).flatten()).tobytes()
    except Exception:
        return str(src), None


def group_class(items):
    """Group id per item, with a size cap so one group can never swallow a class.

    Links are applied strongest evidence first:
      1. near-identical pixels (closest pairs first)
      2. photos taken within TIME_GAP seconds of each other
      3. consecutive numbered files (weakest assumption)
    A link is skipped if it would make a group larger than GROUP_CAP.
    """
    n = len(items)
    parent = list(range(n))
    size = [1] * n

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb or size[ra] + size[rb] > GROUP_CAP:
            return
        parent[ra] = rb
        size[rb] += size[ra]

    hashes = np.array([np.frombuffer(it["hash"], dtype=np.uint8) for it in items])
    edges = []
    for i in range(n):
        dist = POPCOUNT[hashes ^ hashes[i]].sum(axis=1)
        for j in np.where(dist <= HASH_DIST)[0]:
            if j > i:
                edges.append((int(dist[j]), i, int(j)))
    for _, i, j in sorted(edges):
        union(i, j)

    stamped = sorted(
        (timestamp(it["name"]), i) for i, it in enumerate(items) if timestamp(it["name"]) is not None
    )
    for (t1, i1), (t2, i2) in zip(stamped, stamped[1:]):
        if t2 - t1 <= TIME_GAP:
            union(i1, i2)

    first = {}
    for i, it in enumerate(items):
        k = block_key(it["name"])
        if k is not None:
            if k in first:
                union(i, first[k])
            else:
                first[k] = i

    return [find(i) for i in range(n)]