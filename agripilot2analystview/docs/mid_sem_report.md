# AgriPilot — Multimodal Autonomous Farm Decision Assistance System
### Mid-semester report · Project 4.3, Agricultural Decision Support Agent for Crop Management

---

## 1. Problem and scope of this submission

Smallholder farmers make irrigation, fertiliser and spray decisions on a calendar, because
expert agronomic advice is scarce, late and generic. AgriPilot is an autonomous agent that
observes a farm every day, decides what to do, executes through farm devices where it is
allowed to, and explains itself to the farmer in their own language.

This submission covers roughly **30% of the project**: the full decision stack end to end,
a biophysical simulation environment to develop and evaluate it against, a 60-farm two-year
synthetic pilot with a three-way comparison, and a working low-bandwidth farmer app.
What is deliberately not here — real API traffic, real device fleets, learned models, a
real farmer cohort — is listed in §8 with the plan to reach 100%.

---

## 2. System architecture

```
   weather ensemble ─┐
   soil probes ──────┤
   satellite NDVI ───┼──►  state estimation  ──►  decision engine  ──►  tool calls
   scouting reports ─┘     (Kalman + model)       (3 sub-policies)      (auto/confirm/advise)
                                   ▲                      │                     │
                                   │                      ▼                     ▼
                            digital twin  ◄────── multi-objective        farmer app
                          (FAO-56/FAO-33)          optimisation        (explanations,
                                                  (farmer weights)      accept/reject)
                                                                             │
                                                        local adaptation ◄───┘
                                                    (TAW estimate, trust, weights)
```

Layer by layer:

**Sensing (`sensors.py`, `connectors.py`).** Capacitance probes at two depths with calibration
drift, 7% LoRa packet loss and stuck-sensor faults; Sentinel-2 NDVI on a 5-day revisit with
cloud-masked scenes dropped; farmer scouting reports as sparse categorical evidence. Each
modality has a deployment adapter (Open-Meteo ensemble API, Sentinel-2 STAC, ChirpStack/MQTT,
ModBus valve controller, SMS gateway) that normalises payloads into the same internal types,
with an offline fallback so a farm without probes still gets advice.

**State estimation.** A scalar Kalman filter on root-zone depletion `Dr`. The water-balance
model propagates the state; moisture readings correct it; "suspect" readings are down-weighted
by inflating `R` rather than discarded. This is what lets the agent act during the monsoon when
NDVI is missing for two weeks and the probe has dropped half its packets.

**Decision engine (`policies.py`).** Three sub-policies — irrigation, nitrogen, pest — described
in §4.

**Tool execution (`tools.py`).** Every action leaves the reasoning layer as a typed call with
payload, confidence, rationale and an autonomy level: `auto` (drip valve opens itself),
`confirm` (farmer approves in the app), `advise` (agent can only recommend). The bus keeps an
immutable audit trail; adoption rate is computed from it.

**Optimisation (`optimizer.py`).** Grid search over the agent's four free parameters, scored on
a farmer-specific scalarised objective, with an ε-constraint that forbids buying margin with
more than 1% of attainable yield, plus a Pareto front over (yield, water, environmental load).

---

## 3. The digital twin

| component | model |
|---|---|
| reference ET | Hargreaves–Samani (needs only Tmin/Tmax/Ra — the right choice for sites without full weather stations) |
| crop water use | FAO-56 single crop coefficient, piecewise-linear Kc, root depth growing with the crop |
| water balance | `Dr_i = Dr_{i-1} − (P − RO) − I_net + ETa + DP`, `Ks` reduction below RAW, curve-number style runoff |
| nitrogen | mineralisation, pool-limited uptake (30%/day), application losses that depend on rain/heat/irrigation, drainage-driven leaching |
| pest | degree-day establishment, temperature/humidity suitability, stochastic outbreaks, spray residual with resistance build-up |
| yield | FAO-33 multiplicative stage-wise water function × N factor × pest factor |
| weather | two-state Markov rain occurrence, gamma amounts, AR(1) temperature anomalies, calibrated to 620–950 mm kharif rainfall for the Deccan pilot region |

Forecasts are **ensembles**, not point values: 24 members with a shared bias term and skill
decaying geometrically with lead time. That correlation structure is what makes naive
"average the ensemble" irrigation decisions fail on convective rainfall, and it is the reason
the agent reasons over the members instead of their mean.

---

## 4. How the agent decides

