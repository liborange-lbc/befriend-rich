"""Valuation metrics computed from index PE data.

PE data is fetched on-demand from the existing market_insight index_kline
endpoint rather than stored in DB. Percentiles are computed against the
full available history (~8 years from Sina + CSIndex).
"""

import logging

logger = logging.getLogger(__name__)

# Index codes with PE support and their display names
INDEX_INFO = {
    "000016": "上证50",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000688": "科创50",
    "000932": "中证消费",
    "000933": "中证医药",
    "399986": "中证银行",
    "399808": "中证新能",
    "000993": "全指信息",
    "000922": "中证红利",
    "000015": "红利指数",
}

# DCA coefficient tiers: (temp_upper_bound, coefficient, label)
DCA_TIERS = [
    (20, 1.5, "极度低估"),
    (40, 1.2, "偏低估"),
    (60, 1.0, "正常"),
    (80, 0.8, "偏高估"),
    (100, 0.5, "极度高估"),
]


def compute_percentile(values: list[float], current: float) -> float:
    """Compute percentile rank of current value in historical distribution."""
    if not values:
        return 50.0
    below = sum(1 for v in values if v < current)
    return round(below / len(values) * 100, 2)


def compute_valuation_from_kline(kline_data: list[dict]) -> dict | None:
    """Given kline data (from index_kline API), compute valuation metrics.

    Each item: {"date": str, "close": float, "pe": float | None}
    """
    pe_points = [(d["date"], d["pe"]) for d in kline_data if d.get("pe") is not None]
    if len(pe_points) < 50:
        return None

    all_pe = [p[1] for p in pe_points]
    current_pe = pe_points[-1][1]
    current_date = pe_points[-1][0]

    percentile = compute_percentile(all_pe, current_pe)

    # Temperature = percentile directly (0-100)
    temperature = percentile

    # DCA coefficient
    dca_coeff = 1.0
    dca_label = "正常"
    for upper, coeff, label in DCA_TIERS:
        if temperature <= upper:
            dca_coeff = coeff
            dca_label = label
            break

    # PE stats
    pe_min = min(all_pe)
    pe_max = max(all_pe)
    pe_median = sorted(all_pe)[len(all_pe) // 2]
    pe_mean = sum(all_pe) / len(all_pe)

    return {
        "current_pe": round(current_pe, 2),
        "current_date": current_date,
        "pe_percentile": percentile,
        "temperature": round(temperature, 1),
        "dca_coefficient": dca_coeff,
        "dca_label": dca_label,
        "pe_min": round(pe_min, 2),
        "pe_max": round(pe_max, 2),
        "pe_median": round(pe_median, 2),
        "pe_mean": round(pe_mean, 2),
        "data_points": len(pe_points),
        "pe_history": [{"date": d, "pe": p} for d, p in pe_points],
    }


def get_dca_coefficient_table() -> list[dict]:
    """Return the DCA coefficient tier table."""
    return [
        {"range": f"≤{upper}%", "coefficient": coeff, "label": label}
        for upper, coeff, label in DCA_TIERS
    ]
