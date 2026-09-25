"""
AgriPilot :: weather layer.

Two responsibilities:
  1. WeatherGenerator - a stochastic weather model that produces the *true*
     daily weather of a season (the ground truth the simulator advances on).
     Rain occurrence is a two-state Markov chain, rain amount a gamma variate,
     temperature a seasonal sinusoid with AR(1) anomalies.  ET0 is computed
     with the Hargreaves-Samani equation, which needs only Tmin/Tmax/Ra and is
     therefore the right choice for smallholder sites without full weather
     stations.
  2. ForecastProvider - what the agent actually sees: a 7-day *ensemble*
     forecast whose skill decays with lead time.  This is the object the
     decision engine must reason over probabilistically.

In deployment, ForecastProvider is swapped for the IMD / Open-Meteo adapter in
`connectors.py`; the interface (ensemble array of shape [members, horizon]) is
identical, so nothing downstream changes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Latitude of the pilot region (Nashik ~20 deg N)
LATITUDE_DEG = 20.0


def extraterrestrial_radiation(doy: int, lat_deg: float = LATITUDE_DEG) -> float:
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )


def hargreaves_et0(tmin: float, tmax: float, doy: int, lat_deg: float = LATITUDE_DEG) -> float:
    """Reference evapotranspiration, mm/day (Hargreaves-Samani)."""
    tmean = 0.5 * (tmin + tmax)
    ra = extraterrestrial_radiation(doy, lat_deg)
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.5)) * ra * 0.408
    return float(max(et0, 0.3))


@dataclass
class DayWeather:
    doy: int
    rain: float        # mm
    tmin: float
    tmax: float
    rh: float          # mean relative humidity, %
    et0: float
    wind: float


class WeatherGenerator:
    """Stochastic daily weather for one site."""

    def __init__(self, rng: np.random.Generator, monsoon_index: float = 1.0,
                 warming: float = 0.0):
        self.rng = rng
        self.monsoon_index = monsoon_index   # 0.7 = drought year, 1.3 = wet year
        self.warming = warming
        self._t_anom = 0.0
        self._wet_yesterday = False

    # --- occurrence / amount parameters vary through the year ---------------
    def _p_wet(self, doy: int) -> float:
        # monsoon June(152)-Sept(273); sharp seasonality typical of the Deccan
        season = math.exp(-0.5 * ((doy - 210) / 42.0) ** 2)
        post = math.exp(-0.5 * ((doy - 288) / 26.0) ** 2)   # post-monsoon showers
        base = 0.035 + 0.48 * season * self.monsoon_index + 0.16 * post
        return min(base, 0.85)

    def _mean_rain(self, doy: int) -> float:
        season = math.exp(-0.5 * ((doy - 210) / 48.0) ** 2)
        post = math.exp(-0.5 * ((doy - 288) / 26.0) ** 2)
        return 3.2 + 10.5 * season * self.monsoon_index + 5.0 * post

    def day(self, doy: int) -> DayWeather:
        p_w = self._p_wet(doy)
        # Markov persistence: wet days cluster
        p = 0.35 + 0.55 * p_w if self._wet_yesterday else 0.75 * p_w
        wet = self.rng.random() < min(p, 0.92)
        if wet:
            shape = 0.85
            scale = self._mean_rain(doy) / shape
            rain = float(self.rng.gamma(shape, scale))
            rain = min(rain, 140.0)
        else:
            rain = 0.0
        self._wet_yesterday = wet

        # temperature: seasonal mean + AR(1) anomaly, cooled on wet days
        t_season = 31.0 + 5.0 * math.sin(2 * math.pi * (doy - 100) / 365.0)
        self._t_anom = 0.72 * self._t_anom + self.rng.normal(0, 1.7)
        tmax = t_season + self._t_anom + self.warming - (3.6 if wet else 0.0)
        drange = (6.5 if wet else 13.5) + self.rng.normal(0, 1.2)
        tmin = tmax - max(drange, 4.0)

        rh = 42 + 40 * (1 if wet else 0) * 0.9 + 14 * self._p_wet(doy) + self.rng.normal(0, 5)
        rh = float(min(max(rh, 18), 98))
        wind = float(max(0.4, self.rng.gamma(2.0, 1.0)))
        return DayWeather(doy, rain, tmin, tmax, rh,
                          hargreaves_et0(tmin, tmax, doy), wind)

    def season(self, start_doy: int, length: int) -> list[DayWeather]:
        return [self.day(((start_doy + i - 1) % 365) + 1) for i in range(length)]


class ForecastProvider:
    """
    Ensemble forecast seen by the agent.

    skill(lead) decays geometrically; members are perturbations of truth plus a
    shared bias term, so members are correlated - exactly the structure that
    makes naive "average the ensemble" decisions fail on convective rainfall.
    """

    def __init__(self, truth: list[DayWeather], rng: np.random.Generator,
                 members: int = 24, horizon: int = 7):
        self.truth = truth
        self.rng = rng
        self.members = members
        self.horizon = horizon

    def _skill(self, lead: int) -> float:
        return float(np.clip(0.93 * (0.79 ** lead), 0.02, 0.95))

    def rain_ensemble(self, t: int) -> np.ndarray:
        """Shape [members, horizon] of forecast rainfall (mm); lead 0 = today."""
        out = np.zeros((self.members, self.horizon))
        shared = self.rng.normal(0, 1, self.horizon)      # correlated bias
        for lead in range(self.horizon):
            idx = t + lead
            true_rain = self.truth[idx].rain if idx < len(self.truth) else 0.0
            s = self._skill(lead)
            climatology = 3.0
            for m in range(self.members):
                noise = self.rng.normal(0, 1)
                signal = s * true_rain + (1 - s) * climatology
                spread = (1 - s) * (8.0 + 0.9 * true_rain)
                val = signal + spread * (0.6 * shared[lead] + 0.8 * noise)
                # rainfall is non-negative and intermittent
                if val < 1.2:
                    val = 0.0
                out[m, lead] = max(val, 0.0)
        return out

    def et0_forecast(self, t: int) -> np.ndarray:
        """Deterministic-ish ET0 outlook (ET0 is far more predictable than rain)."""
        vals = []
        for lead in range(self.horizon):
            idx = t + lead
            base = self.truth[idx].et0 if idx < len(self.truth) else 5.0
            vals.append(max(0.4, base + self.rng.normal(0, 0.35 + 0.12 * lead)))
        return np.array(vals)

    def weather_outlook(self, t: int, days: int = 5) -> tuple[float, float]:
        """Mean temperature and humidity outlook - the drivers of pest pressure."""
        tm, rh = [], []
        for lead in range(min(days, self.horizon)):
            idx = t + lead
            if idx >= len(self.truth):
                break
            d = self.truth[idx]
            s = self._skill(lead)
            tm.append(0.5 * (d.tmin + d.tmax) + (1 - s) * self.rng.normal(0, 2.0))
            rh.append(float(np.clip(d.rh + (1 - s) * self.rng.normal(0, 9.0), 10, 100)))
        return float(np.mean(tm)), float(np.mean(rh))

    def prob_rain_above(self, t: int, mm: float, days: int) -> float:
        ens = self.rain_ensemble(t)[:, :days].sum(axis=1)
        return float((ens >= mm).mean())
