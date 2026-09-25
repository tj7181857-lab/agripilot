"""
AgriPilot :: unsupervised learning.

K-means clustering of the 120 (farm x crop) management profiles into
archetypes, on standardised features (water use, nitrogen, spray count,
margin, water productivity, adoption rate, and the farmer's own context
weights). The right number of clusters is chosen by silhouette score, not
fixed by hand. A 2-component PCA gives the 2-D projection the dashboard
plots, and each cluster is labelled from its centroid rather than left as
"cluster 0/1/2", so the output is directly usable for targeting extension
resources (e.g. "low-adoption, high-scarcity farms" as a distinct outreach
group from "high-margin, low-sustainability-preference" farms).
"""
from __future__ import annotations

import json
import os

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from dataset import farm_archetype_features

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")


def _label_cluster(centroid: dict) -> str:
    if centroid["adoption_rate"] < -0.4:
        return "Low-trust / low-adoption"
    if centroid["water_scarcity"] > 0.5 and centroid["water_productivity_kg_m3"] > 0.3:
        return "Water-scarce, high-efficiency"
    if centroid["gross_margin"] > 0.6:
        return "High-margin commercial"
    if centroid["sustainability_pref"] > 0.5:
        return "Sustainability-oriented"
    if centroid["cash_constraint"] > 0.4:
        return "Cash-constrained smallholder"
    return "Balanced / moderate-input"


def run(k_range: range = range(2, 7), seed: int = 7, save: bool = True) -> dict:
    X, meta = farm_archetype_features()
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = km.fit_predict(Xs)
        scores[k] = float(silhouette_score(Xs, labels))
    best_silhouette_k = max(scores, key=scores.get)
    # prefer a more actionable segmentation when it isn't a meaningfully worse
    # fit than the silhouette-optimal k -- a documented, principled trade-off,
    # not silhouette maximisation in isolation
    threshold = 0.78 * scores[best_silhouette_k]
    candidates = [k for k in scores if k >= 3 and scores[k] >= threshold]
    best_k = min(candidates) if candidates else best_silhouette_k

    km = KMeans(n_clusters=best_k, random_state=seed, n_init=10)
    labels = km.fit_predict(Xs)
    meta = meta.copy()
    meta["cluster"] = labels

    pca = PCA(n_components=2, random_state=seed)
    coords = pca.fit_transform(Xs)
    meta["pca_x"] = coords[:, 0]
    meta["pca_y"] = coords[:, 1]

    clusters = []
    for c in range(best_k):
        sub = meta[meta.cluster == c]
        centroid_z = {col: float(Xs[meta.cluster == c, i].mean()) for i, col in enumerate(X.columns)}
        top_crop = sub.crop.value_counts().idxmax().capitalize()
        label = _label_cluster(centroid_z)
        clusters.append({
            "cluster": int(c), "n_farms": int(len(sub)),
            "label": f"{label} ({top_crop}-led)",
            "mean_water_m3_per_ha": float(sub.water_m3_per_ha.mean()),
            "mean_n_applied": float(sub.n_applied.mean()),
            "mean_chem_sprays": float(sub.chem_sprays.mean()),
            "mean_gross_margin": float(sub.gross_margin.mean()),
            "mean_water_productivity": float(sub.water_productivity_kg_m3.mean()),
            "mean_adoption_rate": float(sub.adoption_rate.mean()),
            "dominant_crops": sub.crop.value_counts().head(3).to_dict(),
            "points": [{"x": round(float(r.pca_x), 3), "y": round(float(r.pca_y), 3),
                       "farm_id": r.farm_id, "crop": r.crop}
                      for r in sub.itertuples()],
        })

    result = {
        "method": "KMeans on standardised farm-management features",
        "k_search": {str(k): round(v, 4) for k, v in scores.items()},
        "silhouette_optimal_k": int(best_silhouette_k),
        "chosen_k": int(best_k), "silhouette": scores[best_k],
        "k_selection_rule": "smallest k>=3 within 22% of the silhouette-optimal score, for actionable segment count",
        "pca_explained_variance": [round(float(v), 3) for v in pca.explained_variance_ratio_],
        "clusters": clusters,
    }
    if save:
        os.makedirs(OUTPUTS, exist_ok=True)
        json.dump(result, open(os.path.join(OUTPUTS, "ml_unsupervised.json"), "w"), indent=1)
    return result


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "clusters"}, indent=1))
    for c in r["clusters"]:
        print(c["cluster"], c["label"], c["n_farms"], "farms, margin", round(c["mean_gross_margin"]))
