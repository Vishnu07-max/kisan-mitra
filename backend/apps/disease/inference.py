"""Crop Doctor inference for model v2.

Preprocessing MUST match ml/disease/v2_common.process() followed by the training
loader, step for step. A parity test in tests.py checks this.
Nothing here returns a diagnosis unless the real model ran AND the result passes
the confidence rules; otherwise the answer is "no_match".
"""
import io
import json
import threading
import time
from pathlib import Path

import numpy as np
from django.conf import settings
from PIL import Image, ImageOps

STD_SIZE = 256
MAX_PIXELS = 50_000_000  # refuse absurdly large images (decompression bombs)

_lock = threading.Lock()
_state = {"model": None, "class_names": None, "meta": None, "dir": None}


class ModelNotAvailable(Exception):
    """The trained model is missing or could not be loaded."""


class InvalidImage(Exception):
    """The bytes are not a usable image."""


def get_model():
    """Load the model on first use and keep it in memory."""
    model_dir = Path(settings.DISEASE_MODEL_DIR)
    with _lock:
        if _state["model"] is not None and _state["dir"] == str(model_dir):
            return _state

        needed = ["model.keras", "class_names.json", "metadata.json"]
        missing = [n for n in needed if not (model_dir / n).exists()]
        if missing:
            raise ModelNotAvailable(
                f"Missing {', '.join(missing)} in {model_dir}. "
                "Train the model (ml/disease/train_v2.py) and set DISEASE_MODEL_DIR."
            )
        try:
            import tensorflow as tf
        except ImportError as exc:
            raise ModelNotAvailable(
                "TensorFlow is not installed. Run: pip install -r requirements-ml.txt"
            ) from exc
        try:
            model = tf.keras.models.load_model(model_dir / "model.keras", compile=False)
            class_names = json.loads((model_dir / "class_names.json").read_text(encoding="utf-8"))
            meta = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
        except Exception as exc:
            raise ModelNotAvailable(f"Could not load the model: {exc}") from exc
        if model.output_shape[-1] != len(class_names):
            raise ModelNotAvailable("class_names.json does not match the model's output size.")

        _state.update(model=model, class_names=class_names, meta=meta, dir=str(model_dir))
        return _state


def preprocess(source, size):
    """Bytes, path or file object -> float32 array (size, size, 3), values 0-255."""
    try:
        img = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
        if img.width * img.height > MAX_PIXELS:
            raise InvalidImage("The image is too large.")
        img.draft("RGB", (STD_SIZE * 2, STD_SIZE * 2))  # same fast JPEG decode as training
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        scale = STD_SIZE / min(w, h)
        img = img.resize((max(STD_SIZE, round(w * scale)), max(STD_SIZE, round(h * scale))), Image.LANCZOS)
        w, h = img.size
        left, top = (w - STD_SIZE) // 2, (h - STD_SIZE) // 2
        img = img.crop((left, top, left + STD_SIZE, top + STD_SIZE))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)  # training images were saved this way, without metadata
    except InvalidImage:
        raise
    except Exception as exc:
        raise InvalidImage("The file is not a readable image.") from exc

    import tensorflow as tf

    decoded = tf.io.decode_jpeg(buf.getvalue(), channels=3)
    return tf.image.resize(decoded, (size, size), antialias=True).numpy().astype(np.float32)


def _describe(index, confidence, class_names):
    crop, _, condition = class_names[index].partition("___")
    return {
        "class_id": index,
        "label": class_names[index],
        "crop": crop,
        "condition": condition,
        "is_healthy": condition.strip().lower() == "healthy",
        "confidence": round(confidence, 4),
    }


def build_result(probs, class_names, version, *, disease_min, healthy_min,
                 withheld_crops=(), experimental_crops=(), top_k=3):
    """Pure function: probabilities -> result dict. Testable without TensorFlow.

    A "no_match" result deliberately contains NO label, so a wrong guess cannot
    reach the screen.
    """
    probs = np.asarray(probs, dtype=float)
    order = np.argsort(probs)[::-1][:top_k]
    top = [_describe(int(i), float(probs[i]), class_names) for i in order]
    best = top[0]
    base = {
        "model_version": version,
        "max_confidence": best["confidence"],
        "thresholds": {"disease": disease_min, "healthy": healthy_min},
    }
    if best["crop"] in withheld_crops:
        return {**base, "status": "no_match", "reason": "withheld_class"}
    needed = healthy_min if best["is_healthy"] else disease_min
    if best["confidence"] < needed:
        return {**base, "status": "no_match", "reason": "low_confidence"}
    return {
        **base,
        "status": "ok",
        "reason": None,
        "outcome": "no_disease_detected" if best["is_healthy"] else "disease_possible",
        "experimental": best["crop"] in experimental_crops,
        "top_prediction": best,
        "top_k": top,
    }


def predict(source):
    """Run the real model on one image."""
    state = get_model()
    x = preprocess(source, state["meta"]["image_size"])[None]

    t0 = time.perf_counter()
    with _lock:
        probs = state["model"](x, training=False).numpy()[0]
    elapsed_ms = (time.perf_counter() - t0) * 1000

    withheld = tuple(settings.DISEASE_WITHHELD_CROPS)
    result = build_result(
        probs,
        state["class_names"],
        state["meta"]["version"],
        disease_min=settings.DISEASE_CONF_MIN,
        healthy_min=settings.DISEASE_CONF_HEALTHY,
        withheld_crops=withheld,
        experimental_crops=tuple(settings.DISEASE_EXPERIMENTAL_CROPS),
    )
    result["inference_ms"] = round(elapsed_ms, 1)
    result["supported_crops"] = sorted(
        {n.partition("___")[0] for n in state["class_names"]} - set(withheld)
    )
    result["experimental_crops"] = list(settings.DISEASE_EXPERIMENTAL_CROPS)
    return result