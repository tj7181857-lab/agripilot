"""
AgriPilot :: multimodal sensing layer.

Three modalities, each with the failure modes that actually occur in the field:

  SoilMoistureProbe  capacitance probe at 2 depths - white noise, slow
                     calibration drift, 7% packet loss on the LoRa uplink,
                     and a "stuck value" fault that must be detected.
  SatelliteNDVI      5-day revisit, scenes dropped when cloud cover is high
                     (so NDVI is systematically missing during the monsoon,
                     exactly when the crop is most dynamic).
  FarmerReport       scouting observations entered in the app - sparse,
                     categorical, and the only direct evidence of pest state.

`StateEstimator` fuses them with the water-balance forward model through a
scalar Kalman filter on root-zone depletion.  This is what lets the agent act
when data are missing: the model propagates, the sensors correct.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class SensorReading:
    dap: int
    theta_shallow: Optional[float]
    theta_deep: Optional[float]
    ndvi: Optional[float]
    quality: str            # "ok" | "missing" | "suspect"


class SoilMoistureProbe:
    def __init__(self, soil, rng: np.random.Generator, dropout: float = 0.07):
        self.soil, self.rng, self.dropout = soil, rng, dropout
        self.bias = rng.normal(0, 0.012)          # calibration offset
        self.drift_rate = rng.normal(0, 0.00012)  # per-day drift
        self.stuck_until = -1
        self.last_value = None

    def read(self, field, dap: int) -> tuple[Optional[float], Optional[float], str]:
        # occasional stuck-sensor fault lasting 3-9 days
        if dap > self.stuck_until and self.rng.random() < 0.008:
            self.stuck_until = dap + int(self.rng.integers(3, 10))
        if dap <= self.stuck_until and self.last_value is not None:
            return self.last_value[0], self.last_value[1], "suspect"
        if self.rng.random() < self.dropout:
            return None, None, "missing"

        taw = field.taw
        theta_mean = self.soil.field_capacity - (field.dr / max(taw, 1e-6)) * (
            self.soil.field_capacity - self.soil.wilting_point)
        drift = self.bias + self.drift_rate * dap
        shallow = theta_mean - 0.018 + drift + self.rng.normal(0, 0.011)
        deep = theta_mean + 0.012 + drift + self.rng.normal(0, 0.008)
        self.last_value = (float(shallow), float(deep))
        return float(shallow), float(deep), "ok"


class SatelliteNDVI:
    def __init__(self, rng: np.random.Generator, revisit: int = 5):
        self.rng, self.revisit = rng, revisit

    def read(self, field, dap: int, rain_last3: float) -> Optional[float]:
        if dap % self.revisit != 0:
            return None
        cloud_p = np.clip(0.18 + 0.055 * rain_last3, 0, 0.95)
        if self.rng.random() < cloud_p:
            return None            # scene discarded by the cloud mask
        true_ndvi = field.history[-1].ndvi if field.history else 0.2
        return float(np.clip(true_ndvi + self.rng.normal(0, 0.035), 0.02, 0.98))


class FarmerReport:
    """Scouting input from the mobile app: 'how many insects on 10 leaves?'"""

    def __init__(self, rng: np.random.Generator, diligence: float = 0.5):
        self.rng, self.diligence = rng, diligence

    def read(self, field, dap: int) -> Optional[float]:
        if self.rng.random() > self.diligence / 7.0:      # ~diligence reports per week
            return None
        true_pressure = field.history[-1].pest_pressure if field.history else 0.0
        observed = true_pressure * self.rng.uniform(0.55, 1.45)
        return float(max(observed, 0.0))


class StateEstimator:
    """
    Scalar Kalman filter on root-zone depletion Dr (mm).

    predict(): advance with the water-balance model using forecast/observed
               weather and the actions actually executed.
    update():  correct with soil-moisture-derived Dr when a trustworthy
               reading arrives; inflate R for "suspect" readings instead of
               discarding them outright.
    Also maintains a recursive least-squares estimate of TAW: irrigation
    events are natural experiments that reveal the true water-holding
    capacity of *this* field, which is the core of local adaptation.
    """

    def __init__(self, soil, taw_prior: float, sigma0: float = 12.0):
        self.dr = 0.30 * taw_prior
        self.var = sigma0 ** 2
        self.q = 3.2 ** 2            # process noise (model error), mm^2
        self.r_ok = 6.0 ** 2         # observation noise, mm^2
        self.r_suspect = 26.0 ** 2
        self.soil = soil
        self.taw_hat = taw_prior
        self.taw_var = (0.25 * taw_prior) ** 2
        self.n_updates = 0

    def predict(self, etc: float, ks_hat: float, rain: float, irr_net: float,
                runoff: float, taw: float):
        eta = ks_hat * etc
        infil = max(rain - runoff, 0.0) + irr_net
        dp = max(0.0, infil - eta - self.dr)
        self.dr = float(np.clip(self.dr - infil + eta + dp, 0.0, taw))
        self.var += self.q

    def update(self, theta_obs: float, taw: float, quality: str):
        if theta_obs is None:
            return
        fc, wp = self.soil.field_capacity, self.soil.wilting_point
        dr_obs = float(np.clip((fc - theta_obs) / max(fc - wp, 1e-6), 0, 1.3) * taw)
        r = self.r_ok if quality == "ok" else self.r_suspect
        k = self.var / (self.var + r)
        innovation = dr_obs - self.dr
        self.dr = float(np.clip(self.dr + k * innovation, 0.0, taw))
        self.var = (1 - k) * self.var
        self.n_updates += 1

    def learn_taw(self, dr_before: float, dr_after: float, applied_net: float):
        """RLS on the observed response to an irrigation event."""
        if applied_net <= 3 or dr_before <= dr_after:
            return
        observed_capacity = dr_before          # field could absorb at least this
        gain = self.taw_var / (self.taw_var + 140.0)
        self.taw_hat += gain * (max(observed_capacity / 0.75, 40.0) - self.taw_hat)
        self.taw_var *= (1 - gain)

    @property
    def sigma(self) -> float:
        return float(np.sqrt(self.var))
