"""
AgriPilot :: unsupervised anomaly detection.

An Isolation Forest flags days in the sensor stream that look mechanically
odd -- not "bad weather" (which is normal and the agent already handles)
but days where the *relationship* between rainfall, crop water use,
irrigation and depletion doesn't fit the pattern the rest of the season
shows. In deployment this is the model that would sit between the raw
sensor feed and the state estimator: a flagged day gets its soil-moisture
reading down-weighted (same mechanism `sensors.StateEstimator` already uses
for a "suspect" reading) and is queued for a technician to check the probe.

This is deliberately a separate, unsupervised check from the physically-
grounded Kalman filter in `sensors.py` -- the filter assumes the physics is
right and the sensor might be noisy; the anomaly detector makes no physical
assumption at all and instead learns "normal" empirically, which catches
failure modes the physics-based filter isn't looking for (e.g. a probe
mis-installed at the wrong depth from day one, which is internally
consistent but consistently wrong).
"""
from __future__ import annotations

import json
import os

import numpy as np
from sklearn.ensemble import IsolationForest

from dataset import daily_sensor_features

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")

FEATURES = ["rain", "etc", "irrigation", "depletion_ratio", "raw_ratio", "pest"]


def run(contamination: float = 0.05, seed: int = 7, save: bool = True) -> dict:
    df = daily_sensor_features()
    out = {}
    all_flagged = []
    for farm_id, sub in df.groupby("farm_id"):
        X = sub[FEATURES].fillna(sub[FEATURES].median())
        model = IsolationForest(n_estimators=200, contamination=contamination,
                                random_state=seed)
        labels = model.fit_predict(X)          # -1 = anomaly
        scores = -model.score_samples(X)        # higher = more anomalous
        sub = sub.assign(anomaly=(labels == -1), anomaly_score=scores)
        flagged = sub[sub.anomaly].sort_values("anomaly_score", ascending=False)
        out[farm_id] = {
            "crop": sub.crop.iloc[0], "n_days": int(len(sub)),
            "n_flagged": int(len(flagged)),
            "flagged_days": [
                {"day": int(r.day), "score": round(float(r.anomaly_score), 3),
                 "rain": round(float(r.rain), 1), "irrigation": round(float(r.irrigation), 1),
                 "depletion_ratio": round(float(r.depletion_ratio), 2)}
                for r in flagged.itertuples()],
        }
        all_flagged.append(flagged.assign(farm_id=farm_id))

    result = {
        "method": "IsolationForest, per-farm, on (rain, crop water use, irrigation, "
                  "depletion ratio, stress-threshold ratio, pest pressure)",
        "contamination": contamination,
        "farms": out,
        "total_days_scored": int(len(df)),
        "total_flagged": int(sum(v["n_flagged"] for v in out.values())),
    }
    if save:
        os.makedirs(OUTPUTS, exist_ok=True)
        json.dump(result, open(os.path.join(OUTPUTS, "ml_anomaly.json"), "w"), indent=1)
    return result


if __name__ == "__main__":
    r = run()
    print("scored", r["total_days_scored"], "days, flagged", r["total_flagged"])
    for fid, v in r["farms"].items():
        print(" ", fid, v["crop"], v["n_flagged"], "flagged of", v["n_days"])
