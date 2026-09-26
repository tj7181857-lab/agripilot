"""
AgriPilot :: synthetic pilot deployment.

Builds a cohort of smallholder farms with heterogeneous soils, irrigation
systems, crops and farmer profiles, then runs two consecutive growing years
(one near-normal monsoon, one deficit year) under all three policies on
identical weather.  Produces the tables the mid-semester evaluation needs.

    python -m pilot --farms 60 --years 2 --tune
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict

import numpy as np
import pandas as pd

from config import CROPS, SOILS, ECON, FarmerProfile, PEST_RULES
from optimizer import GRID, pareto_front, scalarised_utility, tune
from policies import AgentParams
from simulate import run_season

KHARIF = ["soybean", "cotton", "tomato"]
RABI = ["onion", "wheat", "grape"]
VILLAGES = ["Dindori", "Niphad", "Sinnar", "Yeola", "Chandwad", "Igatpuri"]


def make_cohort(n: int, rng: np.random.Generator) -> list[dict]:
    farms = []
    for i in range(n):
        wealth = float(rng.beta(2.2, 3.0))          # drives system + cash constraint
        soil = rng.choice(list(SOILS), p=[0.12, 0.26, 0.28, 0.22, 0.12])
        if wealth > 0.72:
            system = "drip"
        elif wealth > 0.42:
            system = rng.choice(["drip", "sprinkler"], p=[0.45, 0.55])
        else:
            system = rng.choice(["sprinkler", "flood"], p=[0.3, 0.7])
        kharif = str(rng.choice(KHARIF, p=[0.46, 0.34, 0.20]))
        rabi = str(rng.choice(RABI, p=[0.44, 0.38, 0.18]))
        if rabi == "grape" and system == "flood":
            system = "drip"                          # vineyards are drip by construction
        profile = FarmerProfile(
            risk_aversion=float(np.clip(rng.beta(2.6, 2.2), 0.05, 0.95)),
            water_scarcity=float(np.clip(rng.beta(2.4, 2.4), 0.03, 0.97)),
            cash_constraint=float(np.clip(1 - wealth + rng.normal(0, 0.08), 0.05, 0.95)),
            sustainability_pref=float(np.clip(rng.beta(2.0, 3.0), 0.02, 0.95)),
            tech_trust=float(np.clip(rng.normal(0.52, 0.13), 0.15, 0.9)),
            literacy_tier=str(rng.choice(["text", "voice", "icon"], p=[0.45, 0.35, 0.20])),
            language=str(rng.choice(["mr", "en"], p=[0.8, 0.2])),
            habit_irrigation_interval=int(rng.integers(4, 9)),
            habit_spray_interval=int(rng.integers(8, 15)),
        )
        farms.append({
            "farm_id": f"F{i+1:03d}", "village": str(rng.choice(VILLAGES)),
            "area_ha": float(np.round(np.clip(rng.gamma(2.1, 0.55), 0.3, 4.0), 2)),
            "soil": str(soil), "system": system, "kharif": kharif, "rabi": rabi,
            "profile": profile, "has_probe": bool(rng.random() < 0.82),
        })
    return farms


def tune_archetypes(seeds=(101, 202, 303, 404)) -> dict:
    """One tuned parameter set per (crop, water-scarcity tier)."""
    tuned, pareto = {}, {}
    tiers = {"scarce": 0.85, "assured": 0.25}
    for crop in CROPS:
        soil = "loam" if CROPS[crop].season == "rabi" else "clay_loam"
        system = "drip" if crop in ("grape", "onion", "tomato") else "flood"
        for tier, scarcity in tiers.items():
            prof = FarmerProfile(0.45, scarcity, 0.45, 0.4, 0.55, "text", "en", 6, 12)
            best, results = tune(crop, soil, system, prof, seeds=seeds)
            tuned[f"{crop}:{tier}"] = asdict(best)
            pareto[f"{crop}:{tier}"] = [
                {k: round(r[k], 3) for k in ("yield", "water_m3", "env_cost", "n_applied",
                                             "chem_sprays", "gross_margin")}
                | {"params": asdict(r["params"])}
                for r in pareto_front(results)]
            print(f"  tuned {crop:8s} {tier:8s} -> {asdict(best)}")
    return {"best": tuned, "pareto": pareto}


def run_pilot(farms, years: int, tuned: dict | None, out_dir: str) -> pd.DataFrame:
    rows = []
    monsoon = {0: 1.05, 1: 0.78, 2: 1.15}
    for yr in range(years):
        mi = monsoon.get(yr, 1.0)
        for f in farms:
            for season, crop in (("kharif", f["kharif"]), ("rabi", f["rabi"])):
                seed = abs(hash((f["farm_id"], yr, season))) % 1_000_000
                tier = "scarce" if f["profile"].water_scarcity > 0.5 else "assured"
                params = AgentParams(**tuned["best"][f"{crop}:{tier}"]) if tuned else AgentParams()
                for policy in ("farmer_practice", "agronomist", "agripilot"):
                    rec = run_season(crop, f["soil"], f["system"], f["profile"], policy,
                                     seed=seed, area_ha=f["area_ha"],
                                     params=params if policy == "agripilot" else None,
                                     monsoon_index=mi if CROPS[crop].season == "kharif" else 1.0)
                    rec.update({"farm_id": f["farm_id"], "village": f["village"],
                                "year": yr + 1, "season": season,
                                "water_scarcity": f["profile"].water_scarcity,
                                "cash_constraint": f["profile"].cash_constraint,
                                "sustainability_pref": f["profile"].sustainability_pref,
                                "literacy_tier": f["profile"].literacy_tier,
                                "utility": scalarised_utility(rec, f["profile"])})
                    rows.append(rec)
    df = pd.DataFrame(rows)
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "pilot_results.csv"), index=False)
    return df


def summarise(df: pd.DataFrame) -> dict:
    piv = df.pivot_table(index=["farm_id", "year", "season", "crop"], columns="policy",
                         values=["yield_t_ha", "water_m3_per_ha", "n_applied", "chem_sprays",
                                 "pesticide_load", "gross_margin", "n_leached", "env_cost",
                                 "runoff_mm", "water_productivity_kg_m3", "cost",
                                 "biodiversity_index", "stress_days"])

    def delta(metric, a="agripilot", b="farmer_practice", pct=True):
        x, y = piv[(metric, a)], piv[(metric, b)]
        d = (x - y) / y.replace(0, np.nan) * 100 if pct else (x - y)
        return float(np.nanmean(d))

    agent = df[df.policy == "agripilot"]
    base = df[df.policy == "farmer_practice"]
    agro = df[df.policy == "agronomist"]
    extra_cost = float(ECON["sensor_amortised_per_season"])
    margin_gain = float(piv[("gross_margin", "agripilot")].mean() -
                        piv[("gross_margin", "farmer_practice")].mean())

    out = {
        "n_farms": int(df.farm_id.nunique()),
        "n_farm_seasons": int(len(piv)),
        "yield_gain_vs_farmer_pct": delta("yield_t_ha"),
        "yield_gain_vs_agronomist_pct": delta("yield_t_ha", b="agronomist"),
        "water_saving_pct": -delta("water_m3_per_ha"),
        "water_productivity_gain_pct": delta("water_productivity_kg_m3"),
        "nitrogen_reduction_pct": -delta("n_applied"),
        "chem_spray_reduction_pct": -delta("chem_sprays"),
        "pesticide_load_reduction_pct": -delta("pesticide_load"),
        "n_leaching_reduction_pct": -delta("n_leached"),
        "runoff_reduction_mm": -delta("runoff_mm", pct=False),
        "env_cost_reduction_pct": -delta("env_cost"),
        "biodiversity_index_gain_pct": delta("biodiversity_index"),
        "gross_margin_gain_pct": delta("gross_margin"),
        "gross_margin_gain_inr_per_ha": margin_gain,
        "roi_on_agent_cost": margin_gain / extra_cost,
        "mean_adoption_rate": float(agent.adoption_rate.mean()),
        "mean_final_trust": float(agent.final_trust.mean()),
        "stress_days_delta": delta("stress_days", pct=False),
        "means": {
            p: {m: float(g[m].mean()) for m in
                ("yield_t_ha", "water_m3_per_ha", "water_productivity_kg_m3", "n_applied",
                 "n_use_efficiency", "chem_sprays", "bio_sprays", "n_leached", "runoff_mm",
                 "cost", "revenue", "gross_margin", "env_cost", "biodiversity_index",
                 "stress_days", "residue_penalty")}
            for p, g in (("farmer_practice", base), ("agronomist", agro), ("agripilot", agent))},
        "by_crop": {
            c: {"yield_gain_pct": float(np.nanmean(
                    (g[g.policy == "agripilot"].yield_t_ha.mean() -
                     g[g.policy == "farmer_practice"].yield_t_ha.mean()) /
                    g[g.policy == "farmer_practice"].yield_t_ha.mean() * 100)),
                "water_saving_pct": float(
                    (1 - g[g.policy == "agripilot"].water_m3_per_ha.mean() /
                     g[g.policy == "farmer_practice"].water_m3_per_ha.mean()) * 100),
                "n_reduction_pct": float(
                    (1 - g[g.policy == "agripilot"].n_applied.mean() /
                     g[g.policy == "farmer_practice"].n_applied.mean()) * 100),
                "margin_gain_inr": float(g[g.policy == "agripilot"].gross_margin.mean() -
                                         g[g.policy == "farmer_practice"].gross_margin.mean())}
            for c, g in df.groupby("crop")},
        "by_year": {
            int(y): {"water_saving_pct": float(
                        (1 - g[g.policy == "agripilot"].water_m3_per_ha.mean() /
                         g[g.policy == "farmer_practice"].water_m3_per_ha.mean()) * 100),
                     "yield_gain_pct": float(
                        (g[g.policy == "agripilot"].yield_t_ha.mean() /
                         g[g.policy == "farmer_practice"].yield_t_ha.mean() - 1) * 100)}
            for y, g in df.groupby("year")},
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--farms", type=int, default=60)
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--out", default="../outputs")
    args = ap.parse_args()

    rng = np.random.default_rng(2026)
    farms = make_cohort(args.farms, rng)
    os.makedirs(args.out, exist_ok=True)

    tuned = None
    tuned_path = os.path.join(args.out, "tuned_params.json")
    if args.tune:
        print("tuning policy parameters per crop x water-scarcity tier ...")
        tuned = tune_archetypes()
        with open(tuned_path, "w") as fh:
            json.dump(tuned, fh, indent=1)
    elif os.path.exists(tuned_path):
        tuned = json.load(open(tuned_path))

    print(f"running pilot: {len(farms)} farms x {args.years} years x 2 seasons x 3 policies ...")
    df = run_pilot(farms, args.years, tuned, args.out)
    summary = summarise(df)
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)

    cohort = [{k: (asdict(v) if k == "profile" else v) for k, v in f.items()} for f in farms]
    with open(os.path.join(args.out, "cohort.json"), "w") as fh:
        json.dump(cohort, fh, indent=1)

    print(json.dumps({k: v for k, v in summary.items()
                      if isinstance(v, (int, float))}, indent=1))


if __name__ == "__main__":
    main()
