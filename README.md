# AgriPilot — Multimodal Autonomous Farm Decision Assistance System

Project 4.3 · Agricultural Decision Support Agent for Crop Management
**Mid-semester submission (~30% scope).** Everything in this repository runs offline with
numpy + pandas only; no API keys, no internet, no GPU.

---

## What this is

An autonomous agent that reads a farm's state every day — weather forecasts, soil moisture
probes, satellite canopy greenness, farmer scouting reports — and decides what to do about
**irrigation, nitrogen and pest control** on a smallholder farm, then explains each decision
in the farmer's language and waits for their answer.

Because a real pilot takes seasons, the agent is developed and evaluated against a
biophysical **digital twin** of the farm (FAO-56 water balance, mineral-N balance,
degree-day pest model, FAO-33 yield formation). The same twin is used inside the agent as
its forward model, so its planner and its world cannot silently disagree.

Three policies compete on identical weather, soil and pest realisations (paired comparison):

| policy | what it represents |
|---|---|
| `farmer_practice` | calendar irrigation, two heavy urea splits, calendar spraying |
| `agronomist` | competent extension agronomist visiting weekly, no forecast information |
| `agripilot` | the agent: daily sensor fusion, ensemble forecasts, chance-constrained irrigation, uptake-matched N, economic-threshold IPM |

---

## Quick start

```bash
pip install numpy pandas
cd agripilot

# one field-season, three policies
python -c "
from config import FarmerProfile
from simulate import run_season
p = FarmerProfile(0.5, 0.5, 0.4, 0.4, 0.55, 'text', 'en', 6, 12)
for pol in ('farmer_practice','agronomist','agripilot'):
    r = run_season('onion','loam','drip', p, pol, seed=11)
    print(pol, round(r['yield_t_ha'],2), round(r['irrigation_mm']), round(r['gross_margin']))
"

# full pilot: 60 farms x 2 years x 2 seasons x 3 policies  (~3 min)
python pilot.py --farms 60 --years 2 --out ../outputs

# add --tune to re-fit the agent's parameters per crop x water-scarcity tier (~10 min)
python pilot.py --farms 60 --years 2 --tune --out ../outputs
```

Rebuild the farmer app after a run:

```bash
python build_app_en.py     # writes app/index.html — English dashboard + AI assistant (~195 KB)
python build_app.py        # writes app/index_mr_lowbandwidth.html — Marathi, SMS-style (~55 KB)
```

`build_app_en.py` is the primary deliverable: a professional English dashboard with a
farmer-simple view and a full analyst view, four demo farms across different crops, and an
AI assistant tab grounded in that farm's actual simulated season data (falls back to a
rule-based Q&A engine if run outside an environment that grants live AI access).
`build_app.py` produces the earlier low-bandwidth, Marathi-first, SMS-sized variant for
farmers on basic phones or 2G connections — both read from the same simulation outputs.

---

## Layout

```
agripilot/
├── agripilot/
│   ├── config.py        crop + soil knowledge base, economics, residue rules, farmer profiles
│   ├── weather.py       stochastic weather generator, Hargreaves ET0, 24-member ensemble forecast
│   ├── field_model.py   the digital twin: water balance, N balance, pest damage, yield
│   ├── sensors.py       soil probes, satellite NDVI, scouting reports + Kalman state estimator
│   ├── policies.py      the three decision policies and the agent's reasoning
│   ├── farmer.py        adoption / trust model — recommendations can be refused
│   ├── tools.py         typed tool calls, autonomy levels, audit trail
│   ├── explain.py       English + Marathi explanation templates, SMS packing
│   ├── connectors.py    Open-Meteo, Sentinel-2, LoRaWAN probes, valve controller, SMS gateway
│   ├── optimizer.py     multi-objective grid search, epsilon-constraint, Pareto front
│   ├── simulate.py      one field-season end to end
│   └── pilot.py         cohort generation + the whole experiment + metrics
├── app/index.html                    English dashboard + AI assistant (build_app_en.py)
├── app/index_mr_lowbandwidth.html    Marathi SMS-style low-bandwidth view (build_app.py)
├── outputs/             pilot_results.csv, summary.json, tuned_params.json, cohort.json
├── docs/                mid-semester report
└── build_app.py
```

---

## The farmer app

`app/index.html` (published as a standalone page, or run locally) has two audiences behind one
toggle:

- **Farmer view** — the default. One action for today, in plain English, with a confidence
  score and two buttons: *Mark as done* / *Skip this*. That accept/decline signal is what the
  underlying trust and adoption model is built on.
- **Analyst view** — the same data, opened up: season-long water balance, input-use comparison
  against the farm's usual practice, canopy/pest charts, the full advisory log, and the
  aggregated 60-farm pilot results with a crop-by-crop breakdown.

A farm switcher in the sidebar moves between four demo farms spanning tomato, onion, grape and
cotton — a small stand-in for the "case studies across multiple farmers" deliverable.

**Assistant tab.** A chat interface grounded in that farm's actual simulated season — current
soil moisture, this season's water/nitrogen/spray totals against the farm's own baseline, and
the recent advisory log are all passed as context on every question. Where the hosting page has
live AI access it answers directly; otherwise it falls back to a rule-based Q&A engine that
still answers from the same real season data, so the tab is never non-functional.

