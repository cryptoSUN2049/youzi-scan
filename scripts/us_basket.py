#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pull key US AI/tech stocks (DataHub provider=fmp) and inject into /tmp/macro.json overseas.ai_stocks,
so the 外盘 section continuously tracks the names that lead the AI trade (the overnight read that
transmits to the A-share AI-compute chain). Part of STEP 3 (macro). Run after the agent has written
the rest of macro.json (indices / sector flow / news).

Usage: python3 us_basket.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_client as mc

# Ordered to mirror the A-share AI-compute chain (each US name transmits to an A-share sub-sector):
BASKET = [
    # 算力芯片 / 半导体
    ("NVDA", "英伟达"), ("AMD", "超威半导"), ("AVGO", "博通"), ("MRVL", "美满"), ("TSM", "台积电"),
    # 存储 -> A股存储链
    ("MU", "美光"), ("SNDK", "闪迪"),
    # 光模块 / 光通信 -> A股光模块/CPO
    ("LITE", "Lumentum"), ("COHR", "Coherent"),
    # 玻璃/光纤 -> A股玻璃基板/光纤
    ("GLW", "康宁"),
    # 服务器
    ("SMCI", "超微"),
    # 巨头(宏观底色)
    ("MSFT", "微软"), ("GOOGL", "谷歌"), ("META", "Meta"), ("AMZN", "亚马逊"), ("AAPL", "苹果"), ("TSLA", "特斯拉"),
    # 锂 -> A股电新/固态电池(资金轮动参照)
    ("ALB", "雅保"),
]

stocks = []
for sym, zh in BASKET:
    q = mc.call("equity_price_quote", {"symbol": sym, "provider": "fmp"})
    if isinstance(q, list) and q:
        q = q[0]
    if isinstance(q, dict) and q.get("last_price") is not None:
        cp = q.get("change_percent")
        stocks.append({"name": zh, "sym": sym, "px": round(q.get("last_price"), 2),
                       "pct": round((cp or 0) * 100, 2)})
    else:
        print(f"  miss {sym}", file=sys.stderr)

path = "/tmp/macro.json"
m = json.load(open(path)) if os.path.exists(path) else {"overseas": {}}
m.setdefault("overseas", {})["ai_stocks"] = stocks
json.dump(m, open(path, "w"), ensure_ascii=False, indent=1)
print(f"US AI/tech basket -> macro.json: {len(stocks)} stocks", file=sys.stderr)
for s in stocks:
    print(f"  {s['name']}({s['sym']}) {s['px']} {s['pct']:+}%", file=sys.stderr)