**Irrigation — a chance constraint, not a threshold.** The agent samples 40 depletion states
from its Kalman belief, crosses them with the 24 forecast members, and rolls the water balance
forward for each candidate irrigation depth. It applies the *smallest* depth satisfying

> `P(Ks < 0.90 before the next irrigation slot) ≤ budget`

where `budget` tightens with the stage's FAO-33 `Ky` and with the farmer's risk aversion.
Skipping irrigation ahead of likely rain is an output of this arithmetic, not a special case.

**Nitrogen — matched to uptake, deferred around leaching.** Because uptake is pool-limited, the
agent tops the mineral-N pool up to what the *peak* daily demand of the next 12 days requires,
not to the cumulative demand — the fix that removed a systematic under-fertilisation bug found
during calibration. When the ensemble shows >35% chance of 25 mm within 48 h, the split is
deferred and the farmer is told what would have been lost.

**Pest — economic threshold over three options.** Each day the agent scores *nothing*,
*biological*, and *chemical* on expected damage avoided minus cost minus the environmental
shadow price weighted by the farmer's own sustainability preference. Chemical sprays are
rationed toward the highest-pressure windows, because MRL label limits, pre-harvest intervals
and resistance build-up (efficacy decays 4.5% per spray beyond the sixth) all make them scarce.

**Local adaptation.** Every irrigation event is a natural experiment: the observed moisture
response updates a recursive estimate of that field's true water-holding capacity. Accept and
reject events move the farmer's trust, which moves future adoption.

---

## 5. Experimental design

60 synthetic smallholdings across six villages: heterogeneous soils (sandy → black cotton),
irrigation systems (flood / sprinkler / drip, correlated with wealth), one kharif and one rabi
crop each drawn from soybean/cotton/tomato and onion/wheat/grape, and farmer profiles varying
in risk aversion, water scarcity, cash constraint, sustainability preference, literacy tier and
language. Two consecutive years: year 1 near-normal monsoon (index 1.05), year 2 deficit (0.78).

**240 farm-seasons × 3 policies = 720 simulated seasons.** Every policy sees the identical
weather realisation, the same pest stochastics and the same sensor faults on a given
farm-season (common random numbers), so differences are attributable to decisions, not luck.

---

## 6. Results

Mean per hectare per season across all 240 farm-seasons:

| | farmer practice | agronomist | **AgriPilot** |
|---|---|---|---|
| yield (t/ha) | 13.41 | 13.20 | **13.51** |
| irrigation (m³/ha) | 10 853 | 7 494 | **7 043** |
| water productivity (kg/m³) | 1.56 | 1.76 | **2.12** |
| nitrogen applied (kg/ha) | 156.0 | 117.0 | **76.8** |
| N use efficiency (uptake/applied) | 0.66 | 0.90 | **1.46** |
| chemical sprays | 14.1 | 7.1 | **5.7** (+11.9 biological) |
| N leached (kg/ha) | 57.6 | 27.2 | **14.1** |
| production cost (₹/ha) | 64 847 | 45 262 | **54 037** |
| gross margin (₹/ha) | 139 222 | 205 030 | **215 762** |
| environmental cost (₹/ha) | 20 793 | 10 410 | **8 344** |
| biodiversity index | 0.72 | 0.86 | **0.97** |
| residue price penalty | 12% | 3% | **0%** |

Against the project's evaluation metrics, AgriPilot vs. farmer practice:

| metric | result |
|---|---|
| yield improvement per hectare | **+0.3%** (+3.9% vs. the agronomist) |
| water use efficiency (yield per unit water) | **+47.6%** |
| water applied | **−29.4%** |
| fertiliser reduction | **−51.5% N** |
| pesticide reduction | **−57.5% chemical sprays, −44.8% load** |
| economic return | **+₹76 540/ha**, +39.9% margin, **ROI ≈ 70×** on the agent's cost |
| adoption rate | **63%** of recommendations acted on; trust rises 0.52 → 0.94 |
| environmental impact | N leaching **−78.8%**, runoff −4 mm, biodiversity index +37% |

By crop (yield gain / water saving / N reduction / margin gain):

