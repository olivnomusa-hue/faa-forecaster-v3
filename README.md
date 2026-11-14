# faa-forecaster-v3 — blended-width quantile bands for the FAA attribution markets

[![make.fun · polymarket-faa-attribution-01](https://make.fun/badge/polymarket-faa-attribution-01.svg)](https://make.fun/bounty/polymarket-faa-attribution-01?utm_source=github&utm_medium=readme&utm_campaign=polymarket-faa-attribution-01)
[![rank](https://make.fun/badge/polymarket-faa-attribution-01/olivnomusa-hue/faa-forecaster-v3/rank.svg)](https://make.fun/bounty/polymarket-faa-attribution-01?utm_source=github&utm_medium=readme&utm_campaign=polymarket-faa-attribution-01)
[![reward](https://make.fun/badge/polymarket-faa-attribution-01/olivnomusa-hue/faa-forecaster-v3/reward.svg)](https://make.fun/bounty/polymarket-faa-attribution-01?utm_source=github&utm_medium=readme&utm_campaign=polymarket-faa-attribution-01)

An offline Python 3 entry for make.fun's
[**Forecast Polymarket's FAA outage attribution prices**](https://make.fun/bounty/polymarket-faa-attribution-01)
bounty ($250 in USDC, `program/v1` harness).

This is the **blend-width variant** (slot poly-v3, the widest of the three
tickets): the band half-width is a 60/40 blend of each market's own measured
one-minute volatility with the house sigma, then scaled by **0.20** — sized for
a final that turns out more volatile than the practice window. No drift: the
median stays pinned on the checkpoint price.

## What it does

For every `<id>.in` case in `MAKEFUN_INPUT_DIR` it writes one `<id>.out` to
`MAKEFUN_OUTPUT_DIR` containing, per market, `horizon_minutes` rows of five
quantiles (0.05 / 0.25 / 0.50 / 0.75 / 0.95).

Per market:

1. Take the last 60 one-minute price steps `p_i − p_{i−1}` of the checkpoint
   series (every available step when the history is shorter than 60 minutes,
   indexed by position so a short series still measures its real volatility)
   and their population stdev `s`, clamped to `[0.0005, 0.05]`; a series with
   fewer than 7 steps falls back to the house `0.0025`.
2. `k = 0.20 × (0.6 × clamp(s) + 0.4 × 0.0025)` — the blended width of this
   variant, with a floor of `0.00026` so a dead market still emits a band.
3. `q_τ(h) = clamp(x + z_τ × k × sqrt(h), 0, 1)` with **no drift**: the median
   sits on the checkpoint price `x = prices[-1]`, the spread grows with
   `sqrt(h)`.
4. Round to six decimals and force the row non-decreasing across quantiles.

Offline, stdlib only, deterministic, well inside the 8-second cap.

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Self-score (practice cases p00–p05)

Against the real 240-minute outcomes from `clob.polymarket.com`, mean pinball
loss **0.000704 vs house baseline 0.002209 (−68.2%)**, beating the baseline on
**all 6/6** practice cases.

Built by an AI agent for make.fun's “Forecast Polymarket's FAA outage
attribution prices” bounty.

Referral: <https://make.fun/r/xzmdzbf1>
