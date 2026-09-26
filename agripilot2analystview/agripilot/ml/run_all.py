"""
AgriPilot :: run every ML module and assemble one summary file.

    python -m ml.run_all

Writes outputs/ml_summary.json, the single file the dashboard's "ML Insights"
tab and the report both read from.
"""
import json
import os
import time

import supervised
import unsupervised
import anomaly
import reinforcement

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")


def main():
    t0 = time.time()
    print("[1/4] supervised learning (yield regression + stress classification)...")
    sup = supervised.run()
    print("      yield efficiency R^2 =", round(sup["yield_regressor"]["cv_r2_mean"], 3),
          " stress-risk accuracy =", round(sup["stress_classifier"]["cv_accuracy_mean"], 3))

    print("[2/4] unsupervised learning (K-means farm archetypes)...")
    uns = unsupervised.run()
    print("      chosen k =", uns["chosen_k"], " silhouette =", round(uns["silhouette"], 3))

    print("[3/4] anomaly detection (Isolation Forest on sensor streams)...")
    ano = anomaly.run()
    print("      flagged", ano["total_flagged"], "of", ano["total_days_scored"], "sensor-days")

    print("[4/4] reinforcement learning (tabular Q-learning irrigation agent)...")
    rl = reinforcement.run()
    print("      Q-learning yield =", round(rl["q_learning_agent"]["mean_yield_t_ha"], 2),
          " vs analytic agent =", round(rl["agripilot_analytic_agent"]["mean_yield_t_ha"], 2))

    summary = {
        "generated_in_seconds": round(time.time() - t0, 1),
        "supervised": sup, "unsupervised": {k: v for k, v in uns.items() if k != "clusters"},
        "unsupervised_clusters": uns["clusters"],
        "anomaly": {k: v for k, v in ano.items() if k != "farms"},
        "anomaly_by_farm": ano["farms"],
        "reinforcement": rl,
    }
    os.makedirs(OUTPUTS, exist_ok=True)
    json.dump(summary, open(os.path.join(OUTPUTS, "ml_summary.json"), "w"), indent=1)
    print("done in", round(time.time() - t0, 1), "s -> outputs/ml_summary.json")


if __name__ == "__main__":
    main()
