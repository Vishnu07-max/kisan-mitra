"""Find every folder that directly contains images and treat it as one class.

Works with Crop/Disease folders or flat Crop___Disease folders.
Run from the ml folder:
    python disease/inspect_dataset.py "C:\\path\\to\\dataset"
"""
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "plantvillage"
DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
EXTENSIONS = {".jpg", ".jpeg", ".png"}

if not DATA_DIR.exists():
    print(f"Folder not found: {DATA_DIR}")
    sys.exit(1)

counts = Counter()
broken = []
by_hash = defaultdict(list)

print(f"Looking in: {DATA_DIR}\n")

for file in DATA_DIR.rglob("*"):
    if not file.is_file() or file.suffix.lower() not in EXTENSIONS:
        continue
    # Class name = the folder path relative to the dataset root
    label = str(file.parent.relative_to(DATA_DIR))
    try:
        with Image.open(file) as img:
            img.verify()
    except Exception:
        broken.append(file)
        continue
    counts[label] += 1
    by_hash[hashlib.md5(file.read_bytes()).hexdigest()].append(file)

for name in sorted(counts):
    print(f"{counts[name]:6d}  {name}")

duplicate_groups = [files for files in by_hash.values() if len(files) > 1]
print(f"\nTotal readable images : {sum(counts.values())}")
print(f"Class folders found   : {len(counts)}")
print(f"Smallest class        : {min(counts.values()) if counts else 0}")
print(f"Largest class         : {max(counts.values()) if counts else 0}")
print(f"Unreadable files      : {len(broken)}")
print(f"Exact-duplicate groups: {len(duplicate_groups)}")