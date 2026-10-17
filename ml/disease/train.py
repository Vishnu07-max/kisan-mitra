"""Train the Kisan Mitra crop-disease classifier (MobileNetV2 transfer learning).

Reads artifacts/disease/splits.json (made by make_splits.py).
The TEST part is never loaded here; evaluate.py uses it later.

Quick pipeline check:  python disease/train.py --quick
Real training:         python disease/train.py --version v1
"""
import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf

ML_DIR = Path(__file__).resolve().parents[1]
ART = ML_DIR / "artifacts" / "disease"
SEED = 42


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="v1")
    p.add_argument("--img-size", type=int, default=224)
    p.add_argument("--max-per-class", type=int, default=600, help="0 = use all")
    p.add_argument("--max-val-per-class", type=int, default=150, help="0 = use all")
    p.add_argument("--epochs-head", type=int, default=3)
    p.add_argument("--epochs-finetune", type=int, default=2)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--quick", action="store_true", help="tiny run to test the pipeline")
    return p.parse_args()


def pick(items, root, cap, rng):
    """Take up to `cap` random files per class. Returns full paths and labels."""
    by_class = {}
    for rel, y in items:
        by_class.setdefault(int(y), []).append(rel)
    paths, labels = [], []
    for y in sorted(by_class):
        files = sorted(by_class[y])
        rng.shuffle(files)
        if cap > 0:
            files = files[:cap]
        paths += [str(root.joinpath(*r.split("/"))) for r in files]
        labels += [y] * len(files)
    return paths, labels


def make_dataset(paths, labels, batch_size, img_size, training):
    ds = tf.data.Dataset.from_tensor_slices((np.array(paths), np.array(labels, dtype=np.int32)))
    if training:
        ds = ds.shuffle(len(paths), seed=SEED, reshuffle_each_iteration=True)

    def load(path, label):
        data = tf.io.read_file(path)
        img = tf.io.decode_image(data, channels=3, expand_animations=False)
        img.set_shape([None, None, 3])
        img = tf.image.resize(img, (img_size, img_size))  # float32, values 0-255
        return img, label

    ds = ds.map(load, num_parallel_calls=tf.data.AUTOTUNE).ignore_errors()
    return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def build_model(num_classes, img_size):
    keras = tf.keras
    base = keras.applications.MobileNetV2(
        input_shape=(img_size, img_size, 3), include_top=False, weights="imagenet"
    )
    base.trainable = False

    inputs = keras.Input(shape=(img_size, img_size, 3))
    x = keras.Sequential(
        [
            keras.layers.RandomFlip("horizontal_and_vertical"),
            keras.layers.RandomRotation(0.1),
            keras.layers.RandomZoom(0.1),
            keras.layers.RandomContrast(0.15),
            keras.layers.RandomBrightness(0.15, value_range=(0, 255)),
        ],
        name="augmentation",
    )(inputs)  # only active while training
    x = keras.layers.Rescaling(1 / 127.5, offset=-1)(x)  # MobileNetV2 expects [-1, 1]
    x = base(x, training=False)
    x = keras.layers.GlobalAveragePooling2D()(x)
    x = keras.layers.Dropout(0.3)(x)
    outputs = keras.layers.Dense(num_classes, activation="softmax")(x)
    return keras.Model(inputs, outputs), base


def compile_model(model, lr):
    model.compile(
        optimizer=tf.keras.optimizers.Adam(lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )


def clean(history):
    return {k: [float(v) for v in vals] for k, vals in history.items()}


def main():
    args = parse_args()
    if args.quick:
        args.version = "quick-test"
        args.max_per_class = 20
        args.max_val_per_class = 10
        args.epochs_head = 1
        args.epochs_finetune = 0
        args.batch_size = 16

    random.seed(SEED)
    np.random.seed(SEED)
    tf.random.set_seed(SEED)

    split_file = ART / "splits.json"
    if not split_file.exists():
        print("splits.json not found. Run first: python disease/make_splits.py")
        return
    spl = json.loads(split_file.read_text(encoding="utf-8"))
    root = Path(spl["data_dir"])
    class_names = spl["class_names"]
    rng = random.Random(SEED)

    train_p, train_y = pick(spl["train"], root, args.max_per_class, rng)
    val_p, val_y = pick(spl["val"], root, args.max_val_per_class, rng)
    if not Path(train_p[0]).exists():
        print(f"Image not found: {train_p[0]}\nCheck data_dir inside splits.json.")
        return
    print(f"Classes: {len(class_names)} | train images: {len(train_p)} | validation images: {len(val_p)}")
    print("Test images are NOT loaded by this script.\n")

    train_ds = make_dataset(train_p, train_y, args.batch_size, args.img_size, training=True)
    val_ds = make_dataset(val_p, val_y, args.batch_size, args.img_size, training=False)

    out_dir = ART / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

    model, base = build_model(len(class_names), args.img_size)
    compile_model(model, 1e-3)
    history = {}
    start = time.time()

    print("--- Phase 1: training the new classification head ---")
    t0 = time.time()
    h1 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs_head,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)],
    )
    history["head"] = clean(h1.history)
    head_secs = time.time() - t0
    speed = len(train_p) * len(h1.epoch) / head_secs
    print(f"\nPhase 1 speed (approx, includes validation): {speed:.1f} images/second")
    model.save(out_dir / "model_phase1.keras")  # safety copy

    if args.epochs_finetune > 0:
        print("\n--- Phase 2: fine-tuning the top layers of MobileNetV2 ---")
        base.trainable = True
        for layer in base.layers[:-30]:
            layer.trainable = False
        for layer in base.layers:  # keep BatchNorm frozen for stable fine-tuning
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        compile_model(model, 1e-5)
        h2 = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.epochs_finetune,
            callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)],
        )
        history["finetune"] = clean(h2.history)

    minutes = (time.time() - start) / 60
    val_loss, val_acc = model.evaluate(val_ds, verbose=0)

    model.save(out_dir / "model.keras")
    (out_dir / "class_names.json").write_text(
        json.dumps(class_names, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    metadata = {
        "version": args.version,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "tensorflow": tf.__version__,
        "architecture": "MobileNetV2 (ImageNet weights) + GAP + Dropout + Dense",
        "image_size": args.img_size,
        "input_note": "Raw RGB 0-255 float. Rescaling is built into the model.",
        "num_classes": len(class_names),
        "train_images_used": len(train_p),
        "validation_images_used": len(val_p),
        "max_per_class": args.max_per_class,
        "epochs_head": args.epochs_head,
        "epochs_finetune": args.epochs_finetune,
        "training_minutes": round(minutes, 1),
        "validation_accuracy": round(float(val_acc), 4),
        "split_file": "splits.json (grouped by original photo)",
        "test_set_used_in_training": False,
        "note": "Validation accuracy is NOT the final result. Use evaluate.py on the Test set.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\nSaved to: {out_dir}")
    print(f"Training time: {minutes:.1f} minutes")
    print(f"Validation accuracy: {val_acc:.3f}  (not the final test result)")


if __name__ == "__main__":
    main()