"""
AgriPilot :: tool-execution layer.

Every action the agent takes leaves the reasoning layer as a *typed tool call*
with a machine-readable payload, a confidence, a plain-language justification
and an autonomy level.  Three autonomy levels are supported:

  auto      the agent actuates directly (valve controller, injector pump)
  confirm   the farmer must approve in the app before actuation
  advise    the agent can only recommend (e.g. contracting a spray crew)

The bus records an immutable audit trail; this is what the evaluation harness
reads to compute adoption rate, and what a farmer or auditor reads to ask
"why did it open the valve on the 12th?".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Any, Optional


@dataclass
class ToolCall:
    day: int
    date_label: str
    tool: str
    args: dict
    confidence: float
    autonomy: str
    rationale: str
    expected_benefit: dict
    status: str = "pending"          # pending | executed | rejected | deferred
    farmer_feedback: Optional[str] = None


class ActuatorBus:
    """Simulated device/service endpoints + audit log."""

    def __init__(self, farm_id: str):
        self.farm_id = farm_id
        self.log: list[ToolCall] = []

    # -- endpoints ---------------------------------------------------------
    def irrigate(self, depth_mm: float, zone: str = "main") -> dict:
        return {"endpoint": "valve_controller.open",
                "zone": zone, "depth_mm": round(depth_mm, 1),
                "litres_per_ha": round(depth_mm * 10_000, 0)}

    def apply_fertiliser(self, n_kg: float, product: str, method: str) -> dict:
        urea_kg = round(n_kg / 0.46, 1) if product == "urea" else round(n_kg / 0.185, 1)
        return {"endpoint": "fertigation.schedule",
                "n_kg_per_ha": round(n_kg, 1), "product": product,
                "product_kg_per_ha": urea_kg, "method": method}

    def spray(self, kind: str, target: str) -> dict:
        return {"endpoint": "spray_service.book" if kind == "chemical"
                else "biocontrol.dispatch", "kind": kind, "target": target}

    def advisory(self, message: str, channel: str) -> dict:
        return {"endpoint": "notify.push", "channel": channel, "message": message}

    # -- bookkeeping -------------------------------------------------------
    def emit(self, call: ToolCall) -> ToolCall:
        self.log.append(call)
        return call

    def to_json(self) -> str:
        return json.dumps([asdict(c) for c in self.log], indent=1)

    def stats(self) -> dict:
        total = len(self.log)
        executed = sum(1 for c in self.log if c.status == "executed")
        return {"calls": total, "executed": executed,
                "adoption_rate": executed / total if total else 0.0}
