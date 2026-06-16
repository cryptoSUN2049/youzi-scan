#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pattern mining: real backtest of hot-money entry archetypes over the watchlist.

For every stock-day in a lookback window we label the setup the way a youzi trader sees it
(limit-up / breakout / halfway / dip / ambush), then measure forward close-to-close returns at
T+1 / T+3 / T+5. We cluster by (setup) and (setup × sector) and compute win-rate + avg return +
sample count — i.e. which patterns actually paid recently, and over which holding horizon.

Assumptions (stated honestly):
  - Entry = close of the signal day; exit = close of T+N. (A realistic proxy; real limit-up
    boards can't be bought at close — treat 打板 numbers as the board's follow-through strength.)
  - Universe = the watchlist only (patterns *in the stocks you track*, not the whole market).

Usage: python3 pattern_mine.py --symbols ../data/watchlist.csv --end 2026-06-16 --days 80
Output: /tmp/patterns.json  (+ printed summary)
"""
import os, sys, csv, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_client as mc
import helpers as hp

THEME_ZH = None  # filled from report.L if available


def label_setup(c, v, i):
    """Label the setup at index i given close[] c and volume[] v. Returns key or None."""
    if i < 20 or i >= len(c):
        return None
    cur = c[i]
    prev = c[i - 1]
    day_ret = (cur / prev - 1) * 100 if prev else 0
    ma5 = sum(c[i - 5:i]) / 5
    ma10 = sum(c[i - 10:i]) / 10
    ma20 = sum(c[i - 20:i]) / 20
    v5 = sum(v[i - 5:i]) / 5 if i >= 5 and sum(v[i - 5:i]) else 0
    vr = (v[i] / v5) if v5 else 1.0
    win = c[max(0, i - 20):i + 1]
    lo, hi = min(win), max(win)
    pos = (cur - lo) / (hi - lo) * 100 if hi > lo else 50  # 0=low,100=high of 20d range
    bull = ma5 >= ma10 >= ma20
    # archetypes (priority)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.csv"))
    ap.add_argument("--end", default="2026-06-16")
    ap.add_argument("--days", type=int, default=80, help="calendar-day lookback window")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    import datetime
    start = (datetime.date.fromisoformat(a.end) - datetime.timedelta(days=a.days)).isoformat()

    rows = list(csv.DictReader(open(a.symbols)))
    if a.limit:
        rows = rows[:a.limit]
    samples = []  # each: {setup, theme, t1, t3, t5}
    for idx, r in enumerate(rows):
        code = r["code"]; theme = r.get("theme", "Other")
        hist = mc.history(code, start, a.end)
        if isinstance(hist, dict):
            hist = hist.get("results", [])
        if not hist or len(hist) < 30:
            continue
        hist = sorted(hist, key=lambda x: x["date"])
        c = [x["close"] for x in hist]
        v = [x.get("volume") or 0 for x in hist]
        for i in range(20, len(c) - 5):  # need 5 forward days
            s = label_setup(c, v, i)
            if not s:
                continue
            base = c[i]
            samples.append({
                "setup": s, "theme": theme,
                "t1": (c[i + 1] / base - 1) * 100,
                "t3": (c[i + 3] / base - 1) * 100,
                "t5": (c[i + 5] / base - 1) * 100,
            })
        if idx % 20 == 0:
            print(f"  mined {idx}/{len(rows)} ({len(samples)} samples)", file=sys.stderr)

    def agg(group):
        out = {}
        for key, items in group.items():
            n = len(items)
            row = {"n": n}
            for h in ("t1", "t3", "t5"):
                rets = [x[h] for x in items]
                wins = sum(1 for x in rets if x > 0)
                row[h] = {"win": round(wins / n * 100), "avg": round(sum(rets) / n, 2),
                          "med": round(sorted(rets)[n // 2], 2)}
            out[key] = row
        return out

    by_setup = {}
    by_combo = {}
    for x in samples:
        by_setup.setdefault(x["setup"], []).append(x)
        by_combo.setdefault((x["setup"], x["theme"]), []).append(x)
    setup_stats = agg(by_setup)
    combo_stats = {f"{k[0]} @ {k[1]}": v for k, v in agg({k: v for k, v in by_combo.items() if len(v) >= 8}).items()}

    result = {"end": a.end, "window_days": a.days, "n_stocks": len(rows), "n_samples": len(samples),
              "by_setup": setup_stats, "by_combo": combo_stats}
    json.dump(result, open("/tmp/patterns.json", "w"), ensure_ascii=False, indent=1)

    print(f"\n=== 样本 {len(samples)} 条 | {len(rows)} 只 | 窗口 {a.days} 天 ===")
    print(f"{'入场模式':<18}{'样本':>5}{'T+1胜率/均值':>16}{'T+3胜率/均值':>16}{'T+5胜率/均值':>16}")
    for s, st in sorted(setup_stats.items(), key=lambda kv: -kv[1]['t3']['win']):
        print(f"  {s:<16}{st['n']:>5}"
              f"{st['t1']['win']:>6}%/{st['t1']['avg']:>+6.1f}%"
              f"{st['t3']['win']:>6}%/{st['t3']['avg']:>+6.1f}%"
              f"{st['t5']['win']:>6}%/{st['t5']['avg']:>+6.1f}%")
    print("\n=== 最佳「模式×板块」(样本≥8, 按T+3胜率) TOP12 ===")
    for k, st in sorted(combo_stats.items(), key=lambda kv: -kv[1]['t3']['win'])[:12]:
        print(f"  {k:<34} n={st['n']:>3} T+1 {st['t1']['win']}%/{st['t1']['avg']:+.1f}  T+3 {st['t3']['win']}%/{st['t3']['avg']:+.1f}  T+5 {st['t5']['win']}%/{st['t5']['avg']:+.1f}")


if __name__ == "__main__":
    main()
