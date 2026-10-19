"""Simple threshold flags computed from the forecast. These are NOT official warnings.

The limits below are our own placeholders and have not been validated with agronomists
or the India Meteorological Department.
"""
HEAVY_RAIN_MM = 50.0
HEAT_C = 40.0
COLD_C = 5.0
WIND_KMH = 40.0

RULES = [
    ("heavy_rain", "rain_mm", HEAVY_RAIN_MM, "ge"),
    ("heat", "temp_max_c", HEAT_C, "ge"),
    ("cold", "temp_min_c", COLD_C, "le"),
    ("strong_wind", "wind_max_kmh", WIND_KMH, "ge"),
]


def build_alerts(days):
    out = []
    for day in days:
        for kind, field, limit, op in RULES:
            value = day.get(field)
            if value is None:
                continue
            if (op == "ge" and value >= limit) or (op == "le" and value <= limit):
                out.append({"type": kind, "date": day["date"], "value": value, "threshold": limit})
    return out