"""
AgriPilot :: reinforcement learning.

A tabular Q-learning agent that learns an irrigation policy purely from
trial and error against the field_model.Field environment -- no agronomic
formula, no forecast, no Kalman filter, just (state, action, reward) tuples
accumulated over many simulated seasons. It exists to answer a specific
question honestly: does the hand-designed, chance-constrained policy in
policies.AgriPilotAgent actually beat a policy that discovers its own
strategy from scratch?

State:  (depletion decile, days-since-last-irrigation bucket, crop-stage)
Action: {skip, light (40% of a full refill), full refill}
Reward: yield-linked terminal payoff at season end, shaped by a small
        per-step water cost so the agent isn't indifferent between two
        policies that reach the same terminal state via different amounts
        of water.

This is intentionally a small, interpretable state space (fits in a table,
no function approximation) -- appropriate for one field's irrigation timing
and honest about what tabular Q-learning can and can't do: it does not see
weather forecasts (the analytic agent does), which is the main reason the
comparison below is not simply "RL wins".
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CROPS, SOILS, IRRIGATION_SYSTEMS
from field_model import Field
from weather import WeatherGenerator

HERE = os.path.dirname(__file__)
OUTPUTS = os.path.join(HERE, "..", "..", "outputs")

ACTIONS = ["skip", "light", "full"]
N_DEPLETION_BINS = 8
N_GAP_BINS = 4
N_STAGE_BINS = 4


def discretise(dr, taw, gap, stage):
    d_bin = min(N_DEPLETION_BINS - 1, int(N_DEPLETION_BINS * dr / max(taw, 1e-6)))
    g_bin = min(N_GAP_BINS - 1, gap)
    return (d_bin, g_bin, stage)


class QLearningIrrigator:
    def __init__(self, crop_name: str, soil_name: str, system: str,
                 alpha: float = 0.15, gamma: float = 0.97, seed: int = 7):
        self.crop_name, self.soil_name, self.system = crop_name, soil_name, system
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)
        shape = (N_DEPLETION_BINS, N_GAP_BINS, N_STAGE_BINS, len(ACTIONS))
        self.Q = np.zeros(shape)

    def _depth_for(self, action, dr, eff, max_depth):
        if action == "skip":
            return 0.0
        if action == "light":
            return float(np.clip(0.4 * dr / eff, 0, max_depth))
        return float(np.clip(dr / eff, 0, max_depth))

    def train_episode(self, epsilon: float, monsoon_index: float, seed: int) -> float:
        crop, soil = CROPS[self.crop_name], SOILS[self.soil_name]
        eff = IRRIGATION_SYSTEMS[self.system]["efficiency"]
        max_depth = IRRIGATION_SYSTEMS[self.system]["max_depth"]
        start_doy = 160 if crop.season == "kharif" else 300
        wx = WeatherGenerator(np.random.default_rng(seed), monsoon_index).season(start_doy, crop.length)
        field = Field(crop, soil, self.system, 1.0, np.random.default_rng(seed + 500))

        last_gap = 3
        transitions = []
        for t in range(crop.length):
            s = discretise(field.dr, field.taw, min(last_gap, N_GAP_BINS - 1), crop.stage_of(t))
            if self.rng.random() < epsilon:
                a_idx = self.rng.integers(0, len(ACTIONS))
            else:
                a_idx = int(np.argmax(self.Q[s]))
            action = ACTIONS[a_idx]
            depth = self._depth_for(action, field.dr, eff, max_depth)
            n_today = crop.n_requirement / 4 if t in (5, 25, 50, 80) else 0.0
            field.step(wx[t], depth, n_today, None)
            last_gap = 0 if depth > 0 else last_gap + 1
            # stage of the day the episode is now entering (t+1), not the day
            # just simulated -- must match what the next loop iteration's "s"
            # will compute, or the backward-propagation chain breaks silently
            # at every stage boundary (this was the actual bug: three breaks,
            # one per boundary, which cut stage 3's learned values off from
            # ever reaching stages 0-2)
            next_stage = crop.stage_of(t + 1) if t + 1 < crop.length else crop.stage_of(t)
            s2 = discretise(field.dr, field.taw, min(last_gap, N_GAP_BINS - 1), next_stage)
            # small water-cost shaping term, scaled so its season total is a
            # minor fraction of the 0..1 terminal yield reward -- large enough
            # to break ties between equal-yield policies, far too small to
            # dominate the yield signal (that bug previously collapsed the
            # policy to "always skip")
            step_cost = -0.05 * (depth / max_depth) / crop.length
            transitions.append((s, a_idx, step_cost, s2))

        yc = field.yield_components()
        terminal_reward = yc["yield_t_ha"] / max(crop.y_max, 1e-6)   # 0..1

        # one-step Q-learning, processed in REVERSE chronological order within
        # each episode. A forward pass would only propagate the terminal
        # reward back by one state per full episode (since Q(s') is stale
        # until *after* its own transition is processed) -- with a ~150-day
        # season that needs ~150 episodes just to reach day 1. Processing the
        # episode backward means each state's successor has *already* been
        # refreshed earlier in this same pass, so one episode propagates the
        # terminal payoff through the entire trajectory immediately -- this
        # is what actually makes tabular Q-learning converge in a few hundred
        # episodes instead of tens of thousands.
        n_steps = len(transitions)
        for idx in range(n_steps - 1, -1, -1):
            s, a_idx, step_cost, s2 = transitions[idx]
            terminal = idx == n_steps - 1
            r = step_cost + (terminal_reward if terminal else 0.0)
            target = r if terminal else r + self.gamma * float(np.max(self.Q[s2]))
            self.Q[s][a_idx] += self.alpha * (target - self.Q[s][a_idx])
        return terminal_reward * crop.y_max

    def act(self, dr, taw, gap, stage) -> str:
        s = discretise(dr, taw, min(gap, N_GAP_BINS - 1), stage)
        return ACTIONS[int(np.argmax(self.Q[s]))]


def train_and_evaluate(crop_name="onion", soil_name="loam", system="drip",
                       n_train_episodes=450, n_eval_episodes=40, seed=7) -> dict:
    agent = QLearningIrrigator(crop_name, soil_name, system, seed=seed)
    rng = np.random.default_rng(seed)

    train_yields = []
    for ep in range(n_train_episodes):
        epsilon = max(0.05, 0.9 * (1 - ep / (0.8 * n_train_episodes)))
        mi = float(rng.uniform(0.7, 1.2))
        y = agent.train_episode(epsilon, mi, seed=1000 + ep)
        train_yields.append(y)

    # evaluate the learned greedy policy against the analytic AgriPilot policy
    # and farmer practice, on held-out seeds never seen during training
    from config import FarmerProfile
    from policies import AgentParams
    from simulate import run_season

    crop = CROPS[crop_name]
    eff = IRRIGATION_SYSTEMS[system]["efficiency"]
    max_depth = IRRIGATION_SYSTEMS[system]["max_depth"]

    rl_yields, rl_water = [], []
    for i in range(n_eval_episodes):
        seed_e = 500_000 + i
        start_doy = 160 if crop.season == "kharif" else 300
        wx = WeatherGenerator(np.random.default_rng(seed_e), 1.0).season(start_doy, crop.length)
        field = Field(crop, SOILS[soil_name], system, 1.0, np.random.default_rng(seed_e + 500))
        last_gap = 3
        for t in range(crop.length):
            action = agent.act(field.dr, field.taw, last_gap, crop.stage_of(t))
            depth = agent._depth_for(action, field.dr, eff, max_depth)
            n_today = crop.n_requirement / 4 if t in (5, 25, 50, 80) else 0.0
            field.step(wx[t], depth, n_today, None)
            last_gap = 0 if depth > 0 else last_gap + 1
        yc = field.yield_components()
        rl_yields.append(yc["yield_t_ha"])
        rl_water.append(field.irrigation_total)

    profile = FarmerProfile(0.5, 0.5, 0.4, 0.4, 0.55, "text", "en", 6, 12)
    ap_yields, ap_water = [], []
    fp_yields, fp_water = [], []
    for i in range(n_eval_episodes):
        seed_e = 500_000 + i
        ra = run_season(crop_name, soil_name, system, profile, "agripilot", seed=seed_e,
                        params=AgentParams())
        rb = run_season(crop_name, soil_name, system, profile, "farmer_practice", seed=seed_e)
        ap_yields.append(ra["yield_t_ha"]); ap_water.append(ra["irrigation_mm"])
        fp_yields.append(rb["yield_t_ha"]); fp_water.append(rb["irrigation_mm"])

    def summarise(y, w):
        return {"mean_yield_t_ha": float(np.mean(y)), "mean_water_mm": float(np.mean(w)),
                "water_productivity": float(np.mean(y) * 1000 / (np.mean(w) * 10))}

    result = {
        "setup": {"crop": crop_name, "soil": soil_name, "system": system,
                  "train_episodes": n_train_episodes, "eval_episodes": n_eval_episodes,
                  "state_space": [N_DEPLETION_BINS, N_GAP_BINS, N_STAGE_BINS],
                  "actions": ACTIONS},
        "training_curve_sample": [round(float(v), 2) for v in train_yields[::25]],
        "q_learning_agent": summarise(rl_yields, rl_water),
        "agripilot_analytic_agent": summarise(ap_yields, ap_water),
        "farmer_practice_baseline": summarise(fp_yields, fp_water),
        "note": ("Q-learning acts on soil state alone, with no weather forecast; the analytic "
                 "agent sees a 7-day ensemble forecast. The comparison isolates what learning "
                 "a policy from scratch buys versus what forecast information buys."),
    }
    return result


def run(save: bool = True) -> dict:
    result = train_and_evaluate()
    if save:
        os.makedirs(OUTPUTS, exist_ok=True)
        json.dump(result, open(os.path.join(OUTPUTS, "ml_reinforcement.json"), "w"), indent=1)
    return result


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=1))
