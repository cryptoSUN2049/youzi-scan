# youzi-scan

**A hot-money (游资) lens for A-share stock scanning.** Score any basket of Chinese
A-shares the way a *youzi* (游资 — "hot money") day-trader actually decides: by
**sentiment cycle → sector → individual volume/price**, and bucket every name into one
of five tactics — **Ambush / Dip / Halfway / Limit-chase / Avoid** — in a single
self-contained HTML report.

> 游资 ("hot money") is the Chinese term for nimble speculative capital that drives
> A-share momentum. This tool encodes how they read the tape: **volume first**,
> sentiment as the gate, and the real edge in the *mispricing* — names where smart
> money is quietly accumulating at a low position before the rally starts.

![sample](examples/sample-report.html) — open `examples/sample-report.html` in a browser for a full demo.

---

## Why this exists

Most retail scans ask *"did it go up?"*. A hot-money trader asks *"is there anyone left
to relay it?"*. The whole tool is built on one belief and one decision order:

```
Sentiment cycle (the gate)  →  Sector (the direction)  →  Individual volume/price (the trigger)
   can we even trade?            which way?                 which name, and how?
```

- **Sentiment is the gate.** A main rally is a self-reinforcing money effect: yesterday's
  limit-up buyers profited, so more people dare to chase today. That feedback loop only
  holds in an *offensive* cycle. In an *ebb*, even a great setup just gets sold into.
- **The edge is the mispricing.** Same thesis, same hot sector — but the name where
  institutions are still quietly accumulating *at a low position* and it hasn't run yet.

## The 4-dimension indicator system

| Dimension | Indicators | tushare source |
|---|---|---|
| ① **Liquidity · turnover** (the core) | volume-ratio, turnover, 5d-avg turnover, amplitude, volume-price health | `equity_fundamental_backup_daily` |
| ② **Position · pattern** | cumulative main-rally %, distance from 80-day top, MA bull alignment, MA10/20 deviation, BOLL | `equity_fundamental_stock_factor` + history |
| ③ **Capital · institutions** | net institutional inflow (1d/5d), accumulation streak, order-book strength, dragon-tiger hot-money seats | `equity_moneyflow_individual` + `get_dragon_tiger_board` |
| ④ **Timing · technicals** | MACD, KDJ, RSI | `equity_fundamental_stock_factor` |

## The 5 tactics (decision tree)

Evaluated top-to-bottom in `scripts/scan.py::classify`:

| Tactic | When | Meaning |
|---|---|---|
| ⛔ **Avoid** | high + huge turnover / >150% parabolic / high & stalling | distribution / overextended |
| 🔴 **Limit-chase** | limit-up + not high + turnover not overheated | board the limit-up |
| 🟡 **Halfway** | heavy volume + active turnover (3-15%) + +2~7% + strong attack | board it mid-way before the limit |
| 🔵 **Dip** | bull alignment + low-vol pullback to MA10 + MACD above water | right-side dip-buy |
| 🟢 **Ambush** | low position + dry volume + sustained institutional accumulation | **left-side ambush — the top pick** |
| ⚠️ High / △ Watch | high relay / unclear | don't chase / track |

Each name also gets a **0–100 score** = capital 30 + position 22 + volume-price 20 +
MA 12 + MACD 8 + hot-money 8.

## Report sections

1. **Market sentiment cycle** — last 6 sessions of limit-ups / broken boards / seal rate /
   top consecutive boards, with an auto-generated cycle read (offensive / rebound / ebb).
2. **The indicator system** — what's pulled and how it's judged.
3–6. **Tactic pools** — Ambush / Dip / Halfway / Limit-chase, each as scored cards.
7. **Full table** — every name across all four dimensions, grouped by sub-sector.
8. **Risk discipline.**

---

## Setup

No third-party dependencies — pure Python standard library (3.8+). Data is pulled over
HTTP from a **DataHub MCP gateway** that wraps [tushare](https://tushare.pro/).

```bash
git clone <this-repo>
cd youzi-scan
cp .env.example .env          # then put your token in .env (never commit it)
```

`.env`:
```
DATAHUB_MCP_TOKEN=Bearer your_token_here
# DATAHUB_MCP_URL=...         # optional; a default endpoint is set in mcp_client.py
```

## Usage

```bash
cd scripts
python3 scan.py \
    --symbols symbols_ai_compute.csv \   # code,name,theme (one per line)
    --date   2026-06-16 \                # anchor trading day; non-trading days auto-adjust
    --out    ../reports \
    --title  "AI Compute Chain" \
    [--limit 5]                          # only the first N names — a 30s smoke test
```

Output: `<out>/<title>-youzi-scan-<date>.html`

Scan a different universe: make a new `symbols_*.csv` (columns `code,name,theme`, codes
with a `.SH`/`.SZ` suffix) and pass it to `--symbols`. The bundled
`symbols_ai_compute.csv` is a 120-name AI-compute supply chain.

## How it stays honest (robustness)

- **Dynamic date windows** — every pull window is derived from `--date`; change the date
  and nothing shifts out of alignment.
- **Trading-day adaptation** — a weekend/holiday `--date` auto-falls-back to the last
  trading day.
- **Sentiment with sanity-check + cache** — the limit-list endpoint is flaky and empty
  after close; when it can't serve real data, the report falls back to a cached value and
  **honestly labels it "cached (asof X)"** instead of showing garbage.
- **Coverage stats** — the header shows how many names got each field, and lists any
  missing ones, so you know exactly how much of the report is real.
- **Freshness labels** — price vs. derived-indicator anchor dates are shown automatically.

---

## Important notes & gotchas

This is a **T+1 / after-close** tool — best run **after market close (~18:00 CST)** when
the EOD batch has landed all derived indicators (turnover, vol-ratio, MACD, money flow,
dragon-tiger). Intraday it only has price; the derived fields lag.

The data plumbing has a few sharp edges (all handled in code, documented in comments):

- The MCP session is **single-threaded** — calls must be **serial**, never parallel.
- A-shares require `provider="tushare"`.
- `change_percent` is a fraction (×100).
- `backup_daily`'s intraday row is a 0-stub — take the latest row with `turn_over > 0`.
- `quote.float_share` is dirty — never derive turnover from it; use `backup_daily`.

## Disclaimer

This is a **structured capital/volume/technical scan for research and education only**.
It is **not investment advice**. All indicators are computed by the script from tushare
data and may contain errors; verify against the raw tape before any decision. Trading is
risky and you are solely responsible for your own decisions.

## License

MIT — see [LICENSE](LICENSE).
