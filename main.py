#!/usr/bin/env python3
"""Forecast four hours of Polymarket attribution prices as five quantiles per minute.

Reads every ``<id>.in`` case in MAKEFUN_INPUT_DIR (else /input) and writes one
``<id>.out`` per case to MAKEFUN_OUTPUT_DIR (else /output), offline, stdlib only.

House I/O contract (kit starter/main.ts): a case is
``{"schema": "makefun/polymarket-case/v1", "case", "at", "horizon_minutes",
"quantiles", "event", "markets": [{"id", "name", "slug", "yes_token", "start",
"prices"}]}`` where ``prices`` runs one per minute from ``start`` to ``at``
inclusive, so ``prices[-1]`` is the price at the checkpoint.

An output is ``{"forecasts": [{"id": ..., "q": [[5 numbers] x H]}]}``: every
market of the case exactly once, H rows, each row five finite numbers in [0, 1]
at the levels 0.05/0.25/0.50/0.75/0.95 in that order, non-decreasing across the
row. Anything else is an invalid case and scores as if every number were 0.5.

BLEND-WIDTH VARIANT (slot poly-v3): the band half-width blends the market's own
measured one-minute volatility with the house sigma (60/40) and applies width
factor 0.20 -- the widest ticket of the three, sized for a more volatile final.
No drift: the median stays pinned on the checkpoint price.
"""

import json
import math
import os
import statistics
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]
SIGMA_FALLBACK = 0.0025
DELTA_WINDOW = 60
WIDTH_FACTOR = 0.20  # blend width: k = 0.20 x (0.6 x clamped stdev + 0.4 x house sigma)
BLEND_VOL = 0.6      # weight on the measured stdev of the 60m steps
BLEND_HOUSE = 0.4    # weight on the house sigma 0.0025


def clamp01(x: float) -> float:
    """x clipped to [0, 1] and rounded to six decimals (never -0).

    A non-finite x (NaN/inf reaching here only through a broken price series)
    collapses to the neutral 0.5 so the row still satisfies the format gate
    instead of poisoning the JSON with NaN, which parsers reject outright.
    """
    if not math.isfinite(x):
        return 0.5
    v = min(1.0, max(0.0, x))
    return round(v, 6) + 0.0


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        levels = case.get("quantiles") or QUANTILES
        if [round(t, 6) for t in levels] != QUANTILES:
            raise ValueError(f"{path.name} asks for quantiles {levels}, not {QUANTILES}")
        if int(case.get("horizon_minutes") or 0) < 1:
            raise ValueError(f"{path.name} has no horizon_minutes")
        forecasts = [forecast_market(m, case["horizon_minutes"]) for m in case["markets"]]
        out = OUTPUT_DIR / (path.stem + ".out")
        out.write_text(json.dumps({"forecasts": forecasts}, separators=(",", ":")) + "\n", encoding="utf-8")


def band_width(prices: list) -> float:
    """Band half-width k from blended volatility (the poly-v3 blend variant).

    stdev of the last 60 one-minute price steps ``p_i - p_{i-1}`` (all steps
    when the series is shorter than 60 minutes -- computed by index, never by
    self-pairing slices, so a short series still measures its real volatility),
    clamped to [0.0005, 0.05], blended 60/40 with the house sigma 0.0025, then
    scaled by WIDTH_FACTOR (0.20 here). A history too short to measure
    (< 7 steps) is treated as exactly the house sigma before blending,
    matching the lab recipe that produced this config.
    """
    steps = [prices[i] - prices[i - 1] for i in range(max(1, len(prices) - DELTA_WINDOW), len(prices))]
    s = statistics.pstdev(steps) if len(steps) > 5 else SIGMA_FALLBACK
    s_c = min(0.05, max(0.0005, s))
    return WIDTH_FACTOR * (BLEND_VOL * s_c + BLEND_HOUSE * SIGMA_FALLBACK)


def forecast_market(market: dict, horizon: int) -> dict:
    """One market's quantile rows: a blended volatility band around the checkpoint.

    q_tau(h) = clamp(x + z_tau * k * sqrt(h)) with no drift: the median sits on
    the checkpoint price x = prices[-1] and the spread grows with sqrt(h),
    widened by the blend factor 0.20 (variant poly-v3). Rows are made
    non-decreasing across quantiles after clamping so the output can never be
    rejected for crossing bands.
    """
    prices = market["prices"]
    if not prices:
        raise ValueError(f"market {market.get('id')} has no prices")
    x = prices[-1]
    k = band_width(prices)

    rows = []
    for h in range(1, horizon + 1):
        row = [clamp01(x + z * k * math.sqrt(h)) for z in Z]
        for i in range(1, len(row)):  # quantiles must never cross
            if row[i] < row[i - 1]:
                row[i] = row[i - 1]
        rows.append(row)
    return {"id": market["id"], "q": rows}


if __name__ == "__main__":
    main()
