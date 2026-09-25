"""
AgriPilot :: agronomic knowledge base and economic constants.

All crop coefficients follow the FAO-56 single-crop-coefficient convention
(Allen et al., 1998) and the FAO-33 water-production function (Doorenbos &
Kassam, 1979).  Values are calibrated for semi-arid Deccan plateau conditions
(Nashik / Ahmednagar belt, Maharashtra, India) which is the pilot region.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# Crop knowledge
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Crop:
    name: str
    season: str                      # kharif (monsoon) | rabi (winter)
    stage_days: Tuple[int, int, int, int]   # initial, development, mid, late
    kc: Tuple[float, float, float]          # kc_ini, kc_mid, kc_end
    root_depth: Tuple[float, float]         # min, max effective rooting depth (m)
    p_depletion: float                      # fraction of TAW before stress (FAO p)
    ky_stage: Tuple[float, float, float, float]   # yield response factor per stage
    y_max: float                     # attainable yield, t/ha, under good management
    price: float                     # farm-gate price, INR / tonne
    n_requirement: float             # total N uptake requirement, kg/ha
    n_credit: float                  # biological fixation / residual credit, kg/ha
    key_pest: str
    pest_base_temp: float            # degree-day base for the key pest, degC
    pest_dd_threshold: float         # accumulated DD before population establishes
    pest_humidity_driven: bool
    max_damage: float                # yield fraction lost if left fully unprotected

    @property
    def length(self) -> int:
        return sum(self.stage_days)

    def stage_of(self, dap: int) -> int:
        """Return growth stage index 0..3 for a given day-after-planting."""
        edges, acc = [], 0
        for d in self.stage_days:
            acc += d
            edges.append(acc)
        for i, e in enumerate(edges):
            if dap < e:
                return i
        return 3

    def kc_at(self, dap: int) -> float:
        """Piecewise-linear Kc curve."""
        ini, dev, mid, late = self.stage_days
        k_ini, k_mid, k_end = self.kc
        if dap < ini:
            return k_ini
        if dap < ini + dev:
            return k_ini + (k_mid - k_ini) * (dap - ini) / max(dev, 1)
        if dap < ini + dev + mid:
            return k_mid
        frac = (dap - ini - dev - mid) / max(late, 1)
        return k_mid + (k_end - k_mid) * min(frac, 1.0)

    def root_depth_at(self, dap: int) -> float:
        zmin, zmax = self.root_depth
        ini, dev = self.stage_days[0], self.stage_days[1]
        if dap >= ini + dev:
            return zmax
        return zmin + (zmax - zmin) * (dap / max(ini + dev, 1))

    def n_uptake_fraction(self, dap: int) -> float:
        """Cumulative N uptake as a logistic function of thermal progress."""
        x = dap / self.length
        # logistic centred at 45% of the cycle
        import math
        return 1.0 / (1.0 + math.exp(-11.0 * (x - 0.45)))


CROPS: Dict[str, Crop] = {
    "onion": Crop(
        "onion", "rabi", (15, 25, 70, 40), (0.70, 1.05, 0.75), (0.15, 0.45), 0.30,
        (0.45, 0.60, 1.10, 0.80), 34.0, 13_500, 110, 0, "thrips", 11.5, 210, False, 0.35),
    "tomato": Crop(
        "tomato", "kharif", (30, 40, 45, 30), (0.60, 1.15, 0.80), (0.25, 0.85), 0.40,
        (0.40, 0.70, 1.10, 0.85), 55.0, 11_000, 150, 0, "leaf miner / early blight",
        10.0, 180, True, 0.45),
    "grape": Crop(
        "grape", "rabi", (20, 50, 75, 60), (0.30, 0.85, 0.45), (0.45, 1.10), 0.35,
        (0.30, 0.65, 1.05, 0.60), 24.0, 46_000, 125, 0, "downy mildew", 10.0, 160, True, 0.55),
    "soybean": Crop(
        "soybean", "kharif", (20, 35, 60, 25), (0.40, 1.15, 0.50), (0.25, 1.00), 0.50,
        (0.35, 0.75, 1.00, 0.55), 3.1, 46_000, 90, 55, "girdle beetle", 12.0, 250, False, 0.30),
    "wheat": Crop(
        "wheat", "rabi", (20, 30, 60, 30), (0.40, 1.15, 0.35), (0.25, 1.20), 0.55,
        (0.30, 0.60, 1.05, 0.50), 5.4, 23_000, 120, 0, "aphid / yellow rust", 8.0, 230, True, 0.28),
    "cotton": Crop(
        "cotton", "kharif", (30, 50, 60, 55), (0.35, 1.15, 0.60), (0.30, 1.30), 0.65,
        (0.30, 0.60, 1.00, 0.70), 2.4, 68_000, 110, 0, "pink bollworm", 12.0, 320, False, 0.50),
}

# --------------------------------------------------------------------------
# Soil knowledge
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Soil:
    name: str
    field_capacity: float     # m3/m3
    wilting_point: float      # m3/m3
    infiltration: float       # mm/day maximum
    n_mineralisation: float   # kg N /ha /day from organic matter
    leach_fraction: float     # fraction of drained N lost per mm of deep percolation

    def taw(self, root_depth_m: float) -> float:
        """Total available water in the root zone, mm."""
        return 1000.0 * (self.field_capacity - self.wilting_point) * root_depth_m


SOILS: Dict[str, Soil] = {
    "sandy":       Soil("sandy",      0.14, 0.06, 60, 0.08, 0.0060),
    "sandy_loam":  Soil("sandy_loam", 0.20, 0.09, 45, 0.14, 0.0040),
    "loam":        Soil("loam",       0.28, 0.13, 32, 0.20, 0.0028),
    "clay_loam":   Soil("clay_loam",  0.33, 0.19, 22, 0.26, 0.0018),
    "black_cotton": Soil("black_cotton", 0.42, 0.26, 12, 0.32, 0.0010),
}

# --------------------------------------------------------------------------
# Economics (INR, 2025-26 pilot-region figures)
# --------------------------------------------------------------------------

ECON = {
    "water_cost_per_mm_ha": 34.0,    # pumping energy + wear, 1 mm/ha = 10 m3
    "irrigation_labour_event": 260.0,          # manual flood turn
    "irrigation_labour_by_system": {"flood": 260.0, "sprinkler": 140.0, "drip": 30.0},
    "n_cost_per_kg": 29.0,
    "fert_application_cost": 420.0,
    "spray_cost_chemical": 1_350.0,
    "spray_cost_biological": 900.0,
    "scouting_cost": 120.0,
    "sensor_amortised_per_season": 1_100.0,
}

# Environmental damage coefficients used by the sustainability score
ENV = {
    "n_leach_damage_per_kg": 180.0,   # shadow price of leached N (INR/kg)
    "pesticide_load_per_spray": 1.0,  # chemical spray = 1.0 load unit, bio = 0.15
    "pesticide_damage_per_load": 700.0,
    "runoff_damage_per_mm": 9.0,
    "biodiversity_penalty_per_chem_spray": 0.02,   # index points
}

IRRIGATION_SYSTEMS = {
    "flood":     {"efficiency": 0.55, "max_depth": 75, "min_depth": 35},
    "sprinkler": {"efficiency": 0.75, "max_depth": 40, "min_depth": 10},
    "drip":      {"efficiency": 0.90, "max_depth": 30, "min_depth": 4},
}


@dataclass
class FarmerProfile:
    """Preferences and constraints that AgriPilot adapts to."""
    risk_aversion: float           # 0 = risk neutral, 1 = very conservative
    water_scarcity: float          # 0 = canal/assured, 1 = failing borewell
    cash_constraint: float         # 0 = liquid, 1 = severely constrained
    sustainability_pref: float     # weight on environmental objective
    tech_trust: float              # initial trust in the agent, 0..1
    literacy_tier: str             # "text" | "voice" | "icon"
    language: str
    habit_irrigation_interval: int
    habit_spray_interval: int
    weights: Dict[str, float] = field(default_factory=dict)

    def objective_weights(self) -> Dict[str, float]:
        if self.weights:
            return self.weights
        return {
            "yield": 1.0,
            "cost": 0.55 + 0.45 * self.cash_constraint,
            "water": 0.25 + 0.75 * self.water_scarcity,
            "environment": 0.15 + 0.85 * self.sustainability_pref,
        }


# --------------------------------------------------------------------------
# Residue / market rules.  Chemical sprays beyond the label limit, or inside
# the pre-harvest interval, put the consignment at risk of MRL rejection -
# a real and expensive constraint for table grape, onion and tomato in this
# region, and one that calendar spraying routinely violates.
# --------------------------------------------------------------------------

PEST_RULES = {
    "onion":   {"max_chem": 8,  "phi_days": 18, "mrl_penalty": 0.14},
    "tomato":  {"max_chem": 8,  "phi_days": 15, "mrl_penalty": 0.16},
    "grape":   {"max_chem": 6,  "phi_days": 30, "mrl_penalty": 0.30},
    "soybean": {"max_chem": 5,  "phi_days": 20, "mrl_penalty": 0.0},
    "wheat":   {"max_chem": 4,  "phi_days": 25, "mrl_penalty": 0.0},
    "cotton":  {"max_chem": 9,  "phi_days": 20, "mrl_penalty": 0.0},
}
