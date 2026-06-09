from dataclasses import dataclass
import random

DURATIONS = {
    "material_shortage": (1.5, 4.5),
    "logistics_delay": (0.75, 2.5),
    "lifting_delay": (0.50, 1.75),
    "design_information_missing": (1.25, 5.0),
    "equipment_unavailable": (0.50, 2.25),
    "weather_or_site_condition": (0.50, 2.0),
}

@dataclass
class ExternalShock:
    day: int
    trade: str
    disruption_type: str
    base_duration: float
    consumed: bool = False

def generate_external_shock_schedule(seed: int, trades: list[str], days: int = 140, daily_shock_probability: float = 0.32):
    rng = random.Random(seed + 987654)
    types = list(DURATIONS.keys())
    shares = [0.30, 0.22, 0.16, 0.14, 0.10, 0.08]
    schedule = {}
    for day in range(days):
        n = 0
        if rng.random() < daily_shock_probability:
            n = 1 + int(rng.random() < 0.10)
        for _ in range(n):
            r, cum = rng.random(), 0.0
            dtype = types[-1]
            for t, s in zip(types, shares):
                cum += s
                if r <= cum:
                    dtype = t; break
            lo, hi = DURATIONS[dtype]
            schedule.setdefault(day, []).append(ExternalShock(day, rng.choice(trades), dtype, rng.triangular(lo, hi, (lo+hi)/2)))
    return schedule
