---
name: youzi-scan
description: Hot-money (游资) A-share scanner + market-intelligence report (T+1 盘后版). Scores a basket of Chinese A-shares the way a youzi (hot-money) day-trader decides — sentiment cycle × individual volume/capital × chart pattern — buckets each into Ambush/Dip/Halfway/Limit-chase/Avoid, runs a REAL multi-horizon (T+1/3/5/10/20/60) win-rate backtest, joins it with today's setups to surface NEXT-BATCH candidates, pulls 大盘/外盘/全球新闻 (datahub + web search), and renders a conclusion-first single-file HTML report (the conclusion is written by the agent from the real data, not a template). Use whenever the user wants: a 游资/hot-money scan, 主升浪选股, 复盘/盘后做功课, ambush/dip/halfway/limit-chase picks, volume/turnover/capital health check, 龙虎榜 seats, best-pattern backtest, "找下一批" next-batch candidates, market intelligence (大盘/外盘/宏观/新闻), or "跑游资报告". Maintains a watchlist pool. T+1/after-close tool (derived data lands ~18:00 CST). Data via DataHub(tushare) MCP gateway + Claude-Code web search.
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

## ★ STANDARD OPERATING MANUAL — full market-intelligence report (6 steps)

This is the full pipeline the agent runs for a complete report. Its architecture is the whole
point: **the scripts produce DETERMINISTIC data (datahub/backtest, never fabricated); the agent
(Claude) layers SUBJECTIVE analysis on top.** A pure-numbers report misleads (see step 5); the
agent's judgment is what catches the traps. Web search is a Claude-Code tool the Python can't
call — so the macro/news step is done by the agent. That is how this skill "uses Claude Code's
built-in search".

Discipline (the user requires it): **commit + push BEFORE each test**; run smoke (`--limit`) then
full; deterministic data only (no hallucinated numbers); reusable; the conclusion is the agent's,
not a template. The gateway can be slow (~2s/call) — a full 141-stock pull/backtest can take ~20
min; run in the harness background so you're notified, never block.

```
cd scripts                       # everything runs from scripts/ ; .env holds the token

# STEP 1 · POOL (deterministic) — refresh the universe if new research came in
python3 build_pool.py <new_doc.html> --src-name "X-YYYY-MM-DD" --src-date YYYY-MM-DD
#   data/watchlist.csv : code,name,theme,tier,tags,sources,added,active (dedupe, union, max-set)

# STEP 2 · BACKTEST (deterministic) — real forward-return win-rates, multi-horizon + per-stock
python3 pattern_mine.py --symbols ../data/watchlist.csv --end <date> --days 200
#   -> /tmp/patterns.json : by_setup / by_combo / best_combos(模式×板块×个股) over T+1/3/5/10/20/60
#   -> /tmp/patterns_raw.json : raw samples (re-aggregate later with NO re-pull)

# STEP 3 · MACRO + NEWS (deterministic data + AGENT search) — write /tmp/macro.json:
#   - A-share 八大指数: datahub daily_market_digest (consistent with the tape)
#   - 板块资金流: datahub get_sector_moneyflow_rank   (surfaces rotation, e.g. money leaving the pool)
#   - 外盘 / 全球新闻 / 公告: AGENT runs WebSearch (US AI/semis, SOX, Fed/FOMC, geopolitics)
#   - 美股AI/科技核心个股(英伟达/AMD/博通/台积电/巨头): python3 us_basket.py (datahub provider=fmp,
#     deterministic) -> injects overseas.ai_stocks into /tmp/macro.json (a chips row, tracked每次)
#   funnel schema: {"date","global_news":[{tag,t,w}],"overseas":{idx,ai,read},
#                   "ashare":{idx,northbound,read},"sector_flow":[{name,pct,net}],"sector_read","read"}

# STEP 4 · SCAN (deterministic) — 4-D score the pool, save render context
#   OMIT --date and it AUTO-PICKS the anchor + run-mode from Beijing time (helpers.anchor_date_and_mode):
#     >=15:00 盘后复盘=today · <09:30 盘前=prev trading day · 09:30-15:00 盘中=today. No hard-coded date.
python3 scan.py --symbols ../data/watchlist.csv --out ../reports --title "..." \
    --macro-json /tmp/macro.json --patterns-json /tmp/patterns.json   # [--date YYYY-MM-DD to override]

# STEP 4b · PULLBACK AMBUSH (deterministic) — strong names rarely pull back to MA10; project the dip price
python3 pullback.py <date>     # reads /tmp/youzi_scored.json -> /tmp/pullback.json (MA5/MA10 dip-buy targets)
#   -> /tmp/youzi_scored.json (rows) + /tmp/youzi_ctx.json (full render context)
#   The report it writes here has a PLACEHOLDER conclusion — that's expected; step 6 injects the real one.

# STEP 5 · AGENT ANALYSIS (subjective) — read the real data, write the conclusion to /tmp/conclusion.html
#   Read /tmp/youzi_scored.json + patterns + macro, then WRITE a professional 结论先行 covering:
#     ① cycle & macro (why offense/defense)   ② backtest law (which horizon actually pays)
#     ③ historical best 模式×板块×个股          ④ NEXT-BATCH 主观研判 — the key part:
#        the report's "下一批候选" TABLE is a deterministic join (today's setup × sector vs backtest
#        win-rate). The agent must OVERRIDE it with current capital/volume: e.g. a name with a great
#        backtest win-rate but 主力净流出 / 量价背离 today is a TRAP — cut it; a name whose setup fires
#        TODAY in a high-win sector with confirming volume is the real pick. THIS override is the value.

# STEP 6 · RENDER FINAL — fold the agent conclusion in (no re-pull, uses cached ctx)
python3 render_final.py --conclusion-file /tmp/conclusion.html \
    --macro-json /tmp/macro.json --patterns-json /tmp/patterns.json --out ../reports
```

Report funnel (top-down, conclusion-first then the supporting layers):
`00 结论(agent) → 01 全球宏观 → 02 外盘美股AI → 03 A股大盘 → 04 涨停情绪 → 05 板块资金流 →
06 回测(模式定义+多窗口+模式×板块×个股) → 下一批候选(回测×今日联立) → 07 战法池(表格) →
08 TOP10 → 09 全表 → 10 风险`. Default Chinese (`--lang en` for English). Sectors shown as 东财 concepts.

## Watchlist pool

`data/watchlist.csv` is a maintainable pool (code,name,theme,tier,tags,sources,added,active).
Add a new research doc with `python3 build_pool.py <doc.html> --src-name X --src-date Y`
(dedupes by code, unions tags/sources). `scan.py --symbols data/watchlist.csv` uses it.

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
