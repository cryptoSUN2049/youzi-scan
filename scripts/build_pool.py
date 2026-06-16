#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maintain the watchlist pool. Merge stocks from research HTML sources into data/watchlist.csv.

Schema: code,name,theme,tier,tags,sources,added,active
  - code   : ts_code with suffix (primary key)
  - theme  : canonical English key (scan.py groups by it; report.py localizes zh/en)
  - tier   : 龙头 / 二线 / 题材 (free; default "")
  - tags   : free concepts, ';'-separated (a stock can sit on multiple chains)
  - sources: provenance, ';'-separated
  - added  : first-added date (YYYY-MM-DD)
  - active : 1 / 0 (retire without deleting history)

Usage:
  python3 build_pool.py --seed-csv symbols_ai_compute.csv --seed-src "算力紧缺-2026-05-24" --seed-date 2026-05-24
  python3 build_pool.py <source.html> --src-name "基建-2026-06-04" --src-date 2026-06-04
Both can combine; merging is idempotent (re-running the same source changes nothing).
"""
import os, re, csv, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(os.path.dirname(HERE), "data", "watchlist.csv")
FIELDS = ["code", "name", "theme", "tier", "tags", "sources", "added", "active"]

# raw theme/label keyword -> canonical English key (must match report.py THEME_ORDER)
def norm_theme(raw):
    s = (raw or "")
    rules = [
        ("存储", "Memory"), ("HBM", "Memory"), ("DRAM", "Memory"), ("颗粒", "Memory"),
        ("光", "Optical/CPO"), ("CPO", "Optical/CPO"), ("硅光", "Optical/CPO"), ("LPO", "Optical/CPO"),
        ("PCB", "PCB/Substrate"), ("载板", "PCB/Substrate"), ("基板", "Panel/Glass Substrate"),
        ("覆铜板", "CCL/Fiberglass/Resin"), ("CCL", "CCL/Fiberglass/Resin"), ("玻纤", "CCL/Fiberglass/Resin"), ("树脂", "CCL/Fiberglass/Resin"),
        ("MLCC", "MLCC/Passives"), ("被动", "MLCC/Passives"), ("电感", "MLCC/Passives"), ("电容", "MLCC/Passives"), ("磁", "MLCC/Passives"),
        ("铜箔", "Copper Foil/Connect"), ("铜连接", "Copper Foil/Connect"), ("铜缆", "Copper Foil/Connect"),
        ("液冷", "Cooling/Power/Connector"), ("电源", "Cooling/Power/Connector"), ("散热", "Cooling/Power/Connector"), ("连接器", "Cooling/Power/Connector"), ("温控", "Cooling/Power/Connector"),
        ("设备", "Semi Equipment"), ("刻蚀", "Semi Equipment"), ("光刻", "Semi Equipment"), ("封装设备", "Semi Equipment"),
        ("材料", "Semi Materials"), ("特气", "Semi Materials"), ("前驱体", "Semi Materials"), ("抛光", "Semi Materials"), ("硅微粉", "Semi Materials"), ("石英", "Semi Materials"),
        ("封测", "Other Optical/OSAT"), ("先进封装", "Other Optical/OSAT"), ("CoWoS", "Other Optical/OSAT"),
        ("软件", "Software/Ecosystem"), ("生态", "Software/Ecosystem"), ("整机", "Software/Ecosystem"), ("服务器", "Software/Ecosystem"), ("交换机", "Software/Ecosystem"),
        ("面板", "Panel/Glass Substrate"), ("玻璃", "Panel/Glass Substrate"),
        ("GPU", "Compute Chips"), ("CPU", "Compute Chips"), ("芯片", "Compute Chips"), ("算力", "Compute Chips"), ("FPGA", "Compute Chips"), ("ASIC", "Compute Chips"),
    ]
    for kw, canon in rules:
        if kw in s:
            return canon
    return "Other"

def suffix(code):
    code = code.strip()
    if "." in code:
        return code
    if code[0] == "6":
        return code + ".SH"
    if code[0] in "03":
        return code + ".SZ"
    if code[0] in "48":
        return code + ".BJ"
    return code + ".SZ"

def load_pool():
    if not os.path.exists(POOL):
        return {}
    return {r["code"]: r for r in csv.DictReader(open(POOL))}

def merge(pool, code, name, theme, tags, source, added, tier=""):
    code = suffix(code)
    cur = pool.get(code)
    if not cur:
        pool[code] = {"code": code, "name": name, "theme": theme, "tier": tier,
                      "tags": ";".join(tags), "sources": source, "added": added, "active": "1"}
        return
    # merge tags + sources (union), keep earliest added, fill theme/tier if empty
    tset = [t for t in cur["tags"].split(";") if t] + [t for t in tags if t not in cur["tags"]]
    sset = [s for s in cur["sources"].split(";") if s]
    if source not in sset:
        sset.append(source)
    cur["tags"] = ";".join(dict.fromkeys(tset))
    cur["sources"] = ";".join(sset)
    cur["added"] = min(cur["added"], added) if cur["added"] else added
    if not cur.get("theme") or cur["theme"] == "Other":
        cur["theme"] = theme
    if tier and not cur.get("tier"):
        cur["tier"] = tier

def extract_html(path):
    """Extract (code, name, raw_theme) from research HTML. Handles two JS formats."""
    txt = open(path, encoding="utf-8", errors="ignore").read()
    out = []
    # format C: {t:"半导体设备", co:[["688072.SH","拓荆科技","a"],...]}  (segment theme in t)
    for seg in re.finditer(r't:"([^"]+)"\s*,\s*co:\[(.*?)\]\s*\}', txt, re.S):
        theme = seg.group(1)
        for m in re.finditer(r'\["(\d{6}\.\w{2})"\s*,\s*"([^"]+)"', seg.group(2)):
            out.append((m.group(1), m.group(2), theme))
    # format B: {n:"中际旭创",c:"300308",L:"光互联·光模块"...}
    for m in re.finditer(r'\{[^{}]*?n:"([^"]+)"[^{}]*?c:"(\d{6})"[^{}]*?(?:L:"([^"]*)")?[^{}]*?\}', txt):
        out.append((m.group(2), m.group(1), m.group(3) or ""))
    # format A: code:"600584.SH",nm:"长电科技"
    for m in re.finditer(r'code:"(\d{6}\.\w{2})"\s*,\s*nm:"([^"]+)"', txt):
        out.append((m.group(1), m.group(2), ""))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="*", help="research HTML files")
    ap.add_argument("--seed-csv"); ap.add_argument("--seed-src", default="seed"); ap.add_argument("--seed-date", default="")
    ap.add_argument("--src-name", default=""); ap.add_argument("--src-date", default="")
    a = ap.parse_args()
    pool = load_pool()
    # seed from an existing code,name,theme csv
    if a.seed_csv:
        for r in csv.DictReader(open(a.seed_csv)):
            merge(pool, r["code"], r.get("name", ""), r.get("theme", "Other"),
                  [r.get("theme", "")], a.seed_src, a.seed_date)
    # merge HTML sources
    for src in a.sources:
        name_tag = a.src_name or os.path.basename(src)
        date = a.src_date or (re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(src)) or [None, ""])[1] if re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(src)) else ""
        date = (re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(src)) or type('', (), {'group': lambda *_: ""})()).group(1) if re.search(r'\d{4}-\d{2}-\d{2}', os.path.basename(src)) else date
        for code, name, raw in extract_html(src):
            th = norm_theme(raw)
            tags = [t for t in [raw] if t]
            merge(pool, code, name, th, tags, name_tag, date)
    # write
    os.makedirs(os.path.dirname(POOL), exist_ok=True)
    rows = sorted(pool.values(), key=lambda r: (r["theme"], r["code"]))
    with open(POOL, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"pool: {len(rows)} stocks -> {POOL}")
    from collections import Counter
    print("by theme:", dict(Counter(r["theme"] for r in rows)))

if __name__ == "__main__":
    main()
