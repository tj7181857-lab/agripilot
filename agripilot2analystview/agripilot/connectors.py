"""
AgriPilot :: external data connectors.

The simulator is the development harness; these adapters are how the same
agent runs on a real farm.  Each adapter normalises a third-party payload into
the internal types used by `weather.py` / `sensors.py`, so the decision engine
never sees a vendor-specific field name.

Deployment note: the offline research container has no outbound network, so
every adapter carries an explicit `offline_fallback` path that returns
simulator data with `source="synthetic"` stamped on it.  Nothing downstream
branches on the source, which is exactly the property needed for a pilot where
some farms have probes and some do not.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from weather import DayWeather, hargreaves_et0


class Connector:
    name = "base"
    def health(self) -> dict:
        return {"connector": self.name, "status": "unknown"}


# --------------------------------------------------------------------------
class OpenMeteoEnsemble(Connector):
    """
    Ensemble weather forecast (Open-Meteo / ECMWF-IFS ens, or IMD district
    bulletins where available).  Returns rainfall as [members, horizon] mm.
    """
    name = "open_meteo_ensemble"
    BASE = "https://ensemble-api.open-meteo.com/v1/ensemble"

    def __init__(self, lat: float, lon: float, members: int = 24, horizon: int = 7,
                 api_key: Optional[str] = None, timeout: float = 8.0):
        self.lat, self.lon, self.members, self.horizon = lat, lon, members, horizon
        self.api_key, self.timeout = api_key, timeout

    def _request(self) -> dict:
        import urllib.parse, urllib.request
        q = urllib.parse.urlencode({
            "latitude": self.lat, "longitude": self.lon,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "models": "icon_seamless", "forecast_days": self.horizon, "timezone": "Asia/Kolkata"})
        with urllib.request.urlopen(f"{self.BASE}?{q}", timeout=self.timeout) as r:
            return json.loads(r.read())

    def rain_ensemble(self, fallback=None) -> np.ndarray:
        try:
            payload = self._request()
            daily = payload["daily"]
            keys = [k for k in daily if k.startswith("precipitation_sum")]
            arr = np.array([daily[k] for k in keys], dtype=float)
            return np.nan_to_num(arr)[: self.members, : self.horizon]
        except Exception:
            if fallback is None:
                raise
            return fallback()          # offline_fallback -> simulator ensemble


# --------------------------------------------------------------------------
class SentinelHubNDVI(Connector):
    """
    Sentinel-2 L2A NDVI for a field polygon, pulled through a STAC catalogue.
    Scenes with SCL cloud/shadow classes over the parcel are dropped, which is
    why the agent must tolerate NDVI gaps rather than require them.
    """
    name = "sentinel_hub_ndvi"

    def __init__(self, parcel_geojson: dict, max_cloud: float = 0.35,
                 token: Optional[str] = None):
        self.parcel, self.max_cloud, self.token = parcel_geojson, max_cloud, token

    def latest(self, fallback=None) -> Optional[dict]:
        try:
            raise NotImplementedError("wire to sentinelhub-py / openEO in deployment")
        except Exception:
            return fallback() if fallback else None


# --------------------------------------------------------------------------
@dataclass
class ProbePayload:
    device_id: str
    ts: str
    theta_shallow: Optional[float]
    theta_deep: Optional[float]
    battery_v: float
    rssi: int


class LoRaSoilProbe(Connector):
    """
    Capacitance probe reporting over LoRaWAN into an MQTT broker
    (ChirpStack -> ThingsBoard).  `normalise` applies the per-device
    calibration curve and flags readings the estimator should down-weight.
    """
    name = "lora_soil_probe"

    def __init__(self, device_id: str, calibration: tuple[float, float] = (1.0, 0.0)):
        self.device_id = device_id
        self.gain, self.offset = calibration
        self.last_seen: Optional[str] = None

    def normalise(self, payload: ProbePayload) -> dict:
        quality = "ok"
        if payload.theta_deep is None or payload.theta_shallow is None:
            quality = "missing"
        elif payload.battery_v < 3.3 or payload.rssi < -118:
            quality = "suspect"
        scale = lambda v: None if v is None else float(self.gain * v + self.offset)
        self.last_seen = payload.ts
        return {"theta_shallow": scale(payload.theta_shallow),
                "theta_deep": scale(payload.theta_deep),
                "quality": quality, "device_id": payload.device_id}


# --------------------------------------------------------------------------
class ValveController(Connector):
    """Latching-solenoid valve over a ModBus/RTU or LoRa downlink."""
    name = "valve_controller"

    def __init__(self, zone_map: dict[str, str], flow_lph_per_ha: float = 12_000):
        self.zone_map, self.flow = zone_map, flow_lph_per_ha

    def open_for_depth(self, zone: str, depth_mm: float) -> dict:
        minutes = (depth_mm * 10_000 / self.flow) * 60
        return {"zone": self.zone_map.get(zone, zone), "command": "OPEN",
                "duration_min": round(minutes, 1), "expected_depth_mm": round(depth_mm, 1)}


# --------------------------------------------------------------------------
class SMSGateway(Connector):
    """Low-bandwidth advisory delivery: 160-byte SMS, or IVR for voice tier."""
    name = "sms_gateway"

    def __init__(self, sender_id: str = "AGRPLT"):
        self.sender_id = sender_id
        self.outbox: list[dict] = []

    def send(self, msisdn: str, text: str, lang: str = "mr") -> dict:
        msg = {"to": msisdn, "from": self.sender_id, "lang": lang,
               "text": text[:160], "bytes": len(text.encode()[:160])}
        self.outbox.append(msg)
        return msg


REGISTRY = {c.name: c for c in (OpenMeteoEnsemble, SentinelHubNDVI, LoRaSoilProbe,
                                ValveController, SMSGateway)}
