"""
AgriPilot :: multi-objective policy optimisation.

The agent has four free parameters (risk budget, planned deficit, spray
hurdle, nitrogen safety factor).  Their best setting is not universal: it
depends on the crop, the soil, and above all on what *this* farmer is trying to
maximise.  A farmer on a failing borewell wants water productivity; a farmer
with an export contract wants clean produce; a cash-constrained farmer wants
the highest margin per rupee spent.

`tune()` runs a grid search where every candidate is scored on independent
weather realisations (common random numbers across candidates, so the
comparison is paired), using a scalarised objective built from the farmer's
own weights.  `pareto_front()` returns the non-dominated set over the raw
objectives (yield, water, environmental load) for reporting.
"""
from __future__ import annotations

import itertools
from dataclasses import asdict, replace
from typing import Iterable

import numpy as np

from config import ECON, FarmerProfile
from policies import AgentParams
from simulate import run_season

GRID = {
    "risk_budget": [0.07, 0.15, 0.26],
    "deficit_factor": [0.0, 0.08, 0.16],
    "spray_threshold": [0.8, 1.5, 2.5],
    "n_safety": [1.0, 1.15],
}

WATER_SHADOW = 12.0     # INR per m3 of scarcity-weighted groundwater


def scalarised_utility(rec: dict, profile: FarmerProfile) -> float:
    w = profile.objective_weights()
    return (w["yield"] * rec["revenue"]
            - w["cost"] * rec["cost"]
            - w["water"] * WATER_SHADOW * rec["water_m3_per_ha"] * profile.water_scarcity
            - w["environment"] * rec["env_cost"])


def evaluate(params: AgentParams, crop: str, soil: str, system: str,
             profile: FarmerProfile, seeds: Iterable[int]) -> dict:
    recs = [run_season(crop, soil, system, profile, "agripilot", seed=s, params=params)
            for s in seeds]
    u = np.array([scalarised_utility(r, profile) for r in recs])
    return {
        "params": params,
        "utility_mean": float(u.mean()),
        "utility_p10": float(np.percentile(u, 10)),   # downside a smallholder feels
        "yield": float(np.mean([r["yield_t_ha"] for r in recs])),
        "water_m3": float(np.mean([r["water_m3_per_ha"] for r in recs])),
        "n_applied": float(np.mean([r["n_applied"] for r in recs])),
        "chem_sprays": float(np.mean([r["chem_sprays"] for r in recs])),
        "env_cost": float(np.mean([r["env_cost"] for r in recs])),
        "gross_margin": float(np.mean([r["gross_margin"] for r in recs])),
    }


def tune(crop: str, soil: str, system: str, profile: FarmerProfile,
         seeds=(101, 202, 303, 404, 505), risk_lambda: float = 0.35) -> tuple[AgentParams, list[dict]]:
    """Grid search; the selection criterion is mean utility penalised by downside."""
    results = []
    for combo in itertools.product(*GRID.values()):
        p = AgentParams(**dict(zip(GRID.keys(), combo)))
        res = evaluate(p, crop, soil, system, profile, seeds)
        res["score"] = (1 - risk_lambda) * res["utility_mean"] + risk_lambda * res["utility_p10"]
        results.append(res)
    # epsilon-constraint: never buy margin with more than 1% of attainable yield.
    best_yield = max(r["yield"] for r in results)
    feasible = [r for r in results if r["yield"] >= 0.99 * best_yield] or results
    feasible.sort(key=lambda r: -r["score"])
    results.sort(key=lambda r: -r["score"])
    return feasible[0]["params"], results


def pareto_front(results: list[dict]) -> list[dict]:
    """Non-dominated set over (max yield, min water, min environmental cost)."""
    front = []
    for a in results:
        dominated = False
        for b in results:
            if b is a:
                continue
            if (b["yield"] >= a["yield"] and b["water_m3"] <= a["water_m3"]
                    and b["env_cost"] <= a["env_cost"]
                    and (b["yield"] > a["yield"] or b["water_m3"] < a["water_m3"]
                         or b["env_cost"] < a["env_cost"])):
                dominated = True
                break
        if not dominated:
            front.append(a)
    return front
