# -*- coding: utf-8 -*-
"""
HTML report renderer: render(rows, out_file, title, date, sentiment, sent_asof,
sent_fresh, stats, freshness).

Sentiment / freshness / coverage are all injected by scan.py (nothing hard-coded).
Dark theme, A-share convention (red = up, green = down), 4 dimensions + 5 tactics.
"""
import os
import json
from collections import Counter

TAC_META = {
    "🟢 Ambush":      ("buy",   "Low position + sustained institutional accumulation; rally not started — left-side ambush"),
    "🔵 Dip":         ("dip",   "Uptrend pullback to MA10 on low volume — right-side dip-buy"),
    "🟡 Halfway":     ("mid",   "Volume breakout + active turnover + strong attack — board mid-way"),
    "🔴 Limit-chase": ("board", "Limit-up + strong seal + not high — chase the board"),
    "⚠️ High":        ("warn",  "High-position relay; thesis OK but price extended — don't chase"),
    "⛔ Avoid":       ("no",    "High + huge turnover / parabolic end / volume-price divergence — distribution risk"),
    "△ Watch":        ("mid",   "Volume/capital signals unclear — track"),
}
THEMES = ["Memory", "Optical/CPO", "Compute Chips", "Semi Equipment", "Semi Materials",
          "CCL/Fiberglass/Resin", "PCB/Substrate", "MLCC/Passives", "Copper Foil/Connect",
          "Cooling/Power/Connector", "Software/Ecosystem", "Panel/Glass Substrate", "Other Optical/OSAT", "Other"]


def _n(x, d=0):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "—"


def _chgcls(c):
    return 'up' if (c or 0) > 0 else ('down' if (c or 0) < 0 else 'flat')


def _vrcls(v):
    return 'up' if (v or 0) > 1.5 else ('down' if (v is not None and v < 0.8) else 'flat')


def _vphcls(v):
    if 'attack' in v or 'healthy' in v or 'coiling' in v:
        return 'good'
    if 'divergence' in v or 'distribution' in v:
        return 'bad'
    return 'mid'


def sentiment_verdict(sent):
    """Auto-generate the cycle read from the sentiment data (no hard-coding)."""
    valid = [s for s in sent if s.get("up")]
    if len(valid) < 2:
        return "Sentiment data not ready", "limit_list EOD batch / gateway not serving yet; using cache, refresh later."
    ups = [s["up"] for s in valid]
    last = valid[-1]
    peak = max(ups)
    last_seal = last.get("seal") or 0
    last_mb = last.get("mb") or 0
    trend_up = len(ups) >= 2 and ups[-1] > ups[-2]
    if last_seal >= 75 and last_mb >= 6 and trend_up:
        return ("Offensive / building — rally-tradeable",
                f"Seal rate {last_seal}%, top {last_mb} consecutive limit-ups; strong money effect, the main-rally feedback loop holds.")
    if last_seal >= 65:
        return ("Rebound after climax — lacks a high-ladder leader",
                f"{last['up']} limit-ups (peak {peak}), seal {last_seal}%, top {last_mb} boards. Index may be strong but lacks ladder height; money rotates into low laggards, not high relays.")
    return ("Ebb / divergence — defensive",
            f"Seal only {last_seal}%, top {last_mb} boards; many broken boards, money effect fading. Main-rally traders should wait for a colder reset.")


