import sys
from pathlib import Path

import pandas as pd

default = Path(__file__).resolve().parents[1] / "data" / "crop" / "Crop_recommendation.csv"
path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
if not path.exists():
    print(f"File not found: {path}")
    sys.exit(1)

df = pd.read_csv(path)
label = "label" if "label" in df.columns else df.columns[-1]
features = [c for c in df.columns if c != label]
print("Shape:", df.shape)
print("Columns:", list(df.columns))
print("\nMissing values per column:")
print(df.isna().sum().to_string())
print("\nExact duplicate rows:", int(df.duplicated().sum()))
print("\nRows per crop:")
print(df[label].value_counts().to_string())
print("\nFeature ranges (all rows):")
print(df[features].describe().loc[["min", "25%", "50%", "75%", "max"]].round(1).to_string())
print("\nPer-crop median of each feature:")
print(df.groupby(label)[features].median().round(1).to_string())
crops = set(df[label].astype(str).str.lower())
wanted = ["wheat", "sugarcane", "mustard", "potato", "barley", "rice", "maize"]
print("\nRegional crops NOT in this dataset:", [c for c in wanted if c not in crops])
