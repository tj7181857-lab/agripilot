"""
AgriPilot :: biophysical field model (the "digital twin" the agent acts on).

Implements, at daily time step:
  * FAO-56 root-zone water balance with runoff, deep percolation and a
    water-stress coefficient Ks;
  * a mineral-N balance with mineralisation, crop uptake, leaching and
    application losses;
  * a degree-day + weather driven pest pressure and damage model;
  * FAO-33 multiplicative stage-wise yield formation.

The same class is used twice: as the *environment* the simulator advances, and
(with sensor-derived estimates instead of true state) as the *forward model*
the agent uses inside its Monte-Carlo look-ahead.  Keeping one implementation
avoids the classic "planner disagrees with reality" bug.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

import numpy as np

from config import Crop, Soil, IRRIGATION_SYSTEMS


@dataclass
class DayResult:
    dap: int
    et0: float
    etc: float
    eta: float
    ks: float
    dr: float
    taw: float
    raw: float
    rain: float
    runoff: float
    irrigation_gross: float
    irrigation_net: float
    deep_perc: float
    soil_n: float
    n_uptake: float
    n_leached: float
    pest_pressure: float
    damage: float
    ndvi: float


class Field:
    def __init__(self, crop: Crop, soil: Soil, system: str, area_ha: float,
                 rng: np.random.Generator, initial_depletion_frac: float = 0.3,
                 initial_soil_n: float = 26.0):
        self.crop, self.soil, self.system = crop, soil, system
        self.area_ha = area_ha
        self.rng = rng
        self.eff = IRRIGATION_SYSTEMS[system]["efficiency"]

        z0 = crop.root_depth_at(0)
        self.dr = initial_depletion_frac * soil.taw(z0)
        self.soil_n = initial_soil_n
        self.dap = 0

        # accumulators
        self.stage_etc = np.zeros(4)
        self.stage_eta = np.zeros(4)
        self.n_uptake_total = 0.0
        self.n_leached_total = 0.0
        self.runoff_total = 0.0
        self.deep_perc_total = 0.0
        self.irrigation_total = 0.0
        self.irrigation_events = 0
        self.n_applied_total = 0.0
        self.fert_events = 0
        self.chem_sprays = 0
        self.bio_sprays = 0
        self.days_since_spray = 999
        self.spray_efficacy = 0.0
        self.pest_dd = 0.0
        self.damage = 0.0
        self.stress_days = 0
        self.history: list[DayResult] = []
        self._pending_n: list[tuple[int, float]] = []   # (day_applied, kg) for loss accounting
        self._outbreak = 0.0

    # ---------------------------------------------------------------- water
    @property
    def taw(self) -> float:
        return self.soil.taw(self.crop.root_depth_at(self.dap))

    @property
    def raw(self) -> float:
        return self.crop.p_depletion * self.taw

    @property
    def ks(self) -> float:
        taw, raw = self.taw, self.raw
        if self.dr <= raw:
            return 1.0
        return float(np.clip((taw - self.dr) / max(taw - raw, 1e-6), 0.0, 1.0))

    def _runoff(self, rain: float) -> float:
        """Curve-number style: wetter soil and lower infiltration -> more runoff."""
        if rain <= 2.0:
            return 0.0
        wetness = 1.0 - np.clip(self.dr / max(self.taw, 1e-6), 0, 1)
        s = self.soil.infiltration * 3.2 * (1.0 - 0.65 * wetness)
        ia = 0.2 * s
        if rain <= ia:
            return 0.0
        return float((rain - ia) ** 2 / (rain + 0.8 * s))

    # ----------------------------------------------------------------- pest
    def _pest_pressure(self, tmin: float, tmax: float, rh: float, rain: float) -> float:
        tmean = 0.5 * (tmin + tmax)
        self.pest_dd += max(0.0, tmean - self.crop.pest_base_temp)
        if self.pest_dd < self.crop.pest_dd_threshold:
            return 0.0
        # temperature suitability, peaked
        suit = float(np.exp(-0.5 * ((tmean - 26.0) / 6.5) ** 2))
        if self.crop.pest_humidity_driven:
            wet = np.clip((rh - 60.0) / 30.0, 0, 1) * (1.0 + 0.5 * (rain > 4))
            suit *= float(np.clip(0.25 + 0.95 * wet, 0, 1.35))
        else:
            suit *= float(np.clip(1.25 - 0.55 * (rain > 18), 0.3, 1.25))
        # stochastic outbreaks persist a few days
        if self.rng.random() < 0.028:
            self._outbreak = 1.0
        self._outbreak *= 0.82
        return float(np.clip(suit * (1.0 + 1.3 * self._outbreak), 0, 2.2))

    # ----------------------------------------------------------------- step
    def step(self, wx, irrigation_gross: float = 0.0, n_applied: float = 0.0,
             spray: Optional[str] = None) -> DayResult:
        crop, soil = self.crop, self.soil
        dap = self.dap

        # --- pest control actions
        if spray == "chemical":
            self.chem_sprays += 1
            self.days_since_spray = 0
            # resistance build-up: repeated use of the same chemistry loses bite
            self.spray_efficacy = 0.85 * (0.955 ** max(0, self.chem_sprays - 6))
        elif spray == "biological":
            self.bio_sprays += 1
            self.days_since_spray = 0
            self.spray_efficacy = 0.60
        else:
            self.days_since_spray += 1

        residual = 12 if self.spray_efficacy > 0.7 else 8
        # full efficacy over the first 60% of the residual period, then a taper
        d = self.days_since_spray
        if d >= residual:
            protection = 0.0
        elif d <= 0.6 * residual:
            protection = self.spray_efficacy
        else:
            protection = self.spray_efficacy * (residual - d) / (0.4 * residual)

        # --- water balance
        i_net = irrigation_gross * self.eff
        if irrigation_gross > 0:
            self.irrigation_total += irrigation_gross
            self.irrigation_events += 1
        runoff = self._runoff(wx.rain)
        infil = wx.rain - runoff + i_net

        kc = crop.kc_at(dap)
        etc = kc * wx.et0
        ks = self.ks
        eta = ks * etc
        if ks < 0.75:
            self.stress_days += 1

        dr_prev = self.dr
        dp = max(0.0, infil - eta - dr_prev)
        self.dr = float(np.clip(dr_prev - infil + eta + dp, 0.0, self.taw))

        self.runoff_total += runoff
        self.deep_perc_total += dp

        # --- nitrogen balance
        if n_applied > 0:
            # loss at application: volatilisation if dry & hot, wash-off if heavy rain
            loss = 0.10
            if wx.rain > 25:
                loss += 0.22
            if irrigation_gross == 0 and wx.rain < 3:
                loss += 0.12
            if wx.tmax > 36:
                loss += 0.05
            self.soil_n += n_applied * (1 - min(loss, 0.45))
            self.n_applied_total += n_applied
            self.fert_events += 1
        self.soil_n += soil.n_mineralisation

        demand = crop.n_requirement * (
            crop.n_uptake_fraction(dap) - crop.n_uptake_fraction(dap - 1))
        demand = max(demand, 0.0) * (0.35 + 0.65 * ks)
        if crop.n_credit > 0:   # biological fixation supplies part of demand
            fixed = min(demand * 0.55, crop.n_credit * (1 / max(crop.length, 1)) * 2.2)
        else:
            fixed = 0.0
        uptake = min(demand - fixed, max(self.soil_n, 0.0) * 0.30) + fixed
        uptake = max(uptake, 0.0)
        self.soil_n = max(self.soil_n - (uptake - fixed), 0.0)
        self.n_uptake_total += uptake

        leached = min(self.soil_n, self.soil_n * soil.leach_fraction * dp)
        self.soil_n -= leached
        self.n_leached_total += leached

        # --- pest damage
        pressure = self._pest_pressure(wx.tmin, wx.tmax, wx.rh, wx.rain)
        daily_damage = pressure * 0.010 * self.crop.max_damage * (1 - protection)
        self.damage = float(min(self.damage + daily_damage, crop.max_damage))

        # --- stage accounting for the yield function
        st = crop.stage_of(dap)
        self.stage_etc[st] += etc
        self.stage_eta[st] += eta

        ndvi = self._ndvi(dap, ks)
        res = DayResult(dap, wx.et0, etc, eta, ks, self.dr, self.taw, self.raw,
                        wx.rain, runoff, irrigation_gross, i_net, dp, self.soil_n,
                        uptake, leached, pressure, self.damage, ndvi)
        self.history.append(res)
        self.dap += 1
        return res

    # ----------------------------------------------------------------- NDVI
    def _ndvi(self, dap: int, ks: float) -> float:
        """Canopy greenness proxy the satellite layer observes."""
        x = dap / max(self.crop.length, 1)
        base = 0.16 + 0.72 * np.exp(-0.5 * ((x - 0.55) / 0.27) ** 2)
        n_ratio = np.clip(self.n_uptake_total /
                          max(self.crop.n_requirement * self.crop.n_uptake_fraction(dap), 1e-6), 0, 1)
        return float(np.clip(base * (0.55 + 0.45 * ks) * (0.7 + 0.3 * n_ratio)
                             * (1 - 0.5 * self.damage), 0.05, 0.95))

    # --------------------------------------------------------------- yield
    def yield_components(self) -> dict:
        crop = self.crop
        wf = 1.0
        for s in range(4):
            if self.stage_etc[s] <= 0:
                continue
            ratio = self.stage_eta[s] / self.stage_etc[s]
            wf *= max(0.0, 1 - crop.ky_stage[s] * (1 - ratio))
        n_ratio = self.n_uptake_total / max(crop.n_requirement, 1e-6)
        nf = float(np.clip(0.42 + 0.58 * n_ratio, 0.0, 1.0))
        pf = 1 - self.damage
        y = crop.y_max * wf * nf * pf
        return {"yield_t_ha": float(max(y, 0.0)), "water_factor": float(wf),
                "n_factor": nf, "pest_factor": float(pf)}
