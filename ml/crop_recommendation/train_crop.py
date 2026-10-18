"""Train and honestly evaluate the crop-recommendation models.

Data: Kaggle 'Crop Recommendation Dataset' (augmented, 22 crops, 100 rows each).
Run from the ml folder:  python crop_recommendation/train_crop.py

No hyperparameter tuning is done, so the cross-validation scores are not selected on.
One Random Forest is trained per combination of inputs the farmer can give
(nutrients N/P/K, soil pH, climate) instead of filling missing values with guesses.
"""
import hashlib
import itertools
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.neighbors import NearestCentroid, NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ML_DIR = Path(__file__).resolve().parents[1]
CSV = ML_DIR / "data" / "crop" / "Crop_recommendation.csv"
OUT = ML_DIR / "artifacts" / "crop" / "v1"
SEED = 42
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
GROUPS = {
    "nutrients": ["N", "P", "K"],
    "ph": ["ph"],
    "climate": ["temperature", "humidity", "rainfall"],
}


def input_sets():
    names = list(GROUPS)
    for r in range(len(names), 0, -1):
        for combo in itertools.combinations(names, r):
            yield "+".join(combo), [c for g in combo for c in GROUPS[g]]


def make_rf():
    return RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=-1)


def make_baseline():
    return make_pipeline(StandardScaler(), NearestCentroid())


def cv_scores(X, y, cols, make_model):
    splitter = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED)
    accs, f1s = [], []
    for tr, te in splitter.split(X, y):
        model = make_model()
        model.fit(X.iloc[tr][cols], y[tr])
        pred = model.predict(X.iloc[te][cols])
        accs.append(accuracy_score(y[te], pred))
        f1s.append(f1_score(y[te], pred, average="macro"))
    return np.array(accs), np.array(f1s)


