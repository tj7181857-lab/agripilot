"""
AgriPilot :: farmer-in-the-loop model.

An agronomically optimal recommendation that is ignored has zero value, so the
simulator models adoption explicitly.  Probability of acting on a
recommendation rises with trust, explanation confidence and framing, and falls
with how far the advice departs from the farmer's habit, how much cash it asks
for today, and how illegible it is on their device.

Trust is updated from observed consequences (a skipped irrigation that was
followed by rain builds trust; visible wilting destroys it), which is what makes
adoption a *dynamic* quantity across a season rather than a fixed rate.
"""
from __future__ import annotations

import numpy as np


class FarmerAgent:
    def __init__(self, profile, rng: np.random.Generator):
        self.p = profile
        self.rng = rng
        self.trust = profile.tech_trust
        self.trust_history = [self.trust]
        self.offered = 0
        self.accepted = 0
        self.rejected_kinds: dict[str, int] = {}

    # ------------------------------------------------------------------
    def _deviation(self, kind: str, payload: dict) -> float:
        if kind == "skip_irrigation":
            # skipping feels risky to a farmer used to a fixed turn
            return 0.55
        if kind == "irrigate":
            habitual = 35.0
            return float(min(abs(payload.get("depth", 0) - habitual) / 45.0, 1.0))
        if kind == "fertilise":
            return 0.25
        if kind == "defer_fertiliser":
            return 0.45
        if kind == "spray":
            return 0.2
        if kind == "no_spray":
            return 0.6      # not spraying when neighbours are spraying is hard
        return 0.3

    def _cash_ask(self, kind: str, payload: dict) -> float:
        if kind == "fertilise":
            return 0.6
        if kind == "spray":
            return 0.7
        return 0.05

    def consider(self, kind: str, payload: dict, confidence: float) -> bool:
        self.offered += 1
        legibility = {"text": 1.0, "voice": 0.92, "icon": 0.85}[self.p.literacy_tier]
        score = (0.55
                 + 2.1 * (self.trust - 0.5)
                 + 1.15 * (confidence - 0.5)
                 + 0.7 * (legibility - 0.9)
                 - 1.55 * self._deviation(kind, payload)
                 - 1.25 * self.p.cash_constraint * self._cash_ask(kind, payload)
                 - 0.45 * self.p.risk_aversion * (kind in ("skip_irrigation", "no_spray")))
        p = 1 / (1 + np.exp(-score))
        ok = bool(self.rng.random() < p)
        if ok:
            self.accepted += 1
        else:
            self.rejected_kinds[kind] = self.rejected_kinds.get(kind, 0) + 1
        return ok

    # ------------------------------------------------------------------
    def observe_outcome(self, ks: float, visible_stress: bool, saved_money: float):
        """Weekly trust update from what the farmer can actually see."""
        delta = 0.0
        if visible_stress:
            delta -= 0.06
        elif ks > 0.95:
            delta += 0.018
        if saved_money > 0:
            delta += 0.012
        self.trust = float(np.clip(self.trust + delta, 0.05, 0.98))
        self.trust_history.append(self.trust)

    @property
    def adoption_rate(self) -> float:
        return self.accepted / self.offered if self.offered else 0.0

    def satisfaction(self, margin_gain_pct: float, water_saved_pct: float,
                     workload_change: float) -> float:
        """1-5 Likert score, the metric the pilot survey would collect."""
        s = (2.5
             + 0.028 * np.clip(margin_gain_pct, -40, 60)
             + 0.012 * np.clip(water_saved_pct, -30, 60)
             + 1.1 * (self.trust - 0.5)
             - 0.6 * max(workload_change, 0))
        return float(np.clip(s, 1.0, 5.0))
