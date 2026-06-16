#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
潜在低吸埋伏 (Pullback Ambush).

The static "低吸/回踩MA10" pool is often EMPTY in a strong tape — the strongest stocks rarely pull
back to MA10 (some barely touch MA5). So instead of filtering for "already at MA10", we PROJECT:
for each strong uptrend name that hasn't pulled back yet, compute the price it would need to drop to
(回踩 MA5 / MA10) to become a good low-buy. Output = a watchlist of "if it gaps down to X tomorrow,
that's the dip-buy" with target prices. Set alerts there.

Pre-filters candidates from /tmp/youzi_scored.json (uptrend + above MA10 + not parabolic) so we only
pull history for the ~40 that matter (fast even on a slow gateway).

Usage: python3 pullback.py <end_date>   ->  /tmp/pullback.json
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_client as mc

end = sys.argv[1] if len(sys.argv) > 1 else "2026-06-16"
start = (datetime.date.fromisoformat(end) - datetime.timedelta(days=30)).isoformat()
scored = json.load(open("/tmp/youzi_scored.json"))

# pre-filter: 多头排列 + 当前在MA10上方>2%(还没回踩) + 非妖股末端 + 未归回避
cands_in = [r for r in scored
            if r.get("ma_bull") == 1 and (r.get("above_ma10") or 0) > 2
            and r.get("tactic") != "avoid" and (r.get("cum80") or 0) < 150]
out = []
for i, r in enumerate(cands_in):
    hist = mc.history(r["code"], start, end)
    if isinstance(hist, dict):
        hist = hist.get("results", [])
    if not hist or len(hist) < 10:
        continue
    hist = sorted(hist, key=lambda x: x["date"])
    c = [x["close"] for x in hist]
    lo = [x.get("low", x["close"]) for x in hist]
    cur = c[-1]
    ma5 = sum(c[-5:]) / 5
    ma10 = sum(c[-10:]) / 10
    ma20 = sum(c[-20:]) / 20 if len(c) >= 20 else ma10
    if not (ma5 > ma10 > ma20):   # confirm a real multi-head uptrend
        continue
    to_ma5 = (ma5 / cur - 1) * 100
    to_ma10 = (ma10 / cur - 1) * 100
    # PANIC SCENARIO — recent strong stocks often gap/dip -5%~-8% intraday then recover; that panic = the buy.
    panic5, panic8 = round(cur * 0.95, 2), round(cur * 0.92, 2)   # price if tomorrow drops -5% / -8%
    # does a -5% / -8% panic land at a moving-average support? (best dip = panic INTO support)
    if to_ma5 >= -5:
        verdict = "✅ -5%内即触MA5(优质)"   # shallow panic reaches MA5 support
    elif to_ma5 >= -8:
        verdict = "🟡 -5~8%恐慌触MA5"
    elif to_ma10 >= -8:
        verdict = "🟡 -8%恐慌触MA10"
    else:
        verdict = "⚠️ 太强,-8%仍在MA5上方"
    # VALIDATE with history: count recent days that dipped >=4% intraday then recovered (the pattern itself)
    pr = 0
    for k in range(1, len(c)):
        if c[k - 1] and (lo[k] / c[k - 1] - 1) <= -0.04 and (c[k] / lo[k] - 1) >= 0.02:
            pr += 1
    out.append({
        "code": r["code"], "name": r["name"], "theme": r["theme"], "price": round(cur, 2),
        "ma5": round(ma5, 2), "ma10": round(ma10, 2), "to_ma5": round(to_ma5, 1), "to_ma10": round(to_ma10, 1),
        "panic5": panic5, "panic8": panic8, "verdict": verdict, "panic_recover": pr,
        "cum80": r.get("cum80"), "dtop": r.get("dtop"), "net5": r.get("net5"),
        "score": r.get("score"), "turn": r.get("turn"), "vol_ratio": r.get("vol_ratio"),
    })
    if i % 15 == 0:
        print(f"  {i}/{len(cands_in)}", file=sys.stderr)

# rank: prefer where a shallow panic reaches support (to_ma5 in -8..-2) + strong + has recovered before
def _rk(x):
    near = 0 if -8 <= x["to_ma5"] <= -2 else (1 if x["to_ma5"] > -2 else 2)
    return (near, -(x["score"] or 0), -x["panic_recover"])
out.sort(key=_rk)
json.dump({"date": end, "candidates": out}, open("/tmp/pullback.json", "w"), ensure_ascii=False, indent=1)
print(f"潜在低吸候选 {len(out)} 只", file=sys.stderr)
for x in out[:10]:
    print(f"  {x['name']} 现{x['price']} | -5%→{x['panic5']} -8%→{x['panic8']} | MA5={x['ma5']}({x['to_ma5']}%) | "
          f"{x['verdict']} | 近期恐慌拉回{x['panic_recover']}次 净{(x['net5'] or 0)/10000:+.1f}亿", file=sys.stderr)