## How the agent decides

**Irrigation — chance-constrained, not threshold-based.** The agent holds a Kalman belief over
root-zone depletion (mm). It samples 40 states from that belief, crosses them with the 24
forecast members, and simulates the next few days for each candidate depth. It applies the
*smallest* depth for which `P(water stress before the next irrigation slot) ≤ budget`, where
the budget tightens on stage-sensitive phases (high FAO-33 Ky) and for risk-averse farmers.
Skipping ahead of likely rain therefore comes out of the arithmetic, not a hand-written rule.

**Nitrogen — matched to uptake, deferred around leaching.** Roots can only draw a fraction of
the mineral-N pool per day, so the agent tops the pool up to what the *peak* daily demand of
the next 12 days needs, not to the total. If the ensemble shows >35% chance of 25 mm within
48 h, the split is deferred and the farmer is told why.

**Pest — economic threshold with a rationed chemical budget.** The agent scores three options
each day (nothing / biological / chemical) on expected damage avoided, minus cost, minus the
environmental shadow price weighted by the farmer's own sustainability preference. Chemical
sprays are rationed towards the highest-pressure windows because label limits, pre-harvest
intervals and resistance build-up all make them scarce.

**Local adaptation.** Irrigation events are natural experiments: the observed moisture response
updates a recursive estimate of the field's true water-holding capacity. Accept/reject feedback
moves the farmer's trust, which moves future adoption.

---

## Metrics produced

`outputs/summary.json` reports, against farmer practice: yield gain, water saving, water
productivity, nitrogen and pesticide reduction, N leaching, runoff, biodiversity index,
gross margin, ROI on the agent's cost, adoption rate, trust — overall, by crop and by year
(year 1 near-normal monsoon, year 2 deficit).

## Status

Roughly 30% of the full project. See `docs/mid_sem_report.md` for what is done, what the
numbers say, and the plan to 100%.

---

## Machine learning layer (`agripilot/ml/`)

The simulator and the rule-based/Bayesian agent above produce no learned models at all —
worth saying plainly, because it's a different thing from what's in this section. `ml/` adds
four models trained on the 240 AgriPilot-policy farm-seasons the pilot run already generated:

| module | technique | question it answers |
|---|---|---|
| `supervised.py` | Gradient-boosted regression | Predicts yield *as a fraction of each crop's attainable potential* (not raw yield — that's dominated trivially by which crop was planted) from practice and context features. Cross-validated by `GroupKFold` on farm ID so no farm leaks across train/test. |
| `supervised.py` | Gradient-boosted classification | Predicts, from information known **before the season starts** (soil, crop, system, farmer context — irrigation/nitrogen/sprays are deliberately excluded), whether a farm is headed for above-median water stress. |
| `unsupervised.py` | K-means + PCA | Groups the 120 (farm × crop) profiles into management archetypes from water/nitrogen/spray/margin patterns, with no labels. Cluster count is chosen by silhouette score, then traded off against actionability by a documented rule, not silhouette-maximised blindly. |
| `anomaly.py` | Isolation Forest | Flags sensor-days whose rain/irrigation/depletion relationship doesn't fit the rest of that farm's season — a model-free check that sits alongside, not instead of, the physics-based Kalman filter in `sensors.py`. |
| `reinforcement.py` | Tabular Q-learning | Learns an irrigation policy from scratch (no agronomic formula, no forecast) purely from simulated trial and error, then is evaluated against the hand-designed analytic agent on held-out seasons — an honest answer to "does the designed policy actually beat a learned one." |

Run all four and write `outputs/ml_summary.json` (also what the dashboard's **ML insights**
tab reads):

```bash
cd agripilot/ml
python run_all.py       # ~15-20s
```

**Results as of the last run** (see `outputs/ml_summary.json` for the full numbers):

- Yield-efficiency regressor: cross-validated R² ≈ 0.72, MAE ≈ 4.2 percentage points of
  attainable yield (vs. 9.7 points for a mean-only baseline).
- Pre-season stress classifier: ≈78% cross-validated accuracy, ROC-AUC ≈ 0.76 (baseline from
  always predicting the majority class: 71%).
- K-means finds 4 farm archetypes (e.g. "water-scarce high-efficiency", "cash-constrained
  smallholder") from unlabelled management data.
- Isolation Forest flags ~5% of sensor-days per farm as statistically anomalous.
- The learned Q-learning irrigation policy reaches 21.97 t/ha on held-out onion seasons,
  against 25.18 t/ha for the forecast-aware analytic agent and 26.94 t/ha for calendar
  irrigation (which over-waters relative to what the crop needs) — the honest reading is that
  forecast information, not the learning process itself, is most of what separates the
  analytic agent from a policy that only sees today's soil state.

The debugging story behind `reinforcement.py` is worth knowing if asked: the first working
version silently collapsed to "never irrigate" because of two real, fixable bugs — reward-
shaping magnitudes that let a small water-cost penalty dominate the actual yield signal, and a
state-labelling off-by-one where the successor state used the *current* day's growth stage
instead of the *next* day's, which silently broke value propagation at every stage boundary.
Both are fixed and explained in comments in the file; it's a genuine, debugged result rather
than one that happened to run on the first try.
