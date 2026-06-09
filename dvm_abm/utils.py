from statistics import mean

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def clamp_range(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def safe_mean(values):
    return mean(values) if values else 0.0
