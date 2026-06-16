---
name: youzi-scan
description: Hot-money (游资) A-share scanner. Scores a basket of Chinese A-shares the way a youzi (hot-money) day-trader decides — sentiment cycle × individual volume/capital × chart pattern — and buckets each name into Ambush / Dip / Halfway / Limit-chase / Avoid, producing a single-file HTML report. Use this whenever the user wants: a hot-money/游资 scan, main-rally (主升浪) stock selection, after-close homework, picking ambush/dip/halfway/limit-chase candidates, a volume/turnover/capital health check, dragon-tiger (龙虎榜) hot-money seats, scoring a supply-chain or watchlist from a hot-money angle, or "run the youzi report". This is a T+1 / after-close tool (volume-ratio, turnover, MACD, money flow, dragon-tiger only fully land after the EOD batch ~18:00 CST). Data flows through a DataHub (tushare) MCP gateway.
---

# youzi-scan · hot-money A-share scanner (T+1 / after-close)

Pull market data → score by hot-money tactics → render a single-file HTML report.
Full methodology, indicator system, and usage are in **[README.md](README.md)** — read it first.

## Quick start

```bash
cp .env.example .env          # then put your DATAHUB_MCP_TOKEN in .env (never commit it)
cd scripts
python3 scan.py \
    --symbols symbols_ai_compute.csv \   # code,name,theme (one per line)
    --date   2026-06-16 \                # anchor trading day; non-trading days auto-adjust
    --out    ../reports \
    --title  "AI Compute Chain" \
    [--limit 5]                          # only the first N names — ~30s smoke test
```

Output: `<out>/<title>-youzi-scan-<date>.html`

## Core logic (don't skip layers)

```
Sentiment cycle (the gate) → Sector (the direction) → Individual volume/price (the trigger)
```

Retail asks "did it go up?"; hot money asks "is there anyone left to relay it?". The edge is
the mispricing: same thesis, but institutions are still quietly accumulating at a low position
before the rally starts (the 🟢 Ambush pool).

## 4 dimensions → 5 tactics

- **Liquidity/turnover** (volume-ratio, turnover, amplitude) · **Position/pattern** (rally %, distance from top, MA, BOLL) · **Capital** (net inflow, accumulation streak, dragon-tiger seats) · **Timing** (MACD/KDJ/RSI)
- Decision tree in `scripts/scan.py::classify` → 🟢 Ambush / 🔵 Dip / 🟡 Halfway / 🔴 Limit-chase / ⚠️ High / ⛔ Avoid / △ Watch, each with a 0–100 score.

## Gotchas (handled in code — keep them if you modify)

1. The MCP session is single-threaded → **all calls serial**, never parallel.
2. A-shares require `provider="tushare"`.
3. `change_percent` is a fraction (×100).
4. `backup_daily`'s intraday row is a 0-stub → take the latest row with `turn_over > 0`.
5. `quote.float_share` is dirty → never derive turnover from it; use `backup_daily`.
6. `limit_list` gateway params are unstable / empty after close → sentiment goes through
   `helpers.compute_sentiment` (sanity-check + cache, honestly labeled).
7. Derived data (turnover/vol-ratio/MACD/flow/dragon-tiger) only fully lands after the EOD
   batch (~18:00 CST). **Run after close for a complete report.**

## Files

```
scripts/mcp_client.py   DataHub(tushare) MCP client (token via .env, serial-safe)
scripts/helpers.py      trading calendar / dynamic windows / robust sentiment
scripts/scan.py         orchestrator (entry point)
scripts/report.py       HTML renderer
scripts/symbols_ai_compute.csv   default universe (120-name AI-compute chain)
data/sentiment_cache.json        sentiment cycle cache (last-known-good + asof)
```

Not investment advice — see README disclaimer.
