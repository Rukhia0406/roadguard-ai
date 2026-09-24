from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class RepairMetrics:
    severity_score: float
    surface_area_sqm: float
    patch_depth_m: float
    asphalt_volume_m3: float
    asphalt_weight_tonnes: float
    bags_25kg: int
    tack_coat_liters: float
    estimated_cost_usd: float
    estimated_cost_inr: float
    urgency_level: str


def clamp_severity(score: float) -> float:
    return max(1.0, min(10.0, float(score)))


def calculate_repair_metrics(severity_score: float) -> RepairMetrics:
    score = clamp_severity(severity_score)
    fraction = (score - 1.0) / 9.0
    surface_area = 0.05 + fraction * (1.20 - 0.05)
    patch_depth = 0.03 + fraction * (0.10 - 0.03)
    volume = surface_area * patch_depth
    weight_tonnes = volume * 2.4 * 1.15

    if score >= 7.0:
        urgency = "CRITICAL"
    elif score >= 4.0:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    estimated_cost_usd = round(45.0 + weight_tonnes * 140.0, 2)
    estimated_cost_inr = round(estimated_cost_usd * 83.0, 2)

    return RepairMetrics(
        severity_score=round(score, 2),
        surface_area_sqm=round(surface_area, 4),
        patch_depth_m=round(patch_depth, 4),
        asphalt_volume_m3=round(volume, 4),
        asphalt_weight_tonnes=round(weight_tonnes, 4),
        bags_25kg=ceil(weight_tonnes * 1000 / 25),
        tack_coat_liters=round(surface_area * 0.6, 4),
        estimated_cost_usd=estimated_cost_usd,
        estimated_cost_inr=estimated_cost_inr,
        urgency_level=urgency,
    )