"""
AgriPilot :: supervised learning.

Two models trained on the 240 AgriPilot-policy farm-seasons:

  YieldRegressor      predicts yield_t_ha from practice + context features.
                       Used two ways: (a) as an independent cross-check of
                       the analytic FAO-33 yield function -- if a learned
                       model trained on the same simulation output can't
                       recover yield reasonably well, that is itself a
                       useful diagnostic; (b) to rank which levers (water,
                       nitrogen, sprays, farmer context) matter most, via
                       permutation importance.

  StressRiskClassifier predicts whether a farm-season will land in the
                       high-water-stress half of the distribution, from
                       information available *before* the season plays out
                       (soil, crop, system, scarcity, cash constraint) --
                       i.e. this is the model a district agronomist could
                       run in spring to triage which farms need closer
                       attention.

Both use gradient-boosted trees (good default for small tabular data with
mixed numeric/categorical features) and are evaluated with grouped K-fold
cross-validation, grouped by farm_id so the same farm never appears in both
the train and test fold -- a plain shuffle-split would leak farm identity
across the split and overstate accuracy.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error,
                             r2_score, roc_auc_score)
from sklearn.model_selection import GroupKFold

from dataset import load_raw, season_features

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")


def _groups():
    df = load_raw()
    return df[df.policy == "agripilot"].reset_index(drop=True)["farm_id"]


def train_yield_regressor(n_splits: int = 5, seed: int = 7) -> dict:
    X, y, _, cols = season_features()
    groups = _groups()
    gkf = GroupKFold(n_splits=n_splits)
    fold_r2, fold_mae = [], []
    for tr, te in gkf.split(X, y, groups):
        m = GradientBoostingRegressor(random_state=seed, n_estimators=220,
                                      max_depth=3, learning_rate=0.06, subsample=0.85)
        m.fit(X.iloc[tr], y.iloc[tr])
        pred = m.predict(X.iloc[te])
        fold_r2.append(r2_score(y.iloc[te], pred))
        fold_mae.append(mean_absolute_error(y.iloc[te], pred))

    # final model on all data, for feature importance + the app's "what drives yield" panel
    model = GradientBoostingRegressor(random_state=seed, n_estimators=220,
                                      max_depth=3, learning_rate=0.06, subsample=0.85)
    model.fit(X, y)
    imp = permutation_importance(model, X, y, n_repeats=25, random_state=seed, scoring="r2")
    order = np.argsort(imp.importances_mean)[::-1]
    top_features = [{"feature": cols[i], "importance": round(float(imp.importances_mean[i]), 4)}
                     for i in order[:10]]

    result = {
        "task": "yield_efficiency_regression", "model": "GradientBoostingRegressor",
        "cv_folds": n_splits, "cv_scheme": "GroupKFold by farm_id",
        "cv_r2_mean": float(np.mean(fold_r2)), "cv_r2_std": float(np.std(fold_r2)),
        "cv_mae_efficiency": float(np.mean(fold_mae)),
        "baseline_mae_efficiency": float(mean_absolute_error(y, np.full(len(y), y.mean()))),
        "n_samples": int(len(y)), "n_features": int(X.shape[1]),
        "top_features": top_features,
    }
    return result, model


def train_stress_classifier(n_splits: int = 5, seed: int = 7) -> dict:
    X, _, y, cols = season_features()
    # only pre-season-known features: drop anything the agent could not know in advance
    preseason = [c for c in X.columns if c not in
                 ("irrigation_mm", "n_applied", "chem_sprays", "bio_sprays",
                  "water_intensity", "n_intensity")]
    Xp = X[preseason]
    groups = _groups()
    gkf = GroupKFold(n_splits=n_splits)
    fold_acc, fold_f1, fold_auc = [], [], []
    for tr, te in gkf.split(Xp, y, groups):
        m = GradientBoostingClassifier(random_state=seed, n_estimators=180,
                                       max_depth=2, learning_rate=0.08, subsample=0.85)
        m.fit(Xp.iloc[tr], y.iloc[tr])
        pred = m.predict(Xp.iloc[te])
        proba = m.predict_proba(Xp.iloc[te])[:, 1]
        fold_acc.append(accuracy_score(y.iloc[te], pred))
        fold_f1.append(f1_score(y.iloc[te], pred))
        if len(set(y.iloc[te])) > 1:
            fold_auc.append(roc_auc_score(y.iloc[te], proba))

    model = GradientBoostingClassifier(random_state=seed, n_estimators=180,
                                       max_depth=2, learning_rate=0.08, subsample=0.85)
    model.fit(Xp, y)
    imp = permutation_importance(model, Xp, y, n_repeats=25, random_state=seed, scoring="f1")
    order = np.argsort(imp.importances_mean)[::-1]
    top_features = [{"feature": preseason[i], "importance": round(float(imp.importances_mean[i]), 4)}
                     for i in order[:8]]

    result = {
        "task": "stress_risk_classification", "model": "GradientBoostingClassifier",
        "cv_folds": n_splits, "cv_scheme": "GroupKFold by farm_id",
        "cv_accuracy_mean": float(np.mean(fold_acc)), "cv_f1_mean": float(np.mean(fold_f1)),
        "cv_auc_mean": float(np.mean(fold_auc)) if fold_auc else None,
        "baseline_accuracy": float(max(y.mean(), 1 - y.mean())),
        "n_samples": int(len(y)), "n_features": int(Xp.shape[1]),
        "top_features": top_features,
    }
    return result, model


def run(save: bool = True) -> dict:
    reg_result, _ = train_yield_regressor()
    clf_result, _ = train_stress_classifier()
    out = {"yield_regressor": reg_result, "stress_classifier": clf_result}
    if save:
        os.makedirs(OUTPUTS, exist_ok=True)
        json.dump(out, open(os.path.join(OUTPUTS, "ml_supervised.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=1))
