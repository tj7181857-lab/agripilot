"""
AgriPilot :: ML dataset builder.

Turns the 720-row pilot output (agripilot/pilot.py) into a clean feature
matrix. Two datasets are exposed:

  season_features()   one row per simulated farm-season, engineered for the
                       supervised-learning tasks (yield regression, stress
                       classification) and for clustering.
  daily_features()     one row per sensor-observed day across the four demo
                       farm traces, used for the anomaly-detection model.

Categorical columns are one-hot encoded here rather than inside each model,
so every downstream script shares one definition of "the features".
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")

CATEGORICAL = ["crop", "soil", "system", "season"]
NUMERIC_BASE = ["area_ha", "monsoon_index", "irrigation_mm", "n_applied", "chem_sprays",
                "bio_sprays", "water_scarcity", "cash_constraint", "sustainability_pref",
                "year"]
TARGET_REG = "yield_t_ha"
TARGET_CLF = "high_stress"          # engineered below


def load_raw(path: str = None) -> pd.DataFrame:
    path = path or os.path.join(OUTPUTS, "pilot_results.csv")
    return pd.read_csv(path)


def season_features(policy: str = "agripilot", path: str = None) -> tuple[pd.DataFrame, pd.Series, pd.Series, list[str]]:
    """
    Returns (X, y_yield, y_high_stress, feature_names) for one policy's rows.
    Restricting to a single policy avoids leaking "which policy" into the
    yield model through a spuriously predictive categorical column.
    """
    df = load_raw(path)
    df = df[df.policy == policy].reset_index(drop=True)

    df["high_stress"] = (df["stress_days"] > df["stress_days"].median()).astype(int)
    df["water_intensity"] = df["irrigation_mm"] / df["area_ha"].clip(lower=0.1)
    df["n_intensity"] = df["n_applied"] / df["area_ha"].clip(lower=0.1)
    # yield realised as a fraction of that crop's attainable potential -- this is
    # the quantity actually driven by management (water/N/pest), unlike raw
    # yield_t_ha which is dominated by which crop was planted
    df["yield_efficiency"] = (df["yield_t_ha"] / df["y_max"]).clip(0, 1.2)

    num_cols = NUMERIC_BASE + ["water_intensity", "n_intensity"]
    X_num = df[num_cols].copy()
    X_cat = pd.get_dummies(df[CATEGORICAL], prefix=CATEGORICAL)
    X = pd.concat([X_num, X_cat], axis=1)
    X.columns = [str(c) for c in X.columns]

    return X, df["yield_efficiency"], df[TARGET_CLF], list(X.columns)


def farm_archetype_features(path: str = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    One row per (farm_id, crop) averaged across years, for clustering farms
    into management archetypes. Returns (X_scaled_ready, meta) where meta
    keeps the human-readable columns for labelling clusters afterwards.
    """
    df = load_raw(path)
    df = df[df.policy == "agripilot"]
    agg = df.groupby(["farm_id", "crop"]).agg(
        water_m3_per_ha=("water_m3_per_ha", "mean"),
        n_applied=("n_applied", "mean"),
        chem_sprays=("chem_sprays", "mean"),
        gross_margin=("gross_margin", "mean"),
        water_productivity_kg_m3=("water_productivity_kg_m3", "mean"),
        adoption_rate=("adoption_rate", "mean"),
        water_scarcity=("water_scarcity", "mean"),
        cash_constraint=("cash_constraint", "mean"),
        sustainability_pref=("sustainability_pref", "mean"),
        area_ha=("area_ha", "mean"),
    ).reset_index()
    feature_cols = ["water_m3_per_ha", "n_applied", "chem_sprays", "gross_margin",
                     "water_productivity_kg_m3", "adoption_rate", "water_scarcity",
                     "cash_constraint", "sustainability_pref"]
    return agg[feature_cols], agg


def daily_sensor_features(demo_path: str = None) -> pd.DataFrame:
    """Flatten the four demo-farm daily traces into one frame for anomaly detection."""
    demo_path = demo_path or os.path.join(OUTPUTS, "demo_farms_en.json")
    farms = json.load(open(demo_path))
    rows = []
    for f in farms:
        for d in f["trace"]:
            rows.append({
                "farm_id": f["id"], "crop": f["crop"], "day": d["day"],
                "rain": d.get("rain", 0.0), "etc": d.get("etc", 0.0),
                "irrigation": d.get("irrigation", 0.0),
                "depletion_ratio": d.get("dr", 0.0) / max(d.get("taw", 1.0), 1e-6),
                "raw_ratio": d.get("raw", 0.0) / max(d.get("taw", 1.0), 1e-6),
                "ndvi": d.get("ndvi", np.nan), "pest": d.get("pest", 0.0),
            })
    return pd.DataFrame(rows)
