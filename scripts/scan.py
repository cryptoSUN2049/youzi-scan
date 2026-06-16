#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
youzi-scan orchestrator: pull -> repair intraday stubs -> score by hot-money tactics
-> render a single-file HTML report.

Usage:
  python3 scan.py --symbols symbols_ai_compute.csv --date 2026-06-16 \
          --out ./reports --title "AI Compute Chain" [--limit 5]

Output: <out>/<title>-youzi-scan-<date>.html

Hard-won notes (already handled here):
  - MCP session is single-threaded -> everything is SERIAL, never parallel.
  - A-shares require provider="tushare".
  - change_percent is a fraction (x100).
  - backup_daily's intraday row is a 0-stub -> take the latest row with turn_over>0.
  - quote.float_share is dirty -> never use it to derive turnover; use backup_daily.
  - limit_list gateway params are unstable / empty after close -> sentiment goes through
    helpers.compute_sentiment (sanity check + cache).
  - Derived data (turnover/vol-ratio/MACD/flow/dragon-tiger) only fully lands after the
    EOD batch (~18:00 CST). Run after close for a complete report.
"""
import sys
import os
import json
import csv
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_client as mc
import helpers as h


def f(x):
    try:
        return float(x)
    except Exception:
        return None


# ---------------- 1. data pull (dynamic windows + coverage stats + freshness) ----------------
def pull_all(symbols, date, win, limit=None):
    syms = symbols[:limit] if limit else symbols
    rows = []
    stats = {"total": len(syms), "price": 0, "cum80": 0, "net5": 0, "turn": 0, "macd": 0, "failed": []}
    bd_dates, mf_dates = [], []
    for i, (code, name, theme) in enumerate(syms):
        r = {"code": code, "name": name, "theme": theme}
        # latest / close quote
        q = mc.quote(code)
        if isinstance(q, list) and q:
            q = q[0]
        if isinstance(q, dict) and q.get("last_price") is not None:
            r["price"] = q.get("last_price")
            cp = q.get("change_percent")
            r["chg"] = round(cp * 100, 2) if cp is not None else None
            r["amount"] = q.get("amount")
            stats["price"] += 1
        # main-rally position (dynamic 80-trading-day window)
        hist = mc.history(code, win["hist"], date)
        if isinstance(hist, dict):
            hist = hist.get("results", [])
        if hist:
            hist = sorted(hist, key=lambda x: x["date"])
            c = [x["close"] for x in hist]
            base = sum(c[:10]) / 10
            hi = max(c)
            cur = c[-1]
            r["cum80"] = round((cur / base - 1) * 100)
            r["dtop"] = round((cur / hi - 1) * 100, 1)
            r["d5"] = round((cur / c[-6] - 1) * 100, 1) if len(c) >= 6 else 0
            stats["cum80"] += 1
        # institutional money flow
        mf = mc.moneyflow(code, win["moneyflow"], date)
        if isinstance(mf, dict):
            mf = mf.get("results", [])
        if mf:
            mf = sorted(mf, key=lambda x: x["date"])
            mf_dates.append(mf[-1].get("date"))
            r["net1"] = mf[-1].get("net_mf_amount")
            r["net5"] = sum((x.get("net_mf_amount") or 0) for x in mf[-5:])
            streak = 0
            for x in reversed(mf):
                if (x.get("net_mf_amount") or 0) > 0:
                    streak += 1
                else:
                    break
            r["streak"] = streak
            stats["net5"] += 1
        # volume ratio / turnover / amplitude / order-book strength (latest valid row, turn>0)
        bd = mc.call("equity_fundamental_backup_daily",
                     {"symbol": code, "start_date": win["backup"], "end_date": date, "provider": "tushare"})
        if isinstance(bd, dict):
            bd = bd.get("results", [])
        valid = [x for x in (bd or []) if f(x.get("turn_over")) not in (None, 0.0)]
        if valid:
            valid = sorted(valid, key=lambda x: x.get("trade_date", x.get("date", "")))
            last = valid[-1]
            bd_dates.append(last.get("trade_date") or last.get("date"))
            r["vol_ratio"] = f(last.get("vol_ratio"))
            r["turn"] = f(last.get("turn_over"))
            r["swing"] = f(last.get("swing"))
            r["float_mv"] = f(last.get("float_mv"))
            r["attack"] = f(last.get("attack"))
            r["strength"] = f(last.get("strength"))
            turns = [f(x.get("turn_over")) for x in valid if f(x.get("turn_over")) is not None]
            r["turn5"] = round(sum(turns[-5:]) / len(turns[-5:]), 2) if turns else None
            stats["turn"] += 1
        # technical factors + moving averages
        sfac = mc.call("equity_fundamental_stock_factor",
                       {"symbol": code, "start_date": win["factor"], "end_date": date, "provider": "tushare"})
        if isinstance(sfac, dict):
            sfac = sfac.get("results", [])
        if sfac:
            sfac = sorted(sfac, key=lambda x: x.get("date", ""))
            last = sfac[-1]
            r["macd"] = f(last.get("macd"))
            r["macd_dif"] = f(last.get("macd_dif"))
            r["macd_dea"] = f(last.get("macd_dea"))
            r["kdj_j"] = f(last.get("kdj_j"))
            r["rsi6"] = f(last.get("rsi_6"))
            r["boll_up"] = f(last.get("boll_upper"))
            r["boll_mid"] = f(last.get("boll_mid"))
            closes = [f(x.get("close_qfq") or x.get("close")) for x in sfac if f(x.get("close_qfq") or x.get("close"))]
            if len(closes) >= 20:
                cur = closes[-1]
                ma5 = sum(closes[-5:]) / 5
                ma10 = sum(closes[-10:]) / 10
                ma20 = sum(closes[-20:]) / 20
                r["ma_bull"] = 1 if (ma5 >= ma10 >= ma20) else 0
                r["above_ma10"] = round((cur / ma10 - 1) * 100, 1)
                r["above_ma20"] = round((cur / ma20 - 1) * 100, 1)
                if r.get("boll_up") and r["boll_up"] > r["boll_mid"]:
                    r["boll_pos"] = round((cur - r["boll_mid"]) / (r["boll_up"] - r["boll_mid"]) * 100, 0)
            if r.get("macd") is not None:
                stats["macd"] += 1
        if r.get("price") is None and r.get("turn") is None:
            stats["failed"].append(code)
        rows.append(r)
        if i % 20 == 0:
            print(f"  pulled {i}/{len(syms)}", file=sys.stderr)

    def _mode(xs):
        from collections import Counter
        return Counter(xs).most_common(1)[0][0] if xs else None

    freshness = {"price_date": date, "vp_date": _mode(bd_dates) or "not-ready", "mf_date": _mode(mf_dates) or "not-ready"}
    return rows, stats, freshness


# ---------------- 2. dragon-tiger (top-list) ----------------
def pull_dragon(date):
    GENERIC = {"量化打板", "机构专用", "机构", "深股通专用", "沪股通专用", ""}
    dtmap = {}
    blob = mc.call("get_dragon_tiger_board", {"date": date})
    r = (blob or {}).get("results", {}) if blob else {}
    for s in (r.get("sections", []) if isinstance(r, dict) else []):
        rs = [x for x in s.get("data", []) if "_summary" not in x]
        if s.get("title") == "标的层":  # stock layer
            for x in rs:
                c = x.get("code")
                if c:
                    dtmap.setdefault(c, {"hm": []})
        if s.get("title") == "游资席位":  # hot-money seats
            for x in rs:
                c = x.get("ts_code")
                nm = x.get("hm_name", "")
                if c and nm and nm not in GENERIC:
                    dtmap.setdefault(c, {"hm": []})["hm"].append(nm)
    return dtmap


# ---------------- 3. volume-price health + tactic decision tree ----------------
def vol_price_health(chg, vr):
    if chg is None or vr is None:
        return "-"
    if chg > 1 and vr > 1.5:
        return "Rise+Vol(attack)"
    if chg > 1 and vr < 0.8:
        return "Rise+LowVol(divergence)"
    if chg < -1 and vr < 0.8:
        return "Pullback+LowVol(healthy)"
    if chg < -1 and vr > 1.5:
        return "Drop+Vol(distribution)"
    if abs(chg) <= 1 and vr < 0.9:
        return "Flat+LowVol(coiling)"
    return "Neutral"


def classify(r):
    chg = r.get("chg"); cum = r.get("cum80"); dtop = r.get("dtop")
    vr = r.get("vol_ratio"); turn = r.get("turn"); net5 = r.get("net5"); streak = r.get("streak") or 0
    bull = r.get("ma_bull"); am10 = r.get("above_ma10"); macd = r.get("macd")
    difdea = (r.get("macd_dif") or 0) - (r.get("macd_dea") or 0); attack = r.get("attack"); hm = r.get("hm") or []
    c = chg or 0; cu = cum if cum is not None else 50; dt_ = dtop if dtop is not None else -10
    high = dt_ > -4 or cu > 150
    low = dt_ < -12 and cu < 70
    quiet = (vr is not None and vr < 0.9)
    big = (vr is not None and vr > 1.5)
    huge = (vr is not None and vr > 2.5) or (turn is not None and turn > 20)
    hot_turn = (turn is not None and turn > 20)
    fund_in = (net5 is not None and net5 > 0 and streak >= 2)
    macd_up = (macd is not None and macd > 0) or difdea > 0
    # score 0-100
    score = 0
    score += 30 if fund_in else (15 if (net5 or 0) > 0 else 0)
    score += 22 if low else (12 if not high else 0)
    vph = vol_price_health(chg, vr)
    score += 20 if ("attack" in vph or "coiling" in vph or "healthy" in vph) else (2 if "divergence" in vph or "distribution" in vph else 10)
    if bull:
        score += 12
    if macd_up:
        score += 8
    if hm:
        score += 8
    score = min(100, score)
    # tactic (priority order)
    if high and (huge or hot_turn):
        return "⛔ Avoid", score, "High + huge turnover (distribution risk)", vph
    if cu > 150:
        return "⛔ Avoid", score, "Parabolic end (>150% rally, overextended)", vph
    if high and c < 2:
        return "⛔ Avoid", score, "High + stalling (relay capital fading)", vph
    if c >= 9.7:
        if not high and not hot_turn:
            return "🔴 Limit-chase", score, "Limit-up + not high + turnover not overheated" + (" + hot-money" if hm else ""), vph
        return "⛔ Avoid", score, "High limit-up (chasing risk)", vph
    if big and turn and 3 <= turn <= 15 and 2 <= c <= 7 and (attack is None or attack > 0) and not high:
        return "🟡 Halfway", score, "Volume breakout + active turnover + strong attack", vph
    if bull and quiet and am10 is not None and -3.5 <= am10 <= 3 and macd_up and not high:
        return "🔵 Dip", score, "Uptrend pullback to MA10 on low vol + MACD above water", vph
    if low and (quiet or (vr is not None and vr < 1.3)) and fund_in:
        return "🟢 Ambush", score, "Low position + shrinking vol + sustained institutional accumulation", vph
    if low and fund_in:
        return "🟢 Ambush", score, "Low position + net institutional inflow", vph
    if high:
        return "⚠️ High", score, "High position relay (don't chase)", vph
    return "△ Watch", score, "Volume/capital signals unclear", vph


# ---------------- 4. main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=os.path.join(os.path.dirname(__file__), "symbols_ai_compute.csv"))
    ap.add_argument("--date", default="2026-06-16")
    ap.add_argument("--out", default="./reports")
    ap.add_argument("--title", default="AI Compute Chain")
    ap.add_argument("--limit", type=int, default=None, help="only the first N symbols (fast smoke test)")
    a = ap.parse_args()

    # adapt non-trading days to the most recent trading day
    date = h.resolve_trading_day(a.date)
    if date != a.date:
        print(f"NB: {a.date} is not a trading day; using {date}", file=sys.stderr)
    win = h.windows(date)  # dynamic pull windows

    symbols = [(r["code"], r.get("name", ""), r.get("theme", "Other")) for r in csv.DictReader(open(a.symbols))]
    print(f"{len(symbols)} symbols | anchor {date} | windows {win}", file=sys.stderr)

    rows, stats, freshness = pull_all(symbols, date, win, limit=a.limit)
    dtmap = pull_dragon(date)
    for r in rows:
        r["hm"] = list(dict.fromkeys(dtmap.get(r["code"], {}).get("hm", [])))
        tac, score, reason, vph = classify(r)
        r["tactic"], r["score"], r["reason"], r["vph"] = tac, score, reason, vph

    sent_rows, sent_asof, sent_fresh = h.compute_sentiment(date)

    from collections import Counter
    print("tactics:", dict(Counter(r["tactic"] for r in rows)), file=sys.stderr)
    print(f"coverage: price{stats['price']} pos{stats['cum80']} flow{stats['net5']} vp{stats['turn']} tech{stats['macd']} /{stats['total']}", file=sys.stderr)
    print(f"freshness: price={freshness['price_date']} vp={freshness['vp_date']} flow={freshness['mf_date']} | sentiment asof={sent_asof} fresh={sent_fresh}", file=sys.stderr)

    import report
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{a.title}-youzi-scan-{date}.html")
    report.render(rows, out_file, a.title, date,
                  sentiment=sent_rows, sent_asof=sent_asof, sent_fresh=sent_fresh,
                  stats=stats, freshness=freshness)
    print(f"OK report: {out_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
