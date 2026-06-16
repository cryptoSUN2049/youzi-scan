# -*- coding: utf-8 -*-
"""
Shared helpers: trading calendar, dynamic date windows, robust limit-list,
and the market sentiment cycle (with sanity-check + cache fallback).

All network access goes through mcp_client (serial-safe).
"""
import os
import json
import datetime
import mcp_client as mc

HERE = os.path.dirname(os.path.abspath(__file__))
# Sentiment cache lives under data/ so it can be shipped as an example & refreshed in place.
SENT_CACHE = os.path.join(os.path.dirname(HERE), "data", "sentiment_cache.json")


def _d(s):
    return datetime.date.fromisoformat(s)


# ---------------- trading calendar ----------------
def trade_calendar(start, end):
    r = mc.call("equity_market_trade_calendar", {"start_date": start, "end_date": end, "provider": "tushare"})
    if isinstance(r, dict):
        r = r.get("results", [])
    return r or []


def resolve_trading_day(date):
    """If `date` is a trading day return it; otherwise return the most recent prior trading day."""
    cal = trade_calendar(date, date)
    if cal and cal[0].get("is_open") == 1:
        return date
    if cal and cal[0].get("pretrade_date"):
        return cal[0]["pretrade_date"]
    cal = trade_calendar((_d(date) - datetime.timedelta(days=12)).isoformat(), date)
    opens = sorted(c["date"] for c in cal if c.get("is_open") == 1 and c["date"] <= date)
    return opens[-1] if opens else date


def prev_trading_days(date, n):
    """The most recent n trading days <= date, ascending.
    NB: trade_calendar returns descending order, so we sort before slicing."""
    start = (_d(date) - datetime.timedelta(days=n * 2 + 14)).isoformat()
    cal = trade_calendar(start, date)
    opens = sorted(c["date"] for c in cal if c.get("is_open") == 1 and c["date"] <= date)
    return opens[-n:]


# ---------------- dynamic date windows ----------------
def windows(date):
    """Start dates for each pull window, derived from the anchor date (calendar days,
    sized to cover the target number of trading days). Never hard-code dates."""
    dd = _d(date)
    return {
        "hist":      (dd - datetime.timedelta(days=120)).isoformat(),  # ~80 trading days (main rally)
        "moneyflow": (dd - datetime.timedelta(days=16)).isoformat(),   # ~10 trading days (5d flow + streak)
        "backup":    (dd - datetime.timedelta(days=24)).isoformat(),   # ~15 trading days (turnover/vol trend)
        "factor":    (dd - datetime.timedelta(days=70)).isoformat(),   # ~45 trading days (MA60/MACD)
    }


# ---------------- robust limit-list ----------------
def robust_limit_list(date, limit_type):
    """The gateway is inconsistent about the param name (trade_date YYYYMMDD vs date YYYY-MM-DD)
    across load-balanced workers. Try both, keep the non-empty/larger result, dedupe by ts_code."""
    cands = [
        {"trade_date": date.replace("-", ""), "limit_type": limit_type, "provider": "tushare"},
        {"date": date, "limit_type": limit_type, "provider": "tushare"},
    ]
    best = []
    for a in cands:
        r = mc.call("equity_market_limit_list", a)
        if isinstance(r, dict):
            r = r.get("results", r)
        if isinstance(r, list) and len(r) > len(best):
            best = r
    seen = {}
    for x in best:
        seen[x.get("ts_code")] = x
    return list(seen.values())


def _sentiment_one_day(date):
    """One trading day. Sanity check: a normal A-share session has >=10 limit-ups; anything
    less means the EOD batch hasn't populated (or the gateway routed to an empty worker) -> None."""
    u = robust_limit_list(date, "U")  # limit-up
    z = robust_limit_list(date, "Z")  # broken-board (failed limit)
    nu, nz = len(u), len(z)
    if nu < 10:
        return None
    lt = [int(x.get("limit_times") or 1) for x in u]
    return {"up": nu, "z": nz,
            "seal": round(nu / (nu + nz) * 100) if (nu + nz) else 0,
            "mb": max(lt) if lt else 0,                 # highest consecutive limit-ups
            "b2": sum(1 for b in lt if b >= 2)}          # count of >=2 consecutive


def compute_sentiment(date, days=6):
    """
    Returns (rows, asof, fresh):
      - Pulls the last `days` trading days and sanity-checks each.
      - If >= half are valid, refresh the cache and return fresh=True.
      - Otherwise fall back to the cache (if any), fresh=False, asof=cache date.
        Never shows garbage, never pretends stale data is current.
    rows: [{d, up, z, seal, mb, b2}]
    """
    tdays = prev_trading_days(date, days)
    rows, valid = [], 0
    for d in tdays:
        s = _sentiment_one_day(d)
        if s:
            valid += 1
            rows.append({"d": d[5:], **s})
        else:
            rows.append({"d": d[5:], "up": None, "z": None, "seal": None, "mb": None, "b2": None})
    if valid >= max(1, days // 2):
        os.makedirs(os.path.dirname(SENT_CACHE), exist_ok=True)
        json.dump({"asof": date, "rows": rows}, open(SENT_CACHE, "w"), ensure_ascii=False)
        return rows, date, True
    if os.path.exists(SENT_CACHE):
        c = json.load(open(SENT_CACHE))
        return c["rows"], c.get("asof", "unknown"), False
    return rows, date, False


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-06-16"
    print("resolve_trading_day:", resolve_trading_day(date))
    print("prev 6 trading days:", prev_trading_days(date, 6))
    print("windows:", json.dumps(windows(date)))
    rows, asof, fresh = compute_sentiment(date)
    print(f"sentiment asof={asof} fresh={fresh}")
