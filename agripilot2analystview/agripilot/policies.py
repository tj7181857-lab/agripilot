"""
AgriPilot :: decision policies.

Three policies are evaluated head to head on identical weather, soil and pest
realisations:

  FarmerPractice      calendar irrigation, two heavy urea splits, calendar
                      sprays.  This is the baseline the project must beat.
  AgronomistProtocol  a competent extension agronomist visiting weekly:
                      correct agronomy, but decisions are only as fresh as the
                      last visit and carry no forecast information.
  AgriPilotAgent      the autonomous agent: daily sensor fusion, ensemble
                      forecasts, chance-constrained irrigation, uptake-matched
                      nitrogen, economic-threshold IPM, and a multi-objective
                      score tuned to the individual farmer.

Every policy returns the same Action object, so the simulator is policy-blind.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

import numpy as np

import explain
from config import Crop, Soil, ECON, ENV, IRRIGATION_SYSTEMS, PEST_RULES
from tools import ToolCall, ActuatorBus


@dataclass
class Action:
    irrigation_gross: float = 0.0
    n_kg: float = 0.0
    spray: Optional[str] = None
    calls: list = dc_field(default_factory=list)


AVAILABILITY = 0.30   # matches field_model's uptake constraint


def _sigmoid(x: float) -> float:
    return float(1 / (1 + np.exp(-x)))


class Policy:
    name = "base"

    def __init__(self, crop: Crop, soil: Soil, system: str, profile, rng):
        self.crop, self.soil, self.system, self.profile, self.rng = crop, soil, system, profile, rng
        self.eff = IRRIGATION_SYSTEMS[system]["efficiency"]
        self.min_depth = IRRIGATION_SYSTEMS[system]["min_depth"]
        self.max_depth = IRRIGATION_SYSTEMS[system]["max_depth"]
        self.last_irrigation = -99
        self.last_fert = -99
        self.last_spray = -99
        self.n_applied = 0.0

    def decide(self, t, ctx) -> Action:
        raise NotImplementedError


# ---------------------------------------------------------------------------
class FarmerPractice(Policy):
    name = "farmer_practice"

    def decide(self, t, ctx) -> Action:
        a = Action()
        crop, p = self.crop, self.profile
        # calendar irrigation, skipped only if it visibly rained yesterday
        rained = ctx["rain_yesterday"] > 18
        if t - self.last_irrigation >= p.habit_irrigation_interval and not rained:
            a.irrigation_gross = self.max_depth * (0.9 if self.system == "flood" else 0.8)
            self.last_irrigation = t
        # two heavy splits, 1.4x the crop requirement (typical urea over-use)
        dose = crop.n_requirement * 1.4
        if t == 3:
            a.n_kg = dose * 0.45
        elif t == int(0.33 * crop.length):
            a.n_kg = dose * 0.55
        self.n_applied += a.n_kg
        # calendar spraying from the start of the vegetative phase
        if t >= 18 and t - self.last_spray >= p.habit_spray_interval:
            a.spray = "chemical"
            self.last_spray = t
        return a


# ---------------------------------------------------------------------------
class AgronomistProtocol(Policy):
    name = "agronomist"

    def __init__(self, *args, visit_interval: int = 7, **kw):
        super().__init__(*args, **kw)
        self.visit_interval = visit_interval
        self.scheduled_interval = 6
        self.scheduled_depth = 30.0

    def decide(self, t, ctx) -> Action:
        a = Action()
        crop = self.crop
        visit = (t % self.visit_interval == 0)
        if visit:
            # accurate reading of the true state, plus a week of ET0 history
            dr = ctx["true_dr"] * (1 + self.rng.normal(0, 0.05))
            raw, taw = ctx["raw"], ctx["taw"]
            etc_recent = max(ctx["etc_recent"], 0.5)
            self.scheduled_interval = int(np.clip(raw / etc_recent, 2, 12))
            self.scheduled_depth = float(np.clip(raw / self.eff, self.min_depth, self.max_depth))
            if dr > 0.85 * raw:
                a.irrigation_gross = self.scheduled_depth
                self.last_irrigation = t
            # scouting at the visit, economic threshold on what is seen today
            if ctx["scouted_pressure"] is not None and ctx["scouted_pressure"] > 0.55 \
                    and t - self.last_spray >= 8:
                a.spray = "chemical"
                self.last_spray = t
        else:
            if t - self.last_irrigation >= self.scheduled_interval and ctx["rain_today_obs"] < 15:
                a.irrigation_gross = self.scheduled_depth
                self.last_irrigation = t
        # three splits at the recommended dose
        dose = crop.n_requirement * 1.05
        for frac, share in ((0.05, 0.35), (0.33, 0.40), (0.58, 0.25)):
            if t == int(frac * crop.length):
                a.n_kg = dose * share
        self.n_applied += a.n_kg
        return a


# ---------------------------------------------------------------------------
@dataclass
class AgentParams:
    """Policy parameters exposed to the multi-objective optimiser."""
    risk_budget: float = 0.15        # tolerated P(water stress) before next slot
    deficit_factor: float = 0.05     # planned under-refill (regulated deficit irrigation)
    spray_threshold: float = 1.0     # benefit/cost ratio required to spray
    n_safety: float = 1.10           # nitrogen buffer over forecast uptake
    bio_preference: float = 0.35     # reserved: bias towards biological control


class AgriPilotAgent(Policy):
    name = "agripilot"

    def __init__(self, crop, soil, system, profile, rng, params: AgentParams = None,
                 bus: ActuatorBus = None, horizon: int = 4):
        super().__init__(crop, soil, system, profile, rng)
        self.par = params or AgentParams()
        self.bus = bus
        self.horizon = horizon
        self.n_hat = 26.0                  # belief about the mineral-N pool
        self.pest_belief = 0.0
        self.pest_dd = 0.0
        self.trust = profile.tech_trust
        self.explanations: list[dict] = []
        self.deferred_n = 0.0
        self.chem_used = 0
        self.damage_hat = 0.0
        self.last_spray_kind = None

    # -- irrigation ------------------------------------------------------
    def _min_interval(self) -> int:
        return {"drip": 1, "sprinkler": 2, "flood": 5}[self.system]

    def _stress_risk(self, dr0: np.ndarray, rain_ens: np.ndarray, et0_fc: np.ndarray,
                     depth_gross: float, taw: float, raw: float, kc: float,
                     horizon: int) -> tuple[float, float]:
        """
        Monte-Carlo over (state uncertainty x forecast ensemble).
        Returns P(Ks < 0.9 on any day before the next irrigation slot) and the
        expected deep percolation caused by this action.
        """
        members = rain_ens.shape[0]
        dr = np.repeat(dr0[:, None], members, axis=1).astype(float)   # [S, M]
        dr -= depth_gross * self.eff
        np.clip(dr, 0, taw, out=dr)
        stressed = np.zeros_like(dr, dtype=bool)
        perc = np.zeros_like(dr)
        for lead in range(horizon):
            rain = rain_ens[:, lead][None, :] * 0.85          # effective rainfall
            etc = kc * et0_fc[lead]
            ks = np.clip((taw - dr) / max(taw - raw, 1e-6), 0, 1)
            ks = np.where(dr <= raw, 1.0, ks)
            eta = ks * etc
            dp = np.maximum(0.0, rain - eta - dr)
            perc += dp
            dr = np.clip(dr - rain + eta + dp, 0, taw)
            stressed |= (ks < 0.90)
        return float(stressed.mean()), float(perc.mean())

    def _irrigation_decision(self, t, ctx):
        crop = self.crop
        est = ctx["estimator"]
        taw, raw = ctx["taw"], ctx["raw"]
        kc = crop.kc_at(t)
        rain_ens = ctx["rain_ens"]
        et0_fc = ctx["et0_fc"]
        horizon = max(2, min(self._min_interval() + 1, self.horizon))

        if t - self.last_irrigation < self._min_interval():
            return 0.0, None

        # state uncertainty -> sample the depletion belief
        dr_samples = np.clip(self.rng.normal(est.dr, max(est.sigma, 2.0), 40), 0, taw)

        stage = crop.stage_of(t)
        ky = crop.ky_stage[stage]
        budget = self.par.risk_budget * (1.0 - 0.45 * self.profile.risk_aversion)
        budget *= float(np.clip(1.25 - 0.55 * ky, 0.35, 1.3))     # tighter when Ky is high

        full_depth = float(np.clip((est.dr * (1 - self.par.deficit_factor)) / self.eff,
                                   0, self.max_depth))
        candidates = [0.0]
        if full_depth >= self.min_depth:
            candidates += list(np.linspace(self.min_depth, full_depth, 4))
        best = None
        for depth in candidates:
            risk, perc = self._stress_risk(dr_samples, rain_ens, et0_fc, depth,
                                           taw, raw, kc, horizon)
            if risk <= budget:
                best = (depth, risk, perc)
                break
        if best is None:
            depth = candidates[-1]
            risk, perc = self._stress_risk(dr_samples, rain_ens, et0_fc, depth,
                                           taw, raw, kc, horizon)
            best = (depth, risk, perc)
        depth, risk, perc = best

        p_rain = float((rain_ens[:, :2].sum(axis=1) >= 10).mean())
        moisture_pct = int(100 * np.clip(1 - est.dr / max(raw, 1e-6), 0, 1))
        conf = float(np.clip(0.9 - 0.5 * (est.sigma / max(raw, 1)) - 0.25 * (1 - ctx["data_quality"]), 0.25, 0.97))

        lang = self.profile.language
        if depth <= 0.01:
            if est.dr < 0.35 * raw and t - self.last_irrigation < 3:
                return 0.0, None          # nothing worth notifying the farmer about
            days_left = max(1, int((raw - est.dr) / max(kc * et0_fc[0], 0.5)))
            saved = max(self.min_depth, est.dr / self.eff)
            msg = explain.render("skip_irrigation", lang,
                                 rain_txt=(f"{int(p_rain*100)}% chance of 10 mm+ rain in 48 h"
                                           if lang == "en" else
                                           f"४८ तासांत १० मिमी पावसाची {int(p_rain*100)}% शक्यता"),
                                 days=days_left, saved=int(saved),
                                 rupees=int(saved * ECON["water_cost_per_mm_ha"]))
            kind = "skip_irrigation"
        else:
            loss = int(100 * min(0.35, ky * risk * 1.6 + 0.02))
            msg = explain.render("irrigate", lang, depth=int(depth),
                                 hours=("early morning" if lang == "en" else "पहाटे"),
                                 pct=moisture_pct,
                                 rain_txt=(f"only a {int(p_rain*100)}% chance of useful rain"
                                           if lang == "en" else
                                           f"पावसाची शक्यता फक्त {int(p_rain*100)}%"),
                                 loss=loss)
            kind = "irrigate"
        return depth, {"kind": kind, "message": msg, "confidence": conf,
                       "risk": risk, "perc": perc, "depth": depth}

    # -- nitrogen --------------------------------------------------------
    def _nitrogen_decision(self, t, ctx):
        crop = self.crop
        window = 12
        demand = crop.n_requirement * (
            crop.n_uptake_fraction(min(t + window, crop.length)) - crop.n_uptake_fraction(t))
        # roots can only take up a fraction of the mineral-N pool per day, so the
        # pool has to stand well above the daily requirement for uptake not to be
        # supply-limited.  AVAILABILITY is that fraction in the soil model.
        peak_daily = max(
            crop.n_requirement * (crop.n_uptake_fraction(min(t + d + 1, crop.length))
                                  - crop.n_uptake_fraction(min(t + d, crop.length)))
            for d in range(window))
        target_pool = (peak_daily / AVAILABILITY) * self.par.n_safety
        mineralised = self.soil.n_mineralisation * window * 0.5
        gap = max(target_pool - self.n_hat, demand * self.par.n_safety - self.n_hat - mineralised)
        cap = crop.n_requirement * 1.35 - crop.n_credit
        if gap <= 4 or t - self.last_fert < 9 or self.n_applied >= cap or t > 0.8 * crop.length:
            return 0.0, None

        dose = float(np.clip(gap / 0.85, 8, 55))
        dose = min(dose, cap - self.n_applied)
        p_heavy = float((ctx["rain_ens"][:, :2].sum(axis=1) >= 25).mean())
        lang = self.profile.language
        if p_heavy > 0.35 and gap < demand * 0.9:
            msg = explain.render("defer_fertiliser", lang, rain_p=int(p_heavy * 100),
                                 loss=int(dose * 0.3))
            return 0.0, {"kind": "defer_fertiliser", "message": msg,
                         "confidence": 0.7, "dose": dose}
        product = "urea"
        msg = explain.render("fertilise", lang, n=int(dose),
                             product_kg=int(dose / 0.46), product=("urea" if lang == "en" else "युरिया"),
                             window=window, gap=int(max(gap, 0)))
        return dose, {"kind": "fertilise", "message": msg, "confidence": 0.8,
                      "dose": dose, "product": product}

    # -- pest ------------------------------------------------------------
    def _pest_decision(self, t, ctx):
        crop = self.crop
        tmean = ctx["tmean"]
        self.pest_dd += max(0.0, tmean - crop.pest_base_temp)
        if self.pest_dd < crop.pest_dd_threshold:
            return None, None
        suit = float(np.exp(-0.5 * ((tmean - 26.0) / 6.5) ** 2))
        if crop.pest_humidity_driven:
            wet = np.clip((ctx["rh"] - 60.0) / 30.0, 0, 1)
            suit *= float(np.clip(0.25 + 0.95 * wet, 0, 1.35))
        # forward-looking: pest management is preventive, so the agent also scores
        # the 5-day weather outlook rather than only today's conditions
        t_out, rh_out = ctx["outlook"]
        fwd = float(np.exp(-0.5 * ((t_out - 26.0) / 6.5) ** 2))
        if crop.pest_humidity_driven:
            fwd *= float(np.clip(0.25 + 0.95 * np.clip((rh_out - 60.0) / 30.0, 0, 1), 0, 1.35))
        model_p = max(suit, 0.85 * fwd)
        if ctx["scouted_pressure"] is not None:
            self.pest_belief = 0.45 * model_p + 0.55 * ctx["scouted_pressure"]
        else:
            self.pest_belief = 0.75 * self.pest_belief + 0.25 * model_p
        # canopy stress signal from satellite corroborates an infestation
        if ctx["ndvi_anomaly"] is not None and ctx["ndvi_anomaly"] < -0.06:
            self.pest_belief *= 1.25

        rules = PEST_RULES[crop.name]
        chem_left = rules["max_chem"] - self.chem_used
        # where there is no residue penalty the label limit is not a hard wall, but
        # extra sprays carry a resistance-management and ecological surcharge
        over_budget = chem_left <= 0 and rules["mrl_penalty"] == 0.0
        if over_budget:
            chem_left = 99
        in_phi = t > crop.length - rules["phi_days"]
        residual = 12
        value_per_ha = crop.y_max * crop.price
        remaining = max(crop.max_damage - self.damage_hat, 0.0)
        expected_loss = min(self.pest_belief * 0.010 * crop.max_damage * residual,
                            remaining) * value_per_ha
        w_env = self.profile.objective_weights()["environment"]

        # decision-theoretic choice between doing nothing, a biological release
        # and a chemical spray, net of the environmental shadow price
        options = {"none": 0.0}
        chem_eff = 0.85 * (0.955 ** max(0, self.chem_used - 5))
        options["biological"] = (0.60 * expected_loss
                                 - ECON["spray_cost_biological"]
                                 - w_env * ENV["pesticide_damage_per_load"] * 0.15)
        # ration the label-limited chemical budget towards the highest-pressure
        # windows instead of spending it on the first trigger of the season
        windows_left = max(1.0, (crop.length - rules["phi_days"] - t) / residual)
        chem_gate = (chem_left >= windows_left) or (self.pest_belief >= 0.75)
        if chem_left > 0 and not in_phi and chem_gate:
            options["chemical"] = (chem_eff * expected_loss
                                   - ECON["spray_cost_chemical"]
                                   - w_env * ENV["pesticide_damage_per_load"]
                                   * (1.8 if over_budget else 1.0))
        choice = max(options, key=options.get)
        cost = ECON["spray_cost_chemical"] if choice == "chemical" else ECON["spray_cost_biological"]
        avoided = (chem_eff if choice == "chemical" else 0.60) * expected_loss
        hurdle = cost * self.par.spray_threshold

        lang = self.profile.language
        if choice != "none" and t - self.last_spray >= 7 and options[choice] > 0 and avoided > hurdle:
            kind = choice
            if kind == "chemical":
                self.chem_used += 1
            self.last_spray_kind = kind
            self.damage_hat += 0.010 * crop.max_damage * self.pest_belief * (
                1 - (chem_eff if kind == "chemical" else 0.60))
            msg = explain.render("spray", lang,
                                 method=("bio-control" if kind == "biological" else "chemical")
                                 if lang == "en" else ("जैविक" if kind == "biological" else "रासायनिक"),
                                 pest=crop.key_pest, window=48,
                                 level=("high" if self.pest_belief > 1.0 else "moderate")
                                 if lang == "en" else ("जास्त" if self.pest_belief > 1.0 else "मध्यम"),
                                 rupees=int(avoided), cost=int(cost))
            return kind, {"kind": "spray", "message": msg,
                          "confidence": float(np.clip(0.5 + 0.35 * (avoided / max(cost, 1) - 1), 0.3, 0.95)),
                          "pressure": self.pest_belief}
        # accrue the agent's belief about standing damage, net of residual cover
        gap = t - self.last_spray
        cover = 0.0
        if gap < 12:
            cover = chem_eff if self.last_spray_kind == "chemical" else 0.60
            if gap > 7:
                cover *= (12 - gap) / 5.0
        self.damage_hat += 0.010 * crop.max_damage * self.pest_belief * (1 - cover)
        if t % 6 == 0:
            msg = explain.render("no_spray", lang, pest=crop.key_pest,
                                 cost=int(ECON["spray_cost_chemical"]))
            return None, {"kind": "no_spray", "message": msg, "confidence": 0.75,
                          "pressure": self.pest_belief}
        return None, None

    # -- main ------------------------------------------------------------
    def decide(self, t, ctx) -> Action:
        a = Action()
        depth, irr_expl = self._irrigation_decision(t, ctx)
        dose, n_expl = self._nitrogen_decision(t, ctx)
        spray, pest_expl = self._pest_decision(t, ctx)

        a.irrigation_gross = depth
        a.n_kg = dose
        a.spray = spray
        for e in (irr_expl, n_expl, pest_expl):
            if e:
                a.calls.append(e)
        return a

    def commit(self, t, executed: dict):
        if executed.get("irrigation", 0) > 0:
            self.last_irrigation = t
        if executed.get("n", 0) > 0:
            self.last_fert = t
            self.n_applied += executed["n"]
            self.n_hat += executed["n"] * 0.85
        if executed.get("spray"):
            self.last_spray = t

    def update_beliefs(self, t, ctx, uptake_est: float, drainage: float):
        """Advance the nitrogen belief with mineralisation, uptake and leaching."""
        self.n_hat += self.soil.n_mineralisation
        self.n_hat = max(self.n_hat - uptake_est, 0.0)
        self.n_hat = max(self.n_hat * (1 - self.soil.leach_fraction * drainage), 0.0)