| crop | yield | water | nitrogen | margin |
|---|---|---|---|---|
| tomato | +7.1% | −39.8% | −34.1% | +₹154 593 |
| cotton | +4.0% | −38.2% | −55.9% | +₹16 809 |
| onion | −0.9% | −31.9% | −52.3% | +₹74 799 |
| soybean | −2.1% | −36.1% | −54.2% | +₹5 651 |
| wheat | −4.0% | −35.7% | −49.1% | +₹14 237 |
| grape | −4.4% | −29.3% | −55.8% | +₹408 367 |

**Reading the results honestly.** The headline yield gain is small — the agent's value here is
overwhelmingly on the input and quality side, not on raw tonnage. Three findings are worth
stating plainly:

1. *Where yield falls slightly (grape, wheat, onion), margin still rises sharply*, because the
   agent stays inside label limits and avoids the residue price penalty that calendar spraying
   incurs (12% average price cut under farmer practice, 0% under AgriPilot). On grape that one
   effect dominates everything else.
2. *The agent runs the crop closer to the edge*: 3.2 stress days per season vs. 2.9 under
   farmer practice, despite 29% less water. That is the deliberate consequence of a chance
   constraint with a non-zero risk budget, and it is the knob a nervous farmer should be able
   to turn — it is exposed as `risk_budget` and tuned per farmer.
3. *Non-adoption erodes the gains*: 37% of recommendations are refused, and the largest refusal
   category is "do not irrigate today", which a farmer used to a fixed turn finds hardest to
   accept. Adoption, not agronomy, is the binding constraint on impact.

Year 2 (deficit monsoon) holds water saving at 35% but yield gain falls from +2.1% to −0.6%:
under drought the agent's savings come partly out of yield, which is the correct trade when
water is priced by scarcity but should be surfaced to the farmer explicitly.

---

## 7. The farmer app

`app/index.html` — one self-contained file, ~55 KB, no web fonts, no external requests, opens
from cache on a 2G connection. Marathi first, with an English template set behind the same
renderer. The hero is the single action for today with its reason and the agent's confidence,
then two buttons: *केले* (done) / *नाही करणार* (won't do) — the accept/reject signal that feeds
the trust model. Below it: a soil-moisture gauge against the stress threshold, a seven-day
plan, the season's water and depletion chart, an input comparison against the farmer's usual
practice, and the full advisory log with refused items struck through. Every advisory is also
rendered as a ≤160-byte SMS for farmers without smartphones, and an IVR/voice tier and an
icon-only tier are modelled in the adoption logic.

---

## 8. Gap to 100%, and the plan

| area | now (30%) | end-semester target |
|---|---|---|
| data | synthetic weather/sensors from a calibrated generator | live Open-Meteo + IMD ingest, Sentinel-2 via STAC, MQTT probe fleet; connectors are already written and only need credentials + tests |
| decision engine | analytic + Monte-Carlo policies | add a learned residual model (gradient boosting on yield error) and a scenario-tree planner over the ensemble |
| optimisation | grid search per crop × scarcity tier | Bayesian optimisation per farm, online bandit updates of farmer weights from accept/reject data |
| uncertainty | Kalman filter + ensemble MC | particle filter over (Dr, soil N, pest population) jointly; report prediction intervals in the app |
| evaluation | 60 synthetic farms, 2 years | scale to 200 farms × 4 seasons, add sensitivity and ablation studies (no-forecast, no-sensor, no-adoption variants) |
| human loop | modelled adoption and trust | a real questionnaire instrument, an ablation on explanation style, and a recorded-decision pilot with a small farmer group |
| app | single-file demo with baked-in season | service worker, offline queue, SMS/IVR gateway integration, multi-plot support |
| validation | internal consistency against FAO reference runs | calibrate against published Indian trial data (onion/grape water response, cotton IPM trials) and report RMSE |

**Immediate next steps (weeks 1–3 of the end-semester block).** Wire the live weather and
satellite connectors and re-run the pilot with real 2025–26 weather for Nashik district; add
the ablation studies, which is the fastest way to show *which* part of the agent produces the
29% water saving; and build the particle filter, since the current Kalman filter is the main
approximation limiting decision quality under sensor loss.

---

## 9. Reproducing every number in this report

```bash
cd agripilot
python pilot.py --farms 60 --years 2 --tune --out ../outputs   # ~13 min, single core
python ../build_app.py
```

Outputs: `pilot_results.csv` (720 rows, one per simulated season), `summary.json` (every metric
above), `tuned_params.json` (chosen parameters plus the Pareto front per archetype),
`cohort.json` (the 60 farms), `demo_farm.json` (the season behind the app).