def _card(r):
    cls = TAC_META.get(r["tactic"], ("mid", ""))[0]
    hm = ('｜hot-money ' + '·'.join(r['hm'])) if r.get('hm') else ''
    net5 = (r.get('net5') or 0) / 10000
    ma = "bull" if r.get("ma_bull") == 1 else "non-bull"
    macdst = "red" if (r.get("macd") or 0) > 0 else "green"
    return f'''<div class="pick p-{cls}">
<div class="pk-h"><span class="pk-nm">{r['name']}</span><span class="pk-code">{r['code']}</span>
<span class="pk-score">{r.get('score','')}</span><span class="pk-th">{r['theme']}</span></div>
<div class="pk-grid">
<div class="pk-m"><div class="l">Chg</div><div class="v {_chgcls(r.get('chg'))}">{_n(r.get('chg'),1)}%</div></div>
<div class="pk-m"><div class="l">Vol-ratio</div><div class="v {_vrcls(r.get('vol_ratio'))}">{_n(r.get('vol_ratio'),2)}</div></div>
<div class="pk-m"><div class="l">Turnover</div><div class="v">{_n(r.get('turn'),1)}%</div></div>
<div class="pk-m"><div class="l">Rally</div><div class="v">+{_n(r.get('cum80'),0)}%</div></div>
<div class="pk-m"><div class="l">vs Top</div><div class="v">{_n(r.get('dtop'),0)}%</div></div>
<div class="pk-m"><div class="l">5d Inflow</div><div class="v {'up' if net5>=0 else 'down'}">{('+' if net5>=0 else '')}{net5:.1f}e8</div></div>
<div class="pk-m"><div class="l">Streak</div><div class="v">{r.get('streak',0)}d</div></div>
<div class="pk-m"><div class="l">MA</div><div class="v">{ma}</div></div>
<div class="pk-m"><div class="l">MACD</div><div class="v">{macdst}</div></div>
</div>
<div class="pk-vph vph-{_vphcls(r.get('vph','-'))}">{r.get('vph','-')}</div>
<div class="pk-logic">▶ {r.get('reason','')}{hm}</div></div>'''


def _section_cards(rows, tac):
    rs = sorted([r for r in rows if r["tactic"] == tac], key=lambda x: -x.get("score", 0))
    if not rs:
        return ""
    desc = TAC_META[tac][1]
    return f'<div class="tac-desc">{desc} · {len(rs)} stocks</div><div class="picks">' + ''.join(_card(r) for r in rs) + '</div>'


def _full_row(r):
    cls = TAC_META.get(r["tactic"], ("mid", ""))[0]
    net5 = (r.get('net5') or 0) / 10000
    bull = '✓' if r.get("ma_bull") == 1 else '·'
    macd = 'R' if (r.get("macd") or 0) > 0 else 'G'
    kdj = r.get("kdj_j")
    kdjcls = 'up' if (kdj or 0) > 80 else ('down' if (kdj or 0) < 20 else '')
    streak = r.get('streak', 0)
    return f'''<tr class="t-{cls}">
<td class="nm">{r['name']}<small>{r['code']}</small></td>
<td class="num {_chgcls(r.get('chg'))}">{_n(r.get('chg'),1)}%</td>
<td class="num {_vrcls(r.get('vol_ratio'))}">{_n(r.get('vol_ratio'),2)}</td>
<td class="num">{_n(r.get('turn'),1)}</td>
<td class="num">{_n(r.get('turn5'),1)}</td>
<td class="num">{_n(r.get('swing'),1)}</td>
<td class="num">+{_n(r.get('cum80'),0)}%</td>
<td class="num">{_n(r.get('dtop'),0)}%</td>
<td class="c">{bull}</td>
<td class="num">{_n(r.get('above_ma10'),1)}</td>
<td class="c">{macd}</td>
<td class="num {kdjcls}">{_n(r.get('kdj_j'),0)}</td>
<td class="num {'up' if net5>=0 else 'down'}">{('+' if net5>=0 else '')}{net5:.1f}</td>
<td class="c">{('x'+str(streak)) if streak>=3 else (str(streak) if streak else '·')}</td>
<td class="vph vph-{_vphcls(r.get('vph','-'))}">{r.get('vph','-')}</td>
<td class="c">{('★'+'·'.join(r['hm'][:2])) if r.get('hm') else '·'}</td>
<td class="tac t-{cls}">{r['tactic']}</td>
<td class="num"><b>{r.get('score','')}</b></td>
</tr>'''


def render(rows, out_file, title="AI Compute Chain", date="2026-06-16",
           sentiment=None, sent_asof=None, sent_fresh=False, stats=None, freshness=None):
    sentiment = sentiment or []
    stats = stats or {}
    freshness = freshness or {}
    cnt = Counter(r["tactic"] for r in rows)

    def cc(t):
        return cnt.get(t, 0)

    by_theme = ""
    for th in THEMES:
        rs = [r for r in rows if r.get('theme') == th]
        if not rs:
            continue
        rs = sorted(rs, key=lambda x: -x.get('score', 0))
        by_theme += f'<tr class="grp"><td colspan="18">▎{th} ({len(rs)})</td></tr>\n' + '\n'.join(_full_row(r) for r in rs) + '\n'

    sent_rows = ""
    for s in sentiment:
        seal = f"{s['seal']}%" if s.get('seal') else "—"
        mb = f"{s['mb']}" if s.get('mb') else "—"
        b2 = s.get('b2') if s.get('b2') is not None else "—"
        z = s.get('z') if s.get('z') is not None else "—"
        sent_rows += f'<tr><td class="mono">{s["d"]}</td><td class="num">{s.get("up","—")}</td><td class="num">{z}</td><td class="num">{seal}</td><td class="num">{mb}</td><td class="num">{b2}</td></tr>'
    v_head, v_detail = sentiment_verdict(sentiment)
    fresh_badge = ("🟢 live" if sent_fresh else f"🟡 cached (asof {sent_asof})")

    vp_date = freshness.get("vp_date", "—")
    mf_date = freshness.get("mf_date", "—")
    price_date = freshness.get("price_date", date)
    vp_lag = "" if vp_date == date else f" — NB: vol/turnover/tech anchored {vp_date}, flow {mf_date} (EOD not fully landed)"
    tot = stats.get("total", len(rows))
    succ = f"price{stats.get('price',0)} pos{stats.get('cum80',0)} flow{stats.get('net5',0)} vp{stats.get('turn',0)} tech{stats.get('macd',0)} (of {tot})"
    failed = stats.get("failed", [])
    fail_txt = f"; missing {len(failed)}: {', '.join(failed[:8])}{'…' if len(failed)>8 else ''}" if failed else ""

    pools = {t: _section_cards(rows, t) for t in ["🟢 Ambush", "🔵 Dip", "🟡 Halfway", "🔴 Limit-chase"]}

    html = f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} · youzi-scan · {date}</title>
<style>
:root{{--bg:#0a0e14;--panel:#11161f;--panel2:#161d28;--line:#222c3a;--txt:#e6edf3;--txt2:#9aa7b8;--txt3:#5f6c7d;
--up:#ff4d4f;--down:#1bbf83;--flat:#8a96a6;--gold:#f5a623;--cyan:#3dd9d6;--blue:#4d8dff;--purple:#a374ff;
--g-buy:#33d6a6;--g-dip:#4d8dff;--g-mid:#f5a623;--g-board:#ff6b9d;--g-no:#ff6b6b;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt);line-height:1.55;}}
.mono{{font-family:"JetBrains Mono",Monaco,Consolas,monospace;font-variant-numeric:tabular-nums;}}
header{{background:linear-gradient(135deg,#0d1420,#13212e 60%,#1a2f33);border-bottom:1px solid var(--line);padding:30px 28px 22px;}}
.eyebrow{{font-size:12px;letter-spacing:3px;color:var(--cyan);font-weight:600;}}
h1{{font-size:25px;font-weight:800;margin:8px 0 6px;}}
h1 .hl{{background:linear-gradient(90deg,var(--gold),var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent;}}
.lede{{color:var(--txt2);font-size:13px;max-width:940px;}}
.meta{{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px;}}
.chip{{font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid var(--line);background:#0e151f;color:var(--txt2);}}
.chip b{{color:var(--txt);}}
.tac-bar{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;}}
.tac-pill{{font-size:12px;padding:5px 12px;border-radius:8px;font-weight:700;}}
.tp-buy{{background:rgba(51,214,166,.15);color:var(--g-buy);border:1px solid var(--g-buy);}}
.tp-dip{{background:rgba(77,141,255,.15);color:var(--g-dip);border:1px solid var(--g-dip);}}
.tp-mid{{background:rgba(245,166,35,.15);color:var(--g-mid);border:1px solid var(--g-mid);}}
.tp-board{{background:rgba(255,107,157,.15);color:var(--g-board);border:1px solid var(--g-board);}}
.tp-no{{background:rgba(255,107,107,.12);color:var(--g-no);border:1px solid var(--g-no);}}
.wrap{{padding:24px 28px 60px;max-width:1480px;margin:0 auto;}}
section{{margin-bottom:32px;}}
.sec-h{{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:14px;}}
.sec-h h2{{font-size:18px;font-weight:700;}} .sec-h .n{{font-family:monospace;font-size:13px;color:var(--gold);font-weight:700;}}
.sec-h .desc{{font-size:12px;color:var(--txt3);margin-left:auto;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
th,td{{padding:6px 7px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap;}}
th{{background:var(--panel2);color:var(--txt2);font-weight:600;font-size:10.5px;}}
td.num{{text-align:right;font-family:monospace;}} td.c{{text-align:center;}}
.up{{color:var(--up);}} .down{{color:var(--down);}} .flat{{color:var(--flat);}}
.tbl-wrap{{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow-x:auto;}}
.nm{{font-weight:600;}} .nm small{{display:block;color:var(--txt3);font-size:9.5px;font-family:monospace;font-weight:400;}}
.tac{{font-weight:700;font-size:11px;}}
.t-buy .tac,.tac.t-buy{{color:var(--g-buy);}} .t-dip .tac,.tac.t-dip{{color:var(--g-dip);}}
.t-mid .tac,.tac.t-mid{{color:var(--txt3);}} .t-board .tac,.tac.t-board{{color:var(--g-board);}}
.t-no .tac,.tac.t-no{{color:var(--g-no);}} .t-warn .tac,.tac.t-warn{{color:var(--gold);}}
tr.t-buy{{background:rgba(51,214,166,.05);}} tr.t-board{{background:rgba(255,107,157,.05);}}
tr.grp td{{background:#0c1119;color:var(--cyan);font-weight:700;font-size:11.5px;border-top:1px solid var(--line);}}
.vph{{font-size:10.5px;}} .vph-good{{color:var(--g-buy);}} .vph-bad{{color:var(--up);}} .vph-mid{{color:var(--txt2);}}
.picks{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:13px;}}
.pick{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--g-mid);border-radius:10px;padding:12px 14px;}}
.p-buy{{border-left-color:var(--g-buy);}} .p-dip{{border-left-color:var(--g-dip);}}
.p-board{{border-left-color:var(--g-board);}} .p-no{{border-left-color:var(--g-no);}} .p-warn{{border-left-color:var(--gold);}}
.pk-h{{display:flex;align-items:center;gap:7px;margin-bottom:9px;}}
.pk-nm{{font-size:15px;font-weight:800;}} .pk-code{{font-family:monospace;font-size:10.5px;color:var(--txt3);}}
.pk-score{{font-family:monospace;font-size:13px;font-weight:800;color:var(--gold);background:#1a1408;border:1px solid #3a2c0c;border-radius:6px;padding:1px 7px;}}
.pk-th{{margin-left:auto;font-size:10px;padding:2px 7px;border-radius:9px;background:var(--panel2);color:var(--cyan);}}
.pk-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px;}}
.pk-m{{background:var(--panel2);border-radius:6px;padding:5px 7px;}}
.pk-m .l{{font-size:9.5px;color:var(--txt3);}} .pk-m .v{{font-size:13px;font-weight:700;font-family:monospace;margin-top:1px;}}
.pk-vph{{font-size:11px;font-weight:700;margin-bottom:6px;}}
.pk-logic{{font-size:11px;color:var(--txt2);background:#0c1119;border-radius:6px;padding:6px 8px;}}
.kbox{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);border-radius:8px;padding:11px 13px;}}
.kbox.gold{{border-left-color:var(--gold);}} .kbox.green{{border-left-color:var(--down);}}
.kbox .kl{{font-size:11px;color:var(--txt3);}} .kbox .kv{{font-size:15px;font-weight:700;margin:2px 0;}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px;}}
.note{{background:var(--panel2);border:1px dashed var(--line);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--txt2);}}
.note b{{color:var(--gold);}}
.warn-box{{background:#1a0d0d;border:1px solid #3a1818;border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--txt2);}}
.warn-box b{{color:var(--up);}}
.ind-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;}}
.ind-c{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px;}}
.ind-c h4{{font-size:12.5px;color:var(--cyan);margin-bottom:5px;}}
.ind-c p{{font-size:11px;color:var(--txt2);}}
footer{{border-top:1px solid var(--line);padding:16px 28px 36px;font-size:11px;color:var(--txt3);}}
</style></head><body>
<header>
<div class="eyebrow">HOT-MONEY LENS · VOLUME FIRST · 4-D SCAN (liquidity / pattern / capital / technicals)</div>
<h1>{title} · <span class="hl">youzi-scan</span></h1>
<p class="lede">{len(rows)} A-share names scored the way a Chinese hot-money (游资) trader actually decides:
<b>volume-ratio · turnover · amplitude</b> (chip activity) + <b>moving averages · BOLL · main-rally position</b> (pattern) +
<b>net institutional inflow · accumulation streak · dragon-tiger seats</b> (smart money) + <b>MACD · KDJ · RSI</b> (timing),
bucketed into <b>Ambush / Dip / Halfway / Limit-chase / Avoid</b>.</p>
<div class="meta">
<span class="chip">data · <b>DataHub (tushare)</b></span>
<span class="chip">price · <b>{price_date}</b></span>
<span class="chip">vol/tech anchor · <b>{vp_date}</b></span>
<span class="chip">flow anchor · <b>{mf_date}</b></span>
<span class="chip">coverage · <b>{succ}</b></span>
</div>
<div class="tac-bar">
<span class="tac-pill tp-buy">🟢 Ambush {cc('🟢 Ambush')}</span>
<span class="tac-pill tp-dip">🔵 Dip {cc('🔵 Dip')}</span>
<span class="tac-pill tp-mid">🟡 Halfway {cc('🟡 Halfway')}</span>
<span class="tac-pill tp-board">🔴 Limit-chase {cc('🔴 Limit-chase')}</span>
<span class="tac-pill tp-no">⛔ Avoid {cc('⛔ Avoid')+cc('⚠️ High')}</span>
<span class="tac-pill" style="background:#161d28;color:var(--txt3)">△ Watch {cc('△ Watch')}</span>
</div></header>
<div class="wrap">

<section>
<div class="sec-h"><span class="n">01</span><h2>Market sentiment cycle (the gate)</h2><span class="desc">no rally without the right mood · {fresh_badge}</span></div>
<div class="tbl-wrap" style="margin-bottom:12px"><table>
<thead><tr><th>Date</th><th>Limit-ups</th><th>Broken</th><th>Seal%</th><th>Top boards</th><th>≥2 boards</th></tr></thead>
<tbody>{sent_rows}</tbody></table></div>
<div class="grid2">
<div class="kbox gold"><div class="kl">Cycle read (auto)</div><div class="kv">{v_head}</div>
<div style="font-size:11px;color:var(--txt2)">{v_detail}</div></div>
<div class="kbox green"><div class="kl">For main-rally traders</div><div class="kv">play low-position starts · avoid high relays</div>
<div style="font-size:11px;color:var(--txt2)">Prefer <b style="color:var(--down)">🟢 Ambush + 🔵 Dip</b> (institutions accumulating low / low-vol pullback); 🟡 Halfway needs a volume confirmation; 🔴 Limit-chase only on low-position first boards with a strong seal.</div></div>
</div></section>

<section>
<div class="sec-h"><span class="n">02</span><h2>The indicator system (what we pull, how we judge)</h2></div>
<div class="ind-grid">
<div class="ind-c"><h4>① Liquidity · turnover (the core)</h4><p>vol-ratio &lt;0.8 dry / 0.8-1.5 mild / &gt;1.5 heavy / &gt;2.5 huge; turnover 3-7% healthy, &gt;20% overheated (high = distribution); amplitude; volume-price health</p></div>
<div class="ind-c"><h4>② Position · pattern</h4><p>cumulative main-rally %, distance from 80-day top, MA bull alignment (MA5&gt;10&gt;20), MA10/20 deviation, BOLL position</p></div>
<div class="ind-c"><h4>③ Capital · institutions</h4><p>net institutional inflow (1d/5d), accumulation streak, order-book strength, dragon-tiger hot-money seats</p></div>
<div class="ind-c"><h4>④ Timing · technicals</h4><p>MACD red/green & above/below water, KDJ overbought/oversold, RSI strength</p></div>
</div></section>

<section>
<div class="sec-h"><span class="n">03</span><h2>🟢 Ambush pool · institutions accumulating low (top pick)</h2><span class="desc">low + dry volume + sustained inflow</span></div>
{pools["🟢 Ambush"] or '<div class="note">No ambush candidates in this snapshot.</div>'}
</section>

<section>
<div class="sec-h"><span class="n">04</span><h2>🔵 Dip pool · bull pullback on low volume</h2><span class="desc">pullback to MA10 + MACD above water</span></div>
{pools["🔵 Dip"] or '<div class="note">No dip candidates in this snapshot.</div>'}
</section>

<section>
<div class="sec-h"><span class="n">05</span><h2>🟡 Halfway pool · board it on a volume breakout</h2><span class="desc">heavy volume + active turnover + strong attack</span></div>
{pools["🟡 Halfway"] or '<div class="note">No halfway candidates in this snapshot.</div>'}
</section>

<section>
<div class="sec-h"><span class="n">06</span><h2>🔴 Limit-chase pool · board the limit-up</h2><span class="desc">strong seal + not high</span></div>
{pools["🔴 Limit-chase"] or '<div class="note">No qualifying low-position first-board limit-ups (most limit-ups are high one-word boards → Avoid).</div>'}
</section>

<section>
<div class="sec-h"><span class="n">07</span><h2>All {len(rows)} names · full 4-D table</h2><span class="desc">liquidity / pattern / capital / technicals / tactic / score</span></div>
<div class="tbl-wrap"><table>
<thead><tr><th>Name/Code</th><th>Chg</th><th>VolR</th><th>Turn</th><th>Turn5</th><th>Ampl</th><th>Rally</th><th>vsTop</th><th>MA</th><th>vsMA10</th><th>MACD</th><th>KDJ-J</th><th>5d(e8)</th><th>Streak</th><th>Vol-Price</th><th>Dragon-Tiger</th><th>Tactic</th><th>Score</th></tr></thead>
<tbody>{by_theme}</tbody></table></div>
<div class="note" style="margin-top:10px"><b>Legend:</b> VolR &gt;1.5 red = heavy vol, &lt;0.8 green = dry; Turn in %; MA ✓ = MA5&gt;10&gt;20; vsMA10 = deviation% (near 0 = pulled back to line); MACD R/G histogram; KDJ-J &gt;80 overbought, &lt;20 oversold; 5d(e8) = net institutional inflow over 5 sessions (1e8 ≈ 100M CNY); Streak = consecutive net-inflow days; Score = capital30 + position22 + vol-price20 + MA12 + MACD8 + hot-money8.{fail_txt}</div>
</section>

<section>
<div class="sec-h"><span class="n">08</span><h2>Risk discipline</h2></div>
<div class="grid2">
<div class="warn-box"><b>① Volume-price divergence is the deadliest</b><br>"Rise on shrinking vol" = pushed up without volume, institutions unwilling; "high + heavy vol" = distribution. Avoid rows flagged ⚠.</div>
<div class="warn-box"><b>② Ambush needs a catalyst</b><br>Low-position accumulation can grind sideways for weeks; wait for the sentiment to warm (new ladder leader / seal back above 75%) before it fires.</div>
<div class="warn-box"><b>③ Chase the seal, not the percent</b><br>Only board low-position first boards with a big seal and few breaks; a high one-word board is the end of the relay — disagreement = trap.</div>
<div class="warn-box"><b>④ Data freshness</b><br>price = {price_date}; vol/turnover/MACD anchored {vp_date}, institutional flow {mf_date}{vp_lag}. Derived data fully lands after the EOD batch (~18:00 CST); intraday runs will miss values — re-run after close.</div>
</div></section>

</div>
<footer>
<p>📊 {title} · youzi-scan · liquidity × pattern × capital × technicals · DataHub(tushare) · {date}</p>
<p style="margin-top:6px">⚠️ Disclaimer: this is a structured capital/volume/technical scan for research and education. <b>Not investment advice.</b> Indicators are computed by the script from tushare data; verify against the raw tape before any decision. Trading is risky; you are responsible for your own decisions.</p>
</footer>
</body></html>'''
    d = os.path.dirname(os.path.abspath(out_file))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_file, "w") as fobj:
        fobj.write(html)
    return out_file


if __name__ == "__main__":
    import sys
    rows = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else json.load(open("/tmp/youzi_scored.json"))
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/youzi_test_report.html"
    print(render(rows, out))
