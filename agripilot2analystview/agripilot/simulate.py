"""
AgriPilot :: season simulator and evaluation harness.

run_season() wires the whole stack together for one field-season and returns a
flat record of agronomic, economic, environmental and human metrics.  The same
weather realisation and the same pest stochastics are replayed for every policy
(paired comparison), so differences between policies are attributable to the
decisions, not to luck.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

import numpy as np

import explain
from config import CROPS, SOILS, ECON, ENV, IRRIGATION_SYSTEMS, PEST_RULES, FarmerProfile
from farmer import FarmerAgent
from field_model import Field
from policies import (Action, AgentParams, AgriPilotAgent, AgronomistProtocol,
                      FarmerPractice)
from sensors import FarmerReport, SatelliteNDVI, SoilMoistureProbe, StateEstimator
from tools import ActuatorBus, ToolCall
from weather import ForecastProvider, WeatherGenerator


def build_policy(kind, crop, soil, system, profile, rng, params=None, bus=None):
    if kind == "farmer_practice":
        return FarmerPractice(crop, soil, system, profile, rng)
    if kind == "agronomist":
        return AgronomistProtocol(crop, soil, system, profile, rng)
    if kind == "agripilot":
        return AgriPilotAgent(crop, soil, system, profile, rng, params=params, bus=bus)
    raise ValueError(kind)


def run_season(crop_name: str, soil_name: str, system: str, profile: FarmerProfile,
               policy_kind: str, seed: int, area_ha: float = 1.0,
               params: Optional[AgentParams] = None, monsoon_index: float = 1.0,
               collect_trace: bool = False) -> dict:
    crop, soil = CROPS[crop_name], SOILS[soil_name]
    start_doy = 160 if crop.season == "kharif" else 300

    # identical weather + pest stochastics for every policy on this farm-season
    wx = WeatherGenerator(np.random.default_rng(seed), monsoon_index).season(start_doy, crop.length + 10)
    field_rng = np.random.default_rng(seed + 10_000)
    sensor_rng = np.random.default_rng(seed + 20_000)
    policy_rng = np.random.default_rng(seed + 30_000)
    farmer_rng = np.random.default_rng(seed + 40_000)

    field = Field(crop, soil, system, area_ha, field_rng)
    probe = SoilMoistureProbe(soil, sensor_rng)
    sat = SatelliteNDVI(sensor_rng)
    scout = FarmerReport(sensor_rng, diligence=0.9 if policy_kind == "agripilot" else 0.6)
    est = StateEstimator(soil, soil.taw(crop.root_depth_at(0)))
    est.dr = field.dr * (1 + sensor_rng.normal(0, 0.1))

    bus = ActuatorBus(f"{crop_name}-{soil_name}-{seed}")
    policy = build_policy(policy_kind, crop, soil, system, profile, policy_rng, params, bus)
    farmer = FarmerAgent(profile, farmer_rng)
    fc = ForecastProvider(wx, np.random.default_rng(seed + 50_000))

    trace = []
    deferred_days = 0
    last_exec_irrigation = -99
    last_exec_spray = -99
    etc_window: list[float] = []
    scouting_calls = 0

    for t in range(crop.length):
        day = wx[t]

        # ---- sensing -----------------------------------------------------
        th_s, th_d, quality = probe.read(field, t)
        rain_last3 = sum(w.rain for w in wx[max(0, t - 2):t + 1])
        ndvi_obs = sat.read(field, t, rain_last3)
        scouted = scout.read(field, t) if t > 5 else None
        if policy_kind == "agronomist" and t > 5 and t % 7 == 0:
            # the agronomist scouts properly, but only on visit days
            true_p = field.history[-1].pest_pressure if field.history else 0.0
            scouted = float(max(0.0, true_p * sensor_rng.uniform(0.8, 1.2)))
        if scouted is not None:
            scouting_calls += 1

        if policy_kind == "agripilot" and th_d is not None:
            theta = 0.4 * th_s + 0.6 * th_d
            est.update(theta, field.taw, quality)
        data_quality = 1.0 if quality == "ok" else (0.4 if quality == "suspect" else 0.2)

        expected_ndvi = 0.16 + 0.72 * np.exp(-0.5 * ((t / crop.length - 0.55) / 0.27) ** 2)
        ndvi_anom = (ndvi_obs - expected_ndvi) if ndvi_obs is not None else None

        ctx = {
            "estimator": est,
            "taw": field.taw, "raw": field.raw,
            "true_dr": field.dr,
            "rain_yesterday": wx[t - 1].rain if t > 0 else 0.0,
            "rain_today_obs": day.rain,
            "etc_recent": float(np.mean(etc_window[-7:])) if etc_window else crop.kc_at(t) * day.et0,
            "rain_ens": fc.rain_ensemble(t),
            "et0_fc": fc.et0_forecast(t),
            "tmean": 0.5 * (day.tmin + day.tmax),
            "rh": day.rh,
            "outlook": fc.weather_outlook(t, 5),
            "scouted_pressure": scouted,
            "ndvi_anomaly": ndvi_anom,
            "data_quality": data_quality,
        }

        action = policy.decide(t, ctx)

        # ---- farmer in the loop (agent only; baselines are the farmer) ----
        exec_irr, exec_n, exec_spray = action.irrigation_gross, action.n_kg, action.spray
        if policy_kind == "agripilot":
            for e in action.calls:
                accepted = farmer.consider(e["kind"], e, e["confidence"])
                call = ToolCall(
                    day=t, date_label=f"day {t}",
                    tool={"irrigate": "irrigate", "skip_irrigation": "advisory",
                          "fertilise": "apply_fertiliser", "defer_fertiliser": "advisory",
                          "spray": "spray", "no_spray": "advisory"}[e["kind"]],
                    args=e, confidence=e["confidence"],
                    autonomy="auto" if (e["kind"] in ("irrigate", "skip_irrigation")
                                        and system == "drip") else "confirm",
                    rationale=e["message"],
                    expected_benefit={"kind": e["kind"]},
                    status="executed" if accepted else "rejected")
                bus.emit(call)
                if not accepted:
                    # farmer falls back to habit
                    if e["kind"] == "skip_irrigation":
                        # the farmer falls back to their own irrigation turn
                        if t - last_exec_irrigation >= profile.habit_irrigation_interval:
                            exec_irr = IRRIGATION_SYSTEMS[system]["max_depth"] * 0.7
                    elif e["kind"] == "irrigate":
                        exec_irr = 0.0
                    elif e["kind"] == "fertilise":
                        exec_n = 0.0
                    elif e["kind"] == "defer_fertiliser":
                        exec_n = e.get("dose", 0.0) * 0.8
                    elif e["kind"] == "spray":
                        exec_spray = None
                    elif e["kind"] == "no_spray":
                        # farmer sprays on their own calendar instead
                        if t - last_exec_spray >= profile.habit_spray_interval:
                            exec_spray = "chemical"
                else:
                    if e["kind"] == "defer_fertiliser":
                        deferred_days += 1

        if exec_irr > 0:
            last_exec_irrigation = t
        if exec_spray:
            last_exec_spray = t
        dr_before = field.dr
        res = field.step(day, exec_irr, exec_n, exec_spray)
        etc_window.append(res.etc)

        if policy_kind == "agripilot":
            policy.commit(t, {"irrigation": exec_irr, "n": exec_n, "spray": exec_spray})
            est.predict(etc=crop.kc_at(t) * ctx["et0_fc"][0],
                        ks_hat=float(np.clip((field.taw - est.dr) / max(field.taw - field.raw, 1e-6), 0, 1)),
                        rain=day.rain, irr_net=exec_irr * field.eff,
                        runoff=res.runoff, taw=field.taw)
            est.learn_taw(dr_before, field.dr, exec_irr * field.eff)
            policy.update_beliefs(t, ctx, res.n_uptake, res.deep_perc)
            if t % 7 == 0:
                farmer.observe_outcome(res.ks, visible_stress=res.ks < 0.72,
                                       saved_money=1.0 if exec_irr == 0 else 0.0)

        if collect_trace:
            trace.append({"day": t, "rain": round(day.rain, 1), "et0": round(day.et0, 2),
                          "etc": round(res.etc, 2), "ks": round(res.ks, 3),
                          "dr": round(res.dr, 1), "dr_hat": round(est.dr, 1),
                          "raw": round(field.raw, 1), "taw": round(field.taw, 1),
                          "irrigation": round(exec_irr, 1), "n": round(exec_n, 1),
                          "spray": exec_spray or "", "ndvi": round(res.ndvi, 3),
                          "ndvi_obs": None if ndvi_obs is None else round(ndvi_obs, 3),
                          "pest": round(res.pest_pressure, 2),
                          "damage": round(res.damage, 3), "soil_n": round(res.soil_n, 1)})

    # ---- outcome accounting ------------------------------------------------
    yc = field.yield_components()
    y = yc["yield_t_ha"]
    rules = PEST_RULES[crop_name]
    excess = max(0, field.chem_sprays - rules["max_chem"])
    residue_penalty = min(rules["mrl_penalty"] * (1 if excess else 0)
                          + 0.03 * max(0, excess - 1), rules["mrl_penalty"] * 1.6)
    effective_price = crop.price * (1 - residue_penalty)
    revenue = y * effective_price
    water_mm = field.irrigation_total
    water_m3 = water_mm * 10.0
    cost = (water_mm * ECON["water_cost_per_mm_ha"]
            + field.irrigation_events * ECON["irrigation_labour_by_system"][system]
            + field.n_applied_total * ECON["n_cost_per_kg"]
            + field.fert_events * ECON["fert_application_cost"]
            + field.chem_sprays * ECON["spray_cost_chemical"]
            + field.bio_sprays * ECON["spray_cost_biological"])
    if policy_kind == "agripilot":
        cost += ECON["sensor_amortised_per_season"] + scouting_calls * ECON["scouting_cost"]
    if policy_kind == "agronomist":
        cost += 2_400.0     # extension visit / private agronomist retainer

    pest_load = field.chem_sprays * ENV["pesticide_load_per_spray"] + field.bio_sprays * 0.15
    env_cost = (field.n_leached_total * ENV["n_leach_damage_per_kg"]
                + pest_load * ENV["pesticide_damage_per_load"]
                + field.runoff_total * ENV["runoff_damage_per_mm"])
    biodiversity = float(np.clip(1.0 - ENV["biodiversity_penalty_per_chem_spray"] * field.chem_sprays
                                 + 0.01 * field.bio_sprays, 0.3, 1.0))

    rec = {
        "policy": policy_kind, "crop": crop_name, "soil": soil_name, "system": system,
        "seed": seed, "area_ha": area_ha, "monsoon_index": monsoon_index,
        "yield_t_ha": y, "y_max": crop.y_max,
        "water_factor": yc["water_factor"], "n_factor": yc["n_factor"],
        "pest_factor": yc["pest_factor"],
        "irrigation_mm": water_mm, "irrigation_events": field.irrigation_events,
        "water_m3_per_ha": water_m3,
        "water_productivity_kg_m3": (y * 1000.0 / water_m3) if water_m3 > 0 else float("nan"),
        "n_applied": field.n_applied_total, "n_uptake": field.n_uptake_total,
        "n_leached": field.n_leached_total,
        "n_use_efficiency": field.n_uptake_total / max(field.n_applied_total, 1e-6),
        "chem_sprays": field.chem_sprays, "bio_sprays": field.bio_sprays,
        "pesticide_load": pest_load, "runoff_mm": field.runoff_total,
        "deep_perc_mm": field.deep_perc_total, "stress_days": field.stress_days,
        "residue_penalty": residue_penalty, "effective_price": effective_price,
        "revenue": revenue, "cost": cost, "gross_margin": revenue - cost,
        "env_cost": env_cost, "biodiversity_index": biodiversity,
        "adoption_rate": farmer.adoption_rate if policy_kind == "agripilot" else float("nan"),
        "recommendations": farmer.offered if policy_kind == "agripilot" else 0,
        "final_trust": farmer.trust if policy_kind == "agripilot" else float("nan"),
        "deferred_fertiliser_days": deferred_days,
    }
    if collect_trace:
        rec["trace"] = trace
        rec["audit"] = bus.log
        rec["farmer"] = farmer
    return rec
