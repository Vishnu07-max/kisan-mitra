"""Train v2: PlantVillage (29 classes) + Indian crops (12 classes) = 41 classes.

Reads splits_v1_std.json and splits_indian.json. TEST parts are never loaded here.
Small classes get a higher sample weight (square-root balancing, clipped to 0.5..3).
Images are 256x256 standardised JPEGs; here they are resized to 224 with
tf.image.resize(antialias=True). Serving must use the SAME steps.

Quick check:  python disease/train_v2.py --quick
Real run:     python disease/train_v2.py --version v2
"""
import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf

from train import build_model, clean, compile_model

ML_DIR = Path(__file__).resolve().parents[1]
ART = ML_DIR / "artifacts" / "disease"
SEED = 42
IMG = 224


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v2")
    p.add_argument("--v1-train-per-class", type=int, default=400)
    p.add_argument("--v1-val-per-class", type=int, default=100)
    p.add_argument("--ind-per-class", type=int, default=0, help="0 = use all")
    p.add_argument("--epochs-head", type=int, default=3)
    p.add_argument("--epochs-finetune", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--quick", action="store_true")
    return p.parse_args()


def load_part(part, v1_cap, ind_cap, rng, v1, ind, to_idx):
    paths, labels = [], []
    by_class = {}
    for rel, y in v1[part]:
        by_class.setdefault(int(y), []).append(rel)
    for y in sorted(by_class):
        files = sorted(by_class[y])
        rng.shuffle(files)
        if v1_cap > 0:
            files = files[:v1_cap]
        for rel in files:
            paths.append(str(Path(v1["std_dir"]) / rel))
            labels.append(to_idx[v1["class_names"][y]])
    by_class = {}
    for rel, cls in ind[part]:
        by_class.setdefault(cls, []).append(rel)
    for cls in sorted(by_class):
        files = sorted(by_class[cls])
        rng.shuffle(files)
        if ind_cap > 0:
            files = files[:ind_cap]
        for rel in files:
            paths.append(str(Path(ind["std_dir"]) / rel))
            labels.append(to_idx[cls])
    return paths, labels


def make_dataset(paths, labels, weights, batch, training):
    ds = tf.data.Dataset.from_tensor_slices((np.array(paths), np.array(labels, dtype=np.int32)))
    if training:
        ds = ds.shuffle(len(paths), seed=SEED, reshuffle_each_iteration=True)
    w = tf.constant(weights, dtype=tf.float32)

    def load(path, label):
        img = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        return tf.image.resize(img, (IMG, IMG), antialias=True), label

    def load_weighted(path, label):
        img, label = load(path, label)
        return img, label, tf.gather(w, label)

    ds = ds.map(load_weighted if training else load, num_parallel_calls=tf.data.AUTOTUNE).ignore_errors()
    return ds.batch(batch).prefetch(tf.data.AUTOTUNE)


def main():
    args = parse_args()
    if args.quick:
        args.version = "v2-quick"
        args.v1_train_per_class, args.v1_val_per_class, args.ind_per_class = 8, 4, 12
        args.epochs_head, args.epochs_finetune, args.batch_size = 1, 0, 16

    random.seed(SEED)
    np.random.seed(SEED)
    tf.random.set_seed(SEED)
    rng = random.Random(SEED)

    v1 = json.loads((ART / "splits_v1_std.json").read_text(encoding="utf-8"))
    ind = json.loads((ART / "splits_indian.json").read_text(encoding="utf-8"))
    class_names = list(v1["class_names"]) + list(ind["class_names"])
    assert len(set(class_names)) == len(class_names), "class name clash"
    to_idx = {n: i for i, n in enumerate(class_names)}

    train_p, train_y = load_part("train", args.v1_train_per_class, args.ind_per_class, rng, v1, ind, to_idx)
    val_p, val_y = load_part("val", args.v1_val_per_class, args.ind_per_class, rng, v1, ind, to_idx)
    if not Path(train_p[0]).exists():
        print(f"Image not found: {train_p[0]}. Run standardize_v1.py and build_v2_data.py first.")
        return

    counts = np.bincount(train_y, minlength=len(class_names)).astype(float)
    weights = np.clip((counts[counts > 0].mean() / np.maximum(counts, 1)) ** 0.5, 0.5, 3.0)
    print(f"Classes: {len(class_names)} | train images: {len(train_p)} | validation images: {len(val_p)}")
    print(f"Smallest training class: {int(counts.min())} images | largest: {int(counts.max())}")
    print("Test images are NOT loaded by this script.\n")

    train_ds = make_dataset(train_p, train_y, weights, args.batch_size, training=True)
    val_ds = make_dataset(val_p, val_y, weights, args.batch_size, training=False)

    out_dir = ART / args.version
    out_dir.mkdir(parents=True, exist_ok=True)
    model, base = build_model(len(class_names), IMG)
    compile_model(model, 1e-3)
    history, start = {}, time.time()

    def stopper():
        return tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)

    print("--- Phase 1: training the new classification head ---")
    h1 = model.fit(train_ds, validation_data=val_ds, epochs=args.epochs_head, callbacks=[stopper()])
    history["head"] = clean(h1.history)

    if args.epochs_finetune > 0:
        print("\n--- Phase 2: fine-tuning the top layers of MobileNetV2 ---")
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        for layer in base.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        compile_model(model, 1e-5)
        h2 = model.fit(train_ds, validation_data=val_ds, epochs=args.epochs_finetune, callbacks=[stopper()])
        history["finetune"] = clean(h2.history)

    minutes = (time.time() - start) / 60
    _, val_acc = model.evaluate(val_ds, verbose=0)

    probs = model.predict(val_ds, verbose=0)
    y_true = np.concatenate([y.numpy() for _, y in val_ds])
    y_pred = probs.argmax(1)
    print("\nValidation accuracy per NEW (Indian) class:")
    for name in ind["class_names"]:
        m = y_true == to_idx[name]
        if m.sum():
            print(f"  {float((y_pred[m] == y_true[m]).mean()):.3f}  ({int(m.sum()):3d} images)  {name}")

    model.save(out_dir / "model.keras")
    (out_dir / "class_names.json").write_text(json.dumps(class_names, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (out_dir / "class_weights.json").write_text(
        json.dumps({n: round(float(weights[i]), 3) for i, n in enumerate(class_names)}, indent=2), encoding="utf-8"
    )
    metadata = {
        "version": args.version,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "tensorflow": tf.__version__,
        "architecture": "MobileNetV2 (ImageNet weights) + GAP + Dropout + Dense",
        "image_size": IMG,
        "preprocessing": (
            "PIL: EXIF rotate, RGB, resize short side to 256 (LANCZOS), centre crop 256, "
            "JPEG quality 90 without metadata; then tf.io.decode_jpeg and "
            "tf.image.resize to 224x224 (bilinear, antialias=True), raw 0-255 float"
        ),
        "num_classes": len(class_names),
        "train_images_used": len(train_p),
        "validation_images_used": len(val_p),
        "plantvillage_train_per_class_cap": args.v1_train_per_class,
        "epochs_head": args.epochs_head,
        "epochs_finetune": args.epochs_finetune,
        "training_minutes": round(minutes, 1),
        "validation_accuracy": round(float(val_acc), 4),
        "splits": ["splits_v1_std.json (PlantVillage, grouped by photo)", "splits_indian.json (grouped, cap 16)"],
        "test_set_used_in_training": False,
        "note": "Validation accuracy is NOT the final result. Evaluate on the Test split.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\nSaved to: {out_dir}")
    print(f"Training time: {minutes:.1f} minutes | overall validation accuracy: {val_acc:.3f}")


if __name__ == "__main__":
    main()