# -*- coding: utf-8 -*-
"""
DataHub (tushare gateway) MCP client — serial-safe, streamable-HTTP.

The endpoint URL is hard-coded below (override with DATAHUB_MCP_URL if you like).
The TOKEN is read ONLY from the environment (or a local .env file) — never commit it.

  DATAHUB_MCP_TOKEN  e.g. "Bearer xxxxxxxx"   (required)
  DATAHUB_MCP_URL    optional override of the default endpoint

Hard-won notes (the pipeline already works around these):
  - The streamable-HTTP MCP session is single-threaded: concurrent calls collide
    and return empty. ALWAYS call serially. Never fan out in parallel.
  - A-shares require provider="tushare", otherwise the quote endpoint routes to a
    US-equity source and fails schema validation.
  - `change_percent` is a fraction (0.0416 == 4.16%); multiply by 100.
"""
import os
import json
import time
import urllib.request


def _load_dotenv():
    """Minimal .env loader (stdlib only, no dependency). Looks in CWD and repo root."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(os.getcwd(), ".env"), os.path.join(here, ".env")):
        if not os.path.exists(path):
            continue
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# Endpoint can be hard-coded; override via env if needed.
MCP_URL = os.environ.get("DATAHUB_MCP_URL", "http://43.128.100.43:8010/mcp")
# Token is a secret: env / .env only, never committed.
MCP_TOKEN = os.environ.get("DATAHUB_MCP_TOKEN")  # "Bearer ..."

if not MCP_TOKEN:
    raise SystemExit(
        "Missing DATAHUB_MCP_TOKEN. Set it as an env var or in a local .env file "
        "(see .env.example). Never commit your token."
    )

_HDR_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": MCP_TOKEN,
}


def _init_session():
    """Open an MCP session (initialize handshake) and return the session id."""
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "youzi-scan", "version": "1"}},
    }
    req = urllib.request.Request(MCP_URL, data=json.dumps(body).encode(), headers=_HDR_BASE)
    resp = urllib.request.urlopen(req, timeout=30)
    sid = resp.headers.get("mcp-session-id")
    h = dict(_HDR_BASE); h["Mcp-Session-Id"] = sid
    note = urllib.request.Request(
        MCP_URL, data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode(), headers=h)
    urllib.request.urlopen(note, timeout=15).read()
    return sid


SID = _init_session()
_HDR = dict(_HDR_BASE)
_HDR["Mcp-Session-Id"] = SID


def call(name, args, retry=2):
    """Call one MCP tool serially. Returns the parsed `results` (or raw dict); None on failure."""
    for _ in range(retry + 1):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": name, "arguments": args}}
        req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(), headers=_HDR)
        try:
            raw = urllib.request.urlopen(req, timeout=90).read().decode()
        except Exception:
            time.sleep(0.5); continue
        obj = None
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data: "):
                line = line[6:]
            if line.startswith("{"):
                try:
                    obj = json.loads(line); break
                except Exception:
                    pass
        if not obj:
            time.sleep(0.5); continue
        r = obj.get("result", {})
        if r.get("isError"):
            time.sleep(0.5); continue
        try:
            data = json.loads(r["content"][0]["text"])
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception:
            return None
    return None


# --- convenience wrappers (A-shares always provider=tushare) ---
def quote(symbol):
    return call("equity_price_quote", {"symbol": symbol, "provider": "tushare"})


def history(symbol, start, end):
    return call("equity_price_historical",
                {"symbol": symbol, "start_date": start, "end_date": end, "provider": "tushare"}) or []


def moneyflow(symbol, start, end):
    return call("equity_moneyflow_individual",
                {"symbol": symbol, "start_date": start, "end_date": end, "provider": "tushare"}) or []


if __name__ == "__main__":
    print("MCP session:", SID)
    print("Smoke test (002463.SZ quote):")
    q = quote("002463.SZ")
    if isinstance(q, list):
        q = q[0] if q else {}
    print("  last_price:", q.get("last_price"), "| change%:", round((q.get("change_percent") or 0) * 100, 2))