def main():
    if not CSV.exists():
        print(f"File not found: {CSV}")
        return
    df = pd.read_csv(CSV)
    X, y = df[FEATURES], df["label"].to_numpy()
    classes = sorted(set(y))
    print(f"Rows: {len(df)}, crops: {len(classes)}, chance level: {1 / len(classes):.3f}\n")

    # 1. Near-duplicate check (distance to the nearest OTHER row, standardised units)
    z = StandardScaler().fit_transform(X)
    nn = NearestNeighbors(n_neighbors=2).fit(z).kneighbors(z)[0][:, 1]
    nn_pct = [round(float(np.percentile(nn, p)), 3) for p in (1, 5, 25, 50, 75)]
    print("Distance to the nearest other row (percentiles 1/5/25/50/75):", nn_pct)
    print(f"Rows with a neighbour closer than 0.05: {np.mean(nn < 0.05) * 100:.1f}%, "
          f"closer than 0.10: {np.mean(nn < 0.10) * 100:.1f}%\n")

    # 2. Cross-validated comparison for every combination of inputs
    results = {}
    print(f"{'inputs available':<26}{'baseline':>10}{'RF acc':>9}{'+/-':>7}{'RF macro F1':>13}")
    for key, cols in input_sets():
        b_acc, _ = cv_scores(X, y, cols, make_baseline)
        r_acc, r_f1 = cv_scores(X, y, cols, make_rf)
        results[key] = {
            "baseline_accuracy": round(float(b_acc.mean()), 4),
            "rf_accuracy": round(float(r_acc.mean()), 4),
            "rf_accuracy_fold_std": round(float(r_acc.std()), 4),
            "rf_macro_f1": round(float(r_f1.mean()), 4),
        }
        print(f"{key:<26}{b_acc.mean():>10.3f}{r_acc.mean():>9.3f}{r_acc.std():>7.3f}{r_f1.mean():>13.3f}")

    # 3. Per-crop recall, confusions and noise sensitivity (all inputs, 5-fold)
    skf = StratifiedKFold(5, shuffle=True, random_state=SEED)
    pred = np.empty(len(y), dtype=object)
    levels = [0.0, 0.05, 0.10, 0.20]
    rng = np.random.default_rng(SEED)
    sd = X.std().to_numpy()
    noisy = {lvl: [] for lvl in levels}
    for tr, te in skf.split(X, y):
        model = make_rf().fit(X.iloc[tr], y[tr])
        pred[te] = model.predict(X.iloc[te])
        for lvl in levels:
            jitter = rng.normal(0, 1, (len(te), len(FEATURES))) * sd * lvl
            frame = pd.DataFrame(X.iloc[te].to_numpy() + jitter, columns=FEATURES)
            noisy[lvl].append(accuracy_score(y[te], model.predict(frame)))

    recall = {c: float(np.mean(pred[y == c] == c)) for c in classes}
    print("\nPer-crop recall, all inputs (lowest first):")
    for c, r in sorted(recall.items(), key=lambda kv: kv[1])[:8]:
        print(f"  {r:.2f}  {c}")
    confusions = Counter((t, p) for t, p in zip(y, pred) if t != p)
    print("Most common confusions (true -> predicted):")
    for (t, p), n in confusions.most_common(8):
        print(f"  {n:3d}  {t} -> {p}")
    noise = {str(lvl): round(float(np.mean(v)), 4) for lvl, v in noisy.items()}
    print("\nAccuracy when inputs are noisy (noise = fraction of each feature's spread):")
    for lvl, v in noise.items():
        print(f"  noise {float(lvl):.2f}: {v:.3f}")

    # 4. Final models, plus the ranges used to explain each suggestion
    final = {key: {"columns": cols, "model": make_rf().fit(X[cols], y)} for key, cols in input_sets()}
    importances = sorted(
        zip(FEATURES, final["nutrients+ph+climate"]["model"].feature_importances_), key=lambda t: -t[1]
    )
    print("\nRough feature importance (all inputs):", [(f, round(float(v), 3)) for f, v in importances])

    crop_ranges = {}
    for crop, g in df.groupby("label"):
        crop_ranges[crop] = {
            f: {
                "p10": round(float(g[f].quantile(0.1)), 1),
                "p50": round(float(g[f].quantile(0.5)), 1),
                "p90": round(float(g[f].quantile(0.9)), 1),
            }
            for f in FEATURES
        }
    feature_ranges = {f: {"min": float(df[f].min()), "max": float(df[f].max())} for f in FEATURES}

    metadata = {
        "version": "v1",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "scikit_learn": sklearn.__version__,
        "python": platform.python_version(),
        "csv_sha256": hashlib.sha256(CSV.read_bytes()).hexdigest(),
        "rows": len(df),
        "crops": len(classes),
        "random_forest": {"n_estimators": 300, "tuned": False},
        "cv": "5-fold x 3 repeats, stratified. Folds overlap, so +/- is a spread, not a confidence interval.",
        "note": "Augmented public dataset. Scores show separability within this table, not agronomic validity.",
        "not_covered": ["wheat", "sugarcane", "mustard", "potato", "barley"],
        "rainfall_period": "not stated in the dataset",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"models": final, "class_names": classes, "feature_ranges": feature_ranges,
         "crop_ranges": crop_ranges, "metadata": metadata},
        OUT / "model.joblib", compress=3,
    )
    (OUT / "crop_ranges.json").write_text(json.dumps(crop_ranges, indent=2), encoding="utf-8")
    (OUT / "metrics.json").write_text(
        json.dumps({"metadata": metadata, "cv_by_inputs": results, "per_crop_recall": recall,
                    "noise_accuracy": noise, "nearest_neighbour_percentiles": nn_pct}, indent=2),
        encoding="utf-8",
    )
    size_mb = (OUT / "model.joblib").stat().st_size / 1_048_576
    print(f"\nSaved to {OUT} (model.joblib is {size_mb:.1f} MB)")


if __name__ == "__main__":
    main()