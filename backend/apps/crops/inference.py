"""Crop recommendation inference. Loads the trained bundle once; nothing is guessed for missing inputs."""
import json
import threading
from pathlib import Path

import numpy as np
from django.conf import settings

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
GROUP_OF = {"N": "nutrients", "P": "nutrients", "K": "nutrients", "ph": "ph",
            "temperature": "climate", "humidity": "climate", "rainfall": "climate"}

_lock = threading.Lock()
_state = {"bundle": None, "metrics": None, "dir": None}


class ModelNotAvailable(Exception):
    """The trained model is missing or could not be loaded."""


def load():
    model_dir = Path(settings.CROP_MODEL_DIR)
    with _lock:
        if _state["bundle"] is not None and _state["dir"] == str(model_dir):
            return _state
        f = model_dir / "model.joblib"
        if not f.exists():
            raise ModelNotAvailable(f"Missing model.joblib in {model_dir}. Run ml/crop_recommendation/train_crop.py.")
        try:
            import joblib

            bundle = joblib.load(f)  # only load files produced by our own training script
        except Exception as exc:
            raise ModelNotAvailable(f"Could not load the model: {exc}") from exc
        metrics = {}
        mf = model_dir / "metrics.json"
        if mf.exists():
            try:
                metrics = json.loads(mf.read_text(encoding="utf-8"))
            except ValueError:
                metrics = {}
        _state.update(bundle=bundle, metrics=metrics, dir=str(model_dir))
        return _state


def input_set_key(values):
    """Which trained model matches the inputs given, e.g. 'nutrients+ph'."""
    groups = []
    for g in ("nutrients", "ph", "climate"):
        cols = [c for c in FEATURES if GROUP_OF[c] == g]
        if all(c in values for c in cols):
            groups.append(g)
    return "+".join(groups)


def range_warnings(values, feature_ranges):
    out = []
    for f, v in values.items():
        r = feature_ranges[f]
        if v < r["min"] or v > r["max"]:
            out.append({"feature": f, "value": v, "dataset_min": r["min"], "dataset_max": r["max"]})
    return out


def explain(crop, values, crop_ranges):
    """Your value next to the crop's typical range (its middle 80% of rows in the dataset)."""
    rows = []
    for f in FEATURES:
        if f not in values:
            continue
        r, v = crop_ranges[crop][f], values[f]
        position = "within" if r["p10"] <= v <= r["p90"] else ("below" if v < r["p10"] else "above")
        rows.append({"feature": f, "value": v, "typical_low": r["p10"], "typical_high": r["p90"], "position": position})
    return rows


def recommend(values, top_k=3):
    import pandas as pd

    state = load()
    bundle, metrics = state["bundle"], state["metrics"]
    key = input_set_key(values)
    if not key:
        raise ValueError("No complete group of inputs.")
    entry = bundle["models"][key]
    cols = entry["columns"]
    frame = pd.DataFrame([[values[c] for c in cols]], columns=cols)
    model = entry["model"]
    probs = model.predict_proba(frame)[0]

    suggestions = []
    for i in np.argsort(probs)[::-1][:top_k]:
        if suggestions and probs[i] < 0.02:
            break
        crop = str(model.classes_[i])
        explanation = explain(crop, values, bundle["crop_ranges"])
        suggestions.append({
            "crop": crop,
            "similarity": round(float(probs[i]), 3),
            "matches": sum(1 for e in explanation if e["position"] == "within"),
            "checked": len(explanation),
            "explanation": explanation,
        })
    meta = bundle["metadata"]
    return {
        "input_set": key,
        "suggestions": suggestions,
        "warnings": range_warnings(values, bundle["feature_ranges"]),
        "model_version": meta["version"],
        "cv_accuracy": metrics.get("cv_by_inputs", {}).get(key, {}).get("rf_accuracy"),
        "chance_level": round(1 / len(bundle["class_names"]), 4),
        "crops_covered": list(bundle["class_names"]),
        "not_covered": meta.get("not_covered", []),
    }