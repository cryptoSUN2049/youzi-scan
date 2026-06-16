#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pattern mining: real backtest of hot-money entry archetypes over the watchlist.

For every stock-day in the lookback window we label the setup the way a youzi trader sees it
(limit-up / breakout / halfway / dip / ambush) — that labelled stock-day is ONE sample. We then
measure forward close-to-close returns at several holding horizons (T+1/3/5/10/20/60) and cluster by
setup, setup×sector, and setup×sector×stock — i.e. which patterns actually paid recently, over which
holding horizon, and which specific names drove it.

Sample = (stock, day, setup). win-rate = % of samples with positive forward return at that horizon.
e.g. "低吸@CCL n=29" = the CCL names fired the MA10-pullback setup 29 times in the window.

Assumptions (honest):
  - Entry = close of the signal day; exit = close of T+N (a proxy; limit-up boards can't be bought at
    close, so 打板 numbers = the board's follow-through strength).
  - Universe = the watchlist only. Longer window (~200 cal days) so the 3-month (T+60) horizon has samples.

Usage: python3 pattern_mine.py --symbols ../data/watchlist.csv --end 2026-06-16 --days 200
Output: /tmp/patterns.json (+ /tmp/patterns_raw.json raw samples, so re-aggregation needs no re-pull)
"""
import os, sys, csv, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_client as mc

HORIZONS = [("t1", 1), ("t3", 3), ("t5", 5), ("t10", 10), ("t20", 20), ("t60", 60)]
HMAX = 60


def label_setup(c, v, i):
    """Label the setup at index i. Returns key or None."""
    if i < 20 or i >= len(c):
        return None
    cur = c[i]; prev = c[i - 1]
    day_ret = (cur / prev - 1) * 100 if prev else 0
    ma5 = sum(c[i - 5:i]) / 5; ma10 = sum(c[i - 10:i]) / 10; ma20 = sum(c[i - 20:i]) / 20
    v5 = sum(v[i - 5:i]) / 5 if i >= 5 and sum(v[i - 5:i]) else 0
    vr = (v[i] / v5) if v5 else 1.0
    win = c[max(0, i - 20):i + 1]; lo, hi = min(win), max(win)
    pos = (cur - lo) / (hi - lo) * 100 if hi > lo else 50
    bull = ma5 >= ma10 >= ma20
    if day_ret >= 9.5:
        return "打板/涨停"
    if cur >= hi and day_ret > 2:
        return "突破新高"
    if 2 <= day_ret <= 9 and vr >= 1.8:
        return "半路/放量"
    if bull and abs(cur / ma10 - 1) <= 0.025 and day_ret <= 1:
        return "低吸/回踩MA10"
    if pos <= 35 and vr <= 0.9:
        return "潜伏/低位缩量"
    return None


def agg(items):
    """Aggregate a list of samples into per-horizon win/avg (only over samples that have the horizon)."""
    row = {"n": len(items)}
    for hk, _ in HORIZONS:
        rets = [x[hk] for x in items if x.get(hk) is not None]
        if rets:
            wins = sum(1 for r in rets if r > 0)
            row[hk] = {"n": len(rets), "win": round(wins / len(rets) * 100), "avg": round(sum(rets) / len(rets), 1)}
        else:
            row[hk] = None
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.csv"))
    ap.add_argument("--end", default="2026-06-16")
    ap.add_argument("--days", type=int, default=200, help="calendar-day lookback (200 ~ 135 trading days)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    import datetime
    start = (datetime.date.fromisoformat(a.end) - datetime.timedelta(days=a.days)).isoformat()

    rows = list(csv.DictReader(open(a.symbols)))
    if a.limit:
        rows = rows[:a.limit]
    samples = []
    for idx, r in enumerate(rows):
        code = r["code"]; name = r.get("name", code); theme = r.get("theme", "Other")
        hist = mc.history(code, start, a.end)
        if isinstance(hist, dict):
            hist = hist.get("results", [])
        if not hist or len(hist) < 30:
            continue
        hist = sorted(hist, key=lambda x: x["date"])
        c = [x["close"] for x in hist]; v = [x.get("volume") or 0 for x in hist]
        for i in range(20, len(c) - 1):  # need at least T+1
            s = label_setup(c, v, i)
            if not s:
                continue
            base = c[i]
            smp = {"setup": s, "theme": theme, "code": code, "name": name}
            for hk, h in HORIZONS:
                smp[hk] = round((c[i + h] / base - 1) * 100, 2) if i + h < len(c) else None
            samples.append(smp)
        if idx % 20 == 0:
            print(f"  mined {idx}/{len(rows)} ({len(samples)} samples)", file=sys.stderr)

    json.dump(samples, open("/tmp/patterns_raw.json", "w"), ensure_ascii=False)

    by_setup, by_combo, by_triple = {}, {}, {}
    for x in samples:
        by_setup.setdefault(x["setup"], []).append(x)
        by_combo.setdefault((x["setup"], x["theme"]), []).append(x)
        by_triple.setdefault((x["setup"], x["theme"], x["code"], x["name"]), []).append(x)
    setup_stats = {k: agg(v) for k, v in by_setup.items()}
    combo_items = {k: v for k, v in by_combo.items() if len(v) >= 8}
    combo_stats = {f"{k[0]} @ {k[1]}": agg(v) for k, v in combo_items.items()}

    # best 模式×板块×股票 combos: top combos by T+3 win, each with its best contributing stocks
    triple_stats = {k: agg(v) for k, v in by_triple.items() if len(v) >= 2}
    best_combos = []
    for (setup, theme), items in sorted(combo_items.items(), key=lambda kv: -(agg(kv[1])["t3"] or {"win": 0})["win"])[:10]:
        cs = agg(items)
        stocks = []
        for (s2, th2, code, name), tv in sorted(
                ((k, v) for k, v in triple_stats.items() if k[0] == setup and k[1] == theme),
                key=lambda kv: (-(kv[1]["t3"] or {"win": 0})["win"], -kv[1]["n"])):
            t3 = tv.get("t3") or {}
            stocks.append({"code": code, "name": name, "n": tv["n"], "t3_win": t3.get("win"), "t3_avg": t3.get("avg")})
            if len(stocks) >= 4:
                break
        best_combos.append({"setup": setup, "theme": theme, "n": cs["n"],
                            **{hk: cs[hk] for hk, _ in HORIZONS}, "stocks": stocks})

    result = {"end": a.end, "window_days": a.days, "n_stocks": len(rows), "n_samples": len(samples),
              "horizons": [hk for hk, _ in HORIZONS],
              "by_setup": setup_stats, "by_combo": combo_stats, "best_combos": best_combos}
    json.dump(result, open("/tmp/patterns.json", "w"), ensure_ascii=False, indent=1)

    print(f"\n=== {len(samples)} 样本 | {len(rows)} 只 | 窗口 {a.days} 天 ===")
    hdr = "".join(f"{hk.upper():>11}" for hk, _ in HORIZONS)
    print(f"{'入场模式':<16}{'样本':>5}{hdr}")
    for s, st in sorted(setup_stats.items(), key=lambda kv: -((kv[1]['t3'] or {'win': 0})['win'])):
        line = f"  {s:<14}{st['n']:>5}"
        for hk, _ in HORIZONS:
            h = st.get(hk)
            line += f"{(str(h['win'])+'%') if h else '—':>6}{('/'+format(h['avg'],'+.0f')) if h else '':>5}"
        print(line)
    print("\n=== 最佳「模式×板块×股票」TOP10 (按T+3胜率) ===")
    for bc in best_combos:
        t3 = bc.get("t3") or {}; t5 = bc.get("t5") or {}
        sts = " ".join(f"{s['name']}({s['t3_win']}%)" for s in bc["stocks"][:3])
        print(f"  {bc['setup']}@{bc['theme'][:14]} n={bc['n']} T+3 {t3.get('win')}%/{t3.get('avg')} | 票: {sts}")


if __name__ == "__main__":
    main()
