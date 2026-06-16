#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-render the report from the saved context + an agent-written conclusion — NO data re-pull.

Workflow (deterministic data from scripts, analysis from the agent):
  1) python3 scan.py ... --macro-json ... --patterns-json ...   # pulls data, writes /tmp/youzi_ctx.json
  2) <agent reads /tmp/youzi_scored.json + patterns + macro, writes a conclusion HTML/text file>
  3) python3 render_final.py --conclusion-file conclusion.html --macro-json /tmp/macro.json \
        --patterns-json /tmp/patterns.json --out ../reports

The conclusion is the AGENT's analysis of the real numbers — the script never fabricates it.
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", default="/tmp/youzi_ctx.json")
    ap.add_argument("--conclusion-file", default=None)
    ap.add_argument("--macro-json", default="/tmp/macro.json")
    ap.add_argument("--patterns-json", default="/tmp/patterns.json")
    ap.add_argument("--out", default="./reports")
    a = ap.parse_args()

    ctx = json.load(open(a.ctx))
    macro = json.load(open(a.macro_json)) if os.path.exists(a.macro_json) else None
    patterns = json.load(open(a.patterns_json)) if os.path.exists(a.patterns_json) else None
    conclusion = open(a.conclusion_file).read() if a.conclusion_file and os.path.exists(a.conclusion_file) else None

    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{ctx['title']}-youzi-scan-{ctx['date']}.html")
    report.render(ctx["rows"], out_file, ctx["title"], ctx["date"],
                  sentiment=ctx.get("sentiment"), sent_asof=ctx.get("sent_asof"),
                  sent_fresh=ctx.get("sent_fresh", False), stats=ctx.get("stats"),
                  freshness=ctx.get("freshness"), lang=ctx.get("lang", "zh"),
                  macro=macro, patterns=patterns, conclusion=conclusion)
    print("OK report:", out_file, file=sys.stderr)


if __name__ == "__main__":
    main()
