# -*- coding: utf-8 -*-
"""
Bilingual HTML report renderer. render(..., lang="zh") — defaults to Chinese (A-share market);
pass lang="en" for English. scan.py passes STABLE KEYS for tactic/reason/vph; this module maps
keys -> localized labels, so one code path drives both languages.

Dark theme, A-share convention (red = up, green = down), 4 dimensions + 5 tactics.
"""
import os
import json
from collections import Counter

TAC_CSS = {"ambush": "buy", "dip": "dip", "halfway": "mid", "chase": "board", "high": "warn", "avoid": "no", "watch": "mid"}
TAC_ORDER = ["ambush", "dip", "halfway", "chase", "high", "avoid", "watch"]
THEME_ORDER = ["Memory", "Optical/CPO", "Compute Chips", "Semi Equipment", "Semi Materials",
               "CCL/Fiberglass/Resin", "PCB/Substrate", "MLCC/Passives", "Copper Foil/Connect",
               "Cooling/Power/Connector", "Software/Ecosystem", "Panel/Glass Substrate", "Other Optical/OSAT", "Other"]

L = {
"zh": {
  "tactic": {"ambush": "🟢 潜伏", "dip": "🔵 低吸", "halfway": "🟡 半路", "chase": "🔴 打板", "high": "⚠️ 高位", "avoid": "⛔ 回避", "watch": "△ 观望"},
  "pool_desc": {
    "ambush": "低位+主力连续吸筹，主升浪未启动，左侧埋伏",
    "dip": "上升趋势缩量回踩MA10不破，右侧低吸点",
    "halfway": "放量突破+换手活跃+攻击性强，板前半路上车",
    "chase": "涨停+封单强+位置不高，打板接力"},
  "reason": {
    "avoid_huge_turn": "高位巨量换手·派发嫌疑", "avoid_parabolic": "妖股末端·主升浪透支", "avoid_high_stall": "高位滞涨·资金接力衰竭",
    "chase_ok": "涨停+位置不高+换手未过热", "chase_ok_hm": "涨停+位置不高+换手未过热·有游资", "avoid_high_limit": "高位涨停·追板风险大",
    "halfway": "放量突破+换手活跃+攻击性强", "dip": "多头缩量回踩MA10不破+MACD水上",
    "ambush_quiet": "低位缩量+主力连续吸筹", "ambush_quiet_small": "低位缩量+主力连续吸筹+小盘易拉", "ambush_inflow": "低位+资金净流入",
    "high_relay": "高位接力·不追", "watch": "量价/资金信号不明确"},
  "vph": {"rise_vol": "涨放量·进攻", "rise_lowvol": "涨缩量·背离⚠", "pullback_lowvol": "缩量回踩·健康",
          "drop_vol": "放量下杀·出货⚠", "flat_lowvol": "横盘缩量·蓄势", "neutral": "量价均衡", "na": "—"},
  "theme": {"Memory": "存储", "Optical/CPO": "光模块/CPO", "Compute Chips": "算力芯片", "Semi Equipment": "半导体设备",
            "Semi Materials": "半导体材料", "CCL/Fiberglass/Resin": "CCL/玻纤/树脂", "PCB/Substrate": "PCB/载板",
            "MLCC/Passives": "MLCC/被动", "Copper Foil/Connect": "铜箔/铜连接", "Cooling/Power/Connector": "液冷/电源/连接",
            "Software/Ecosystem": "软件/算力生态", "Panel/Glass Substrate": "面板/玻璃基板", "Other Optical/OSAT": "其他光/封测", "Other": "其他"},
  "eyebrow": "游资思维 · 量价为王 · 四维立体扫描（量能/形态/资金/技术）",
  "lede_a": "只 A 股", "lede_b": "按游资真实决策逻辑取全维指标：<b>量比·换手·振幅</b>（筹码活性）+ <b>均线·BOLL·主升浪位置</b>（形态坐标）+ <b>主力净流入·连续吸筹·龙虎榜游资</b>（聪明钱）+ <b>MACD·KDJ·RSI</b>（买卖时机），按战法归入 <b>潜伏/低吸/半路/打板/回避</b>。",
  "c_data": "数据", "c_price": "价格", "c_vp": "量价/技术锚", "c_flow": "资金锚", "c_cov": "取数成功",
  "fresh_live": "🟢实时", "fresh_cache": "🟡缓存(截至{})",
  "s01": "大盘资金情绪周期（纲）", "s01d": "情绪不对，主升浪做不起来",
  "th_date": "日期", "th_up": "涨停", "th_z": "炸板", "th_seal": "封板率", "th_mb": "最高板", "th_b2": "≥2板",
  "cyc_title": "当前周期(自动判读)", "for_title": "对主升浪选手", "for_kv": "做低位启动·回避高位接力",
  "for_body": "优先 <b style=\"color:var(--down)\">🟢潜伏 + 🔵低吸</b>（主力低位吸筹/缩量回踩）；🟡半路需放量验证；🔴打板仅限低位首板且封单强。",
  "s02": "游资指标体系（取了哪些·怎么判）",
  "i1t": "① 量能·换手（命门）", "i1": "量比&lt;0.8缩量/0.8-1.5温和/&gt;1.5放量/&gt;2.5巨量；换手3-7%健康、&gt;20%过热(高位=出货)；振幅；量价配合",
  "i2t": "② 位置·形态", "i2": "主升浪累计涨幅、距80日顶、均线多头排列、距MA10/20乖离、BOLL位置、流通盘大小",
  "i3t": "③ 资金·主力", "i3": "主力净流入(1日/5日)、连续吸筹天数、盘口攻击性、龙虎榜游资席位",
  "i4t": "④ 时机·技术", "i4": "MACD红绿柱/水上水下、KDJ超买超卖、RSI强弱",
  "s03": "🟢 潜伏池 · 主力低位吸筹（左侧首选）", "s03d": "低位+缩量+连续净流入", "e03": "当前快照无潜伏标的。",
  "s04": "🔵 低吸池 · 多头缩量回踩（右侧低吸）", "s04d": "回踩MA10不破+MACD水上", "e04": "当前快照无低吸标的。",
  "s05": "🟡 半路池 · 放量突破上车", "s05d": "放量+换手活跃+攻击强", "e05": "当前快照无半路标的。",
  "s06": "🔴 打板池 · 涨停接力", "s06d": "封单强+位置不高", "e06": "当前快照无符合「低位首板+换手未过热」的打板标的（涨停多为高位一字，已归入回避）。",
  "s07": "全 {} 只 · 四维全指标总表", "s07d": "量价/形态/资金/技术/战法/评分",
  "tc": ["名称/代码", "今涨", "量比", "换手", "5日换", "振幅", "主升浪", "距顶", "流通亿", "多头", "距MA10", "MACD", "KDJ-J", "5日净亿", "吸筹", "量价", "龙虎榜", "战法", "评分"],
  "legend": "<b>读表：</b>量比&gt;1.5红=放量、&lt;0.8绿=缩量；换手%；流通亿=流通市值;「多头」✓=MA5&gt;10&gt;20；「距MA10」乖离%(接近0=回踩到位)；MACD红/绿柱；KDJ-J&gt;80超买、&lt;20超卖；「5日净亿」主力近5日净流入；评分=资金30+位置22+量价18+均线11+MACD7+游资7±盘子4。",
  "s08": "风险纪律",
  "r1t": "① 量价背离最危险", "r1": "「涨缩量」=拉高无量、主力不愿抬轿；「高位放量」=派发。表中量价标⚠的回避。",
  "r2t": "② 潜伏需等催化", "r2": "主力低位吸筹可能横盘数周，配合情绪转暖(新高度龙头/封板率回75%)再发动，否则磨人。",
  "r3t": "③ 打板看封单不看涨幅", "r3": "低位首板+大封单+炸板少才打；高位一字板是接力末端，分歧即闷杀。",
  "r4t": "④ 数据时效", "r4a": "价格=", "r4b": "；量比/换手/MACD锚", "r4c": "、主力资金锚", "r4d": "。衍生指标盘后(约18:00)才全，盘中跑会缺值，建议收盘后复刷。",
  "vp_lag": " ⚠注:量价/技术锚{0}、资金锚{1}(盘后未全)",
  "foot": "游资全维立体扫描 · 量能×形态×资金×技术四维模型 · DataHub(tushare)",
  "disc": "⚠️ 免责：本报告为资金/量价/技术结构化扫描，<b>不构成投资建议</b>。指标为脚本据tushare数据现算，决策需回原始盘口核对，自负盈亏。",
  "miss": "；缺数据 {} 只: {}",
  "v_low": "情绪数据未就绪", "v_low_d": "limit_list 盘后批跑或网关不稳，用缓存参考，待数据全后重刷。",
  "v_off": "进攻发酵期·可做主升浪", "v_off_d": "封板率{0}%、最高{1}板,赚钱效应强,主升浪正反馈成立。",
  "v_reb": "高潮后修复反弹·缺高度龙头", "v_reb_d": "涨停{0}家(峰值{1})、封板率{2}%、最高{3}板。指数或强但缺连板高度;钱在低位补涨,不在高标接力。",
  "v_ebb": "退潮/分歧期·防守为主", "v_ebb_d": "封板率仅{0}%、最高{1}板,炸板多、赚钱效应衰减;主升浪选手应观望等冰点。",
  "card": {"chg": "今日", "vr": "量比", "turn": "换手", "rally": "主升浪", "top": "距顶", "flow": "5日主力净", "streak": "连续吸筹", "ma": "均线", "macd": "MACD", "float": "流通", "bull": "多头", "nonbull": "非多头", "red": "红柱", "green": "绿柱", "hm": "｜游资 ", "days": "天", "e8": "亿"},
},
"en": {
  "tactic": {"ambush": "🟢 Ambush", "dip": "🔵 Dip", "halfway": "🟡 Halfway", "chase": "🔴 Limit-chase", "high": "⚠️ High", "avoid": "⛔ Avoid", "watch": "△ Watch"},
  "pool_desc": {
    "ambush": "Low position + sustained institutional accumulation; rally not started — left-side ambush",
    "dip": "Uptrend pullback to MA10 on low volume — right-side dip-buy",
    "halfway": "Volume breakout + active turnover + strong attack — board mid-way",
    "chase": "Limit-up + strong seal + not high — chase the board"},
  "reason": {
    "avoid_huge_turn": "High + huge turnover (distribution risk)", "avoid_parabolic": "Parabolic end (>150% rally, overextended)", "avoid_high_stall": "High + stalling (relay capital fading)",
    "chase_ok": "Limit-up + not high + turnover not overheated", "chase_ok_hm": "Limit-up + not high + turnover not overheated + hot-money", "avoid_high_limit": "High limit-up (chasing risk)",
    "halfway": "Volume breakout + active turnover + strong attack", "dip": "Uptrend pullback to MA10 on low vol + MACD above water",
    "ambush_quiet": "Low + dry volume + sustained accumulation", "ambush_quiet_small": "Low + dry volume + accumulation + small float (easy to push)", "ambush_inflow": "Low position + net institutional inflow",
    "high_relay": "High position relay (don't chase)", "watch": "Volume/capital signals unclear"},
  "vph": {"rise_vol": "Rise+Vol(attack)", "rise_lowvol": "Rise+LowVol(divergence)", "pullback_lowvol": "Pullback+LowVol(healthy)",
          "drop_vol": "Drop+Vol(distribution)", "flat_lowvol": "Flat+LowVol(coiling)", "neutral": "Neutral", "na": "-"},
  "theme": {t: t for t in THEME_ORDER},
  "eyebrow": "HOT-MONEY LENS · VOLUME FIRST · 4-D SCAN (liquidity / pattern / capital / technicals)",
  "lede_a": "A-share names", "lede_b": "scored the way a Chinese hot-money (游资) trader decides: <b>volume-ratio · turnover · amplitude</b> (chip activity) + <b>MA · BOLL · main-rally position</b> (pattern) + <b>net institutional inflow · accumulation streak · dragon-tiger seats</b> (smart money) + <b>MACD · KDJ · RSI</b> (timing), bucketed into <b>Ambush / Dip / Halfway / Limit-chase / Avoid</b>.",
  "c_data": "data", "c_price": "price", "c_vp": "vol/tech anchor", "c_flow": "flow anchor", "c_cov": "coverage",
  "fresh_live": "🟢 live", "fresh_cache": "🟡 cached (asof {})",
  "s01": "Market sentiment cycle (the gate)", "s01d": "no rally without the right mood",
  "th_date": "Date", "th_up": "Limit-ups", "th_z": "Broken", "th_seal": "Seal%", "th_mb": "Top boards", "th_b2": "≥2 boards",
  "cyc_title": "Cycle read (auto)", "for_title": "For main-rally traders", "for_kv": "play low-position starts · avoid high relays",
  "for_body": "Prefer <b style=\"color:var(--down)\">🟢 Ambush + 🔵 Dip</b> (institutions accumulating low / low-vol pullback); 🟡 Halfway needs a volume confirmation; 🔴 Limit-chase only on low-position first boards with a strong seal.",
  "s02": "The indicator system (what we pull, how we judge)",
  "i1t": "① Liquidity · turnover (the core)", "i1": "vol-ratio &lt;0.8 dry / 0.8-1.5 mild / &gt;1.5 heavy / &gt;2.5 huge; turnover 3-7% healthy, &gt;20% overheated (high = distribution); amplitude; volume-price health",
  "i2t": "② Position · pattern", "i2": "cumulative rally %, distance from 80-day top, MA bull alignment, MA10/20 deviation, BOLL position, float size",
  "i3t": "③ Capital · institutions", "i3": "net institutional inflow (1d/5d), accumulation streak, order-book strength, dragon-tiger hot-money seats",
  "i4t": "④ Timing · technicals", "i4": "MACD red/green & above/below water, KDJ overbought/oversold, RSI strength",
  "s03": "🟢 Ambush pool · institutions accumulating low (top pick)", "s03d": "low + dry volume + sustained inflow", "e03": "No ambush candidates in this snapshot.",
  "s04": "🔵 Dip pool · bull pullback on low volume", "s04d": "pullback to MA10 + MACD above water", "e04": "No dip candidates in this snapshot.",
  "s05": "🟡 Halfway pool · board on a volume breakout", "s05d": "heavy volume + active turnover + strong attack", "e05": "No halfway candidates in this snapshot.",
  "s06": "🔴 Limit-chase pool · board the limit-up", "s06d": "strong seal + not high", "e06": "No qualifying low-position first-board limit-ups (most are high one-word boards → Avoid).",
  "s07": "All {} names · full 4-D table", "s07d": "liquidity / pattern / capital / technicals / tactic / score",
  "tc": ["Name/Code", "Chg", "VolR", "Turn", "Turn5", "Ampl", "Rally", "vsTop", "Float", "MA", "vsMA10", "MACD", "KDJ-J", "5d(e8)", "Streak", "Vol-Price", "Dragon-Tiger", "Tactic", "Score"],
  "legend": "<b>Legend:</b> VolR &gt;1.5 red = heavy, &lt;0.8 green = dry; Turn %; Float = circulating cap (e8 CNY); MA ✓ = MA5&gt;10&gt;20; vsMA10 deviation%; MACD R/G; KDJ-J &gt;80 overbought, &lt;20 oversold; 5d(e8) = net institutional inflow over 5 sessions; Score = capital30 + position22 + vol-price18 + MA11 + MACD7 + hot-money7 ± float4.",
  "s08": "Risk discipline",
  "r1t": "① Volume-price divergence is deadliest", "r1": "\"Rise on shrinking vol\" = pushed up without volume; \"high + heavy vol\" = distribution. Avoid rows flagged ⚠.",
  "r2t": "② Ambush needs a catalyst", "r2": "Low-position accumulation can grind sideways for weeks; wait for sentiment to warm (new ladder leader / seal back above 75%).",
  "r3t": "③ Chase the seal, not the percent", "r3": "Only board low-position first boards with a big seal and few breaks; a high one-word board is the end of the relay.",
  "r4t": "④ Data freshness", "r4a": "price = ", "r4b": "; vol/turnover/MACD anchored ", "r4c": ", institutional flow ", "r4d": ". Derived data fully lands after the EOD batch (~18:00 CST); intraday runs miss values — re-run after close.",
  "vp_lag": " — NB: vol/tech anchored {0}, flow {1} (EOD not fully landed)",
  "foot": "youzi-scan · liquidity × pattern × capital × technicals · DataHub(tushare)",
  "disc": "⚠️ Disclaimer: a structured capital/volume/technical scan for research/education. <b>Not investment advice.</b> Verify against the raw tape before any decision; you are responsible for your own trades.",
  "miss": "; missing {}: {}",
  "v_low": "Sentiment data not ready", "v_low_d": "limit_list EOD batch / gateway not serving; using cache, refresh later.",
  "v_off": "Offensive / building — rally-tradeable", "v_off_d": "Seal {0}%, top {1} boards; strong money effect, the main-rally loop holds.",
  "v_reb": "Rebound after climax — lacks a high-ladder leader", "v_reb_d": "{0} limit-ups (peak {1}), seal {2}%, top {3} boards. Money rotates into low laggards, not high relays.",
  "v_ebb": "Ebb / divergence — defensive", "v_ebb_d": "Seal only {0}%, top {1} boards; many broken boards, money effect fading. Wait for a colder reset.",
  "card": {"chg": "Chg", "vr": "Vol-ratio", "turn": "Turnover", "rally": "Rally", "top": "vs Top", "flow": "5d Inflow", "streak": "Streak", "ma": "MA", "macd": "MACD", "float": "Float", "bull": "bull", "nonbull": "non-bull", "red": "red", "green": "green", "hm": "｜hot-money ", "days": "d", "e8": "e8"},
},
}


def _n(x, d=0):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "—"


def _chgcls(c):
    return 'up' if (c or 0) > 0 else ('down' if (c or 0) < 0 else 'flat')


def _vrcls(v):
    return 'up' if (v or 0) > 1.5 else ('down' if (v is not None and v < 0.8) else 'flat')


def _vphcls(k):
    if k in ("rise_vol", "pullback_lowvol", "flat_lowvol"):
        return 'good'
    if k in ("rise_lowvol", "drop_vol"):
        return 'bad'
    return 'mid'


def sentiment_verdict(sent, T):
    valid = [s for s in sent if s.get("up")]
    if len(valid) < 2:
        return T["v_low"], T["v_low_d"]
    ups = [s["up"] for s in valid]
    last = valid[-1]
    peak = max(ups)
    seal = last.get("seal") or 0
    mb = last.get("mb") or 0
    trend_up = len(ups) >= 2 and ups[-1] > ups[-2]
    if seal >= 75 and mb >= 6 and trend_up:
        return T["v_off"], T["v_off_d"].format(seal, mb)
    if seal >= 65:
        return T["v_reb"], T["v_reb_d"].format(last["up"], peak, seal, mb)
    return T["v_ebb"], T["v_ebb_d"].format(seal, mb)


def _card(r, T):
    cls = TAC_CSS.get(r["tactic"], "mid")
    hm = (T["card"]["hm"] + '·'.join(r['hm'])) if r.get('hm') else ''
    net5 = (r.get('net5') or 0) / 10000
    ma = T["card"]["bull"] if r.get("ma_bull") == 1 else T["card"]["nonbull"]
    macdst = T["card"]["red"] if (r.get("macd") or 0) > 0 else T["card"]["green"]
    cd = T["card"]
    reason = T["reason"].get(r.get("reason", ""), r.get("reason", ""))
    return f'''<div class="pick p-{cls}">
<div class="pk-h"><span class="pk-nm">{r['name']}</span><span class="pk-code">{r['code']}</span>
<span class="pk-score">{r.get('score','')}</span><span class="pk-th">{T["theme"].get(r['theme'], r['theme'])}</span></div>
<div class="pk-grid">
<div class="pk-m"><div class="l">{cd['chg']}</div><div class="v {_chgcls(r.get('chg'))}">{_n(r.get('chg'),1)}%</div></div>
<div class="pk-m"><div class="l">{cd['vr']}</div><div class="v {_vrcls(r.get('vol_ratio'))}">{_n(r.get('vol_ratio'),2)}</div></div>
<div class="pk-m"><div class="l">{cd['turn']}</div><div class="v">{_n(r.get('turn'),1)}%</div></div>
<div class="pk-m"><div class="l">{cd['rally']}</div><div class="v">+{_n(r.get('cum80'),0)}%</div></div>
<div class="pk-m"><div class="l">{cd['top']}</div><div class="v">{_n(r.get('dtop'),0)}%</div></div>
<div class="pk-m"><div class="l">{cd['flow']}</div><div class="v {'up' if net5>=0 else 'down'}">{('+' if net5>=0 else '')}{net5:.1f}{cd['e8']}</div></div>
<div class="pk-m"><div class="l">{cd['streak']}</div><div class="v">{r.get('streak',0)}{cd['days']}</div></div>
<div class="pk-m"><div class="l">{cd['float']}</div><div class="v">{_n(r.get('float_mv'),0)}</div></div>
<div class="pk-m"><div class="l">{cd['macd']}</div><div class="v">{macdst}</div></div>
</div>
<div class="pk-vph vph-{_vphcls(r.get('vph','na'))}">{T["vph"].get(r.get('vph','na'),'—')}</div>
<div class="pk-logic">▶ {reason}{hm}</div></div>'''


def _pool_table(rows, tactic, lang):
    """Tactic pool as a compact comparison TABLE (not cards) — easier to scan side by side."""
    T = L[lang]
    zh = lang != "en"
    rs = sorted([r for r in rows if r["tactic"] == tactic], key=lambda x: -x.get("score", 0))
    if not rs:
        return ""
    cols = (["名称/代码", "评分", "板块", "今涨", "量比", "换手", "主升浪", "距顶", "5日净亿", "吸筹", "量价", "买入逻辑"] if zh
            else ["Name", "Score", "Sector", "Chg", "VolR", "Turn", "Rally", "vsTop", "5d(e8)", "Streak", "Vol-Price", "Logic"])
    trs = ""
    for r in rs:
        net5 = (r.get('net5') or 0) / 10000
        reason = T["reason"].get(r.get("reason", ""), r.get("reason", ""))
        hm = ('｜' + '·'.join(r['hm'])) if r.get('hm') else ''
        streak = r.get('streak', 0)
        trs += (f'<tr><td class="nm">{r["name"]}<small>{r["code"]}</small></td>'
                f'<td class="num"><b>{r.get("score","")}</b></td>'
                f'<td>{T["theme"].get(r["theme"], r["theme"])}</td>'
                f'<td class="num {_chgcls(r.get("chg"))}">{_n(r.get("chg"),1)}%</td>'
                f'<td class="num {_vrcls(r.get("vol_ratio"))}">{_n(r.get("vol_ratio"),2)}</td>'
                f'<td class="num">{_n(r.get("turn"),1)}</td>'
                f'<td class="num">+{_n(r.get("cum80"),0)}%</td>'
                f'<td class="num">{_n(r.get("dtop"),0)}%</td>'
                f'<td class="num {"up" if net5>=0 else "down"}">{("+" if net5>=0 else "")}{net5:.1f}</td>'
                f'<td class="c">{("连"+str(streak)) if streak>=3 else (str(streak) if streak else "·")}</td>'
                f'<td class="vph vph-{_vphcls(r.get("vph","na"))}">{T["vph"].get(r.get("vph","na"),"—")}</td>'
                f'<td style="white-space:normal;max-width:230px;color:var(--txt2)">{reason}{hm}</td></tr>')
    th = "".join(f"<th>{c}</th>" for c in cols)
    return f'<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def _section_cards(rows, key, T):
    rs = sorted([r for r in rows if r["tactic"] == key], key=lambda x: -x.get("score", 0))
    if not rs:
        return ""
    n_label = (str(len(rs)) + (" stocks" if T is L["en"] else " 只"))
    return f'<div class="tac-desc">{T["pool_desc"][key]} · {n_label}</div><div class="picks">' + ''.join(_card(r, T) for r in rs) + '</div>'


def _full_row(r, T):
    cls = TAC_CSS.get(r["tactic"], "mid")
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
<td class="num">{_n(r.get('float_mv'),0)}</td>
<td class="c">{bull}</td>
<td class="num">{_n(r.get('above_ma10'),1)}</td>
<td class="c">{macd}</td>
<td class="num {kdjcls}">{_n(r.get('kdj_j'),0)}</td>
<td class="num {'up' if net5>=0 else 'down'}">{('+' if net5>=0 else '')}{net5:.1f}</td>
<td class="c">{('x'+str(streak)) if streak>=3 else (str(streak) if streak else '·')}</td>
<td class="vph vph-{_vphcls(r.get('vph','na'))}">{T["vph"].get(r.get('vph','na'),'—')}</td>
<td class="c">{('★'+'·'.join(r['hm'][:2])) if r.get('hm') else '·'}</td>
<td class="tac t-{cls}">{T["tactic"].get(r['tactic'], r['tactic'])}</td>
<td class="num"><b>{r.get('score','')}</b></td>
</tr>'''


SETUP_EN = {"低吸/回踩MA10": "Dip/MA10 pullback", "打板/涨停": "Limit-up board", "突破新高": "Breakout high",
            "潜伏/低位缩量": "Ambush/low dry-vol", "半路/放量": "Halfway/vol-spike"}
# Exact definitions mirroring pattern_mine.label_setup (no hand-waving — these ARE the rules).
SETUP_DEF = {
    "打板/涨停": "当日涨幅 ≥ 9.5%（涨停）",
    "突破新高": "收盘创 20 日新高 且 当日涨幅 > 2%",
    "半路/放量": "当日涨 2~9% 且 量比 ≥ 1.8（放量突破）",
    "低吸/回踩MA10": "多头排列(MA5>10>20) 且 收盘在 MA10 ±2.5% 且 当日涨幅 ≤ 1%（缩量回踩）",
    "潜伏/低位缩量": "20日区间位置 ≤ 35%（低位）且 量比 ≤ 0.9（缩量横盘）",
}
SETUP_DEF_EN = {
    "打板/涨停": "day return ≥ 9.5% (limit-up)",
    "突破新高": "close = 20d high & day return > 2%",
    "半路/放量": "day +2~9% & vol-ratio ≥ 1.8",
    "低吸/回踩MA10": "MA bull & close within MA10 ±2.5% & day ≤ 1%",
    "潜伏/低位缩量": "20d range pos ≤ 35% & vol-ratio ≤ 0.9",
}
# East Money (东方财富) concept-flavored Chinese names for our English theme keys.
CONCEPT_ZH = {
    "Memory": "存储芯片", "Optical/CPO": "CPO/光模块", "Compute Chips": "算力芯片/国产GPU",
    "Semi Equipment": "半导体设备", "Semi Materials": "半导体材料", "CCL/Fiberglass/Resin": "覆铜板/PCB上游",
    "PCB/Substrate": "PCB/IC载板", "MLCC/Passives": "MLCC/被动元件", "Copper Foil/Connect": "铜箔/连接器",
    "Cooling/Power/Connector": "液冷/电源", "Software/Ecosystem": "AI算力/服务器",
    "Panel/Glass Substrate": "玻璃基板", "Other Optical/OSAT": "先进封装", "Other": "其他概念",
}
HORIZON_COLS = [("t1", "T+1"), ("t3", "T+3"), ("t5", "T+5"), ("t10", "T+10"), ("t20", "T+20·1月"), ("t60", "T+60·3月")]


def _hcell(h):
    """A horizon cell: win% + avg. Null-safe."""
    if not h:
        return '<td class="num" style="color:var(--txt3)">—</td>'
    cls = "up" if h["win"] >= 60 else ("down" if h["win"] < 45 else "")
    return f'<td class="num"><b class="{cls}">{h["win"]}%</b> <span style="color:var(--txt3)">{h["avg"]:+.0f}</span></td>'


def _macro_section(macro, lang):
    """Renders the top-down funnel layers 01 global / 02 overseas / 03 A-share / 05 capital."""
    if not macro:
        return ""
    zh = lang != "en"
    def L1(z, e):
        return z if zh else e
    out = ""
    # 01 全球宏观与重大事件
    gn = macro.get("global_news", [])
    if gn:
        news = "".join(f'<div class="news-row"><span class="news-tag">{n["tag"]}</span>{n["t"]}</div>' for n in gn)
        out += f'''<section><div class="sec-h"><span class="n">01</span><h2>{L1("全球宏观与重大事件","Global macro & events")}</h2><span class="desc">{L1("最广镜头:决定全球风险偏好","widest lens · risk appetite")}</span></div>
<div class="kbox red">{news}</div></section>'''
    # 02 外盘·美股AI科技
    ov = macro.get("overseas")
    if ov:
        idx = "".join(f'<span class="chip"><b>{g["name"]}</b> {g["val"]} <span style="color:var(--txt3)">{g["note"]}</span></span>' for g in ov.get("idx", []))
        out += f'''<section><div class="sec-h"><span class="n">02</span><h2>{L1("外盘 · 美股AI科技传导","Overseas · US AI/tech")}</h2><span class="desc">{L1("隔夜美股=我们开盘的情绪底色","overnight US sets the tone")}</span></div>
<div class="mac-row">{idx}</div>
<div class="kbox" style="margin-top:8px"><div class="kl">{L1("AI/半导体动向","AI/semis")}</div><div style="font-size:12px;color:var(--txt2)">{ov.get("ai","")}</div></div>
<div class="note" style="margin-top:8px"><b>{L1("解读","Read")}:</b> {ov.get("read","")}</div></section>'''
    # 03 A股大盘复盘
    asx = macro.get("ashare")
    if asx:
        idx = "".join(f'<span class="chip"><b>{i["name"]}</b> {i["close"]} <span class="{"up" if (i["pct"] or 0)>0 else "down"}">{i["pct"]:+}%</span></span>' for i in asx.get("idx", []))
        nb = asx.get("northbound", "")
        out += f'''<section><div class="sec-h"><span class="n">03</span><h2>{L1("A股大盘复盘","A-share index review")}</h2><span class="desc">{L1("回到主场:指数/北向/风格","home market · style")}</span></div>
<div class="mac-row">{idx}</div>
{f'<div class="note" style="margin-top:8px"><b>{L1("北向","Northbound")}:</b> {nb}</div>' if nb else ''}
<div class="kbox gold" style="margin-top:8px"><div class="kl">{L1("解读","Read")}</div><div style="font-size:12px;color:var(--txt2)">{asx.get("read","")}</div></div></section>'''
    return out


def _capital_section(macro, lang):
    """Funnel layer 05: capital flows (sector money-flow rotation)."""
    if not macro or not macro.get("sector_flow"):
        return ""
    zh = lang != "en"
    sf = macro["sector_flow"]
    chips = "".join(f'<span class="chip"><b>{s["name"]}</b> <span class="{"up" if (s["pct"] or 0)>0 else "down"}">{s["pct"]:+}%</span> <span style="color:var(--gold)">净{s["net"]}亿</span></span>' for s in sf)
    read = macro.get("sector_read", "")
    h = "资金面 · 板块主力流向" if zh else "Capital · sector money flow"
    d = "钱往哪轮动 = 主攻方向" if zh else "where money rotates"
    return f'''<section><div class="sec-h"><span class="n">05</span><h2>{h}</h2><span class="desc">{d}</span></div>
<div class="mac-row" style="margin-bottom:8px">{chips}</div>
<div class="warn-box">{read}</div></section>'''


def _patterns_section(patterns, lang):
    if not patterns:
        return ""
    zh = lang != "en"
    def setlabel(s):
        return s if zh else SETUP_EN.get(s, s)
    def sectorlabel(th):
        return CONCEPT_ZH.get(th, th) if zh else th
    h_title = "最佳赚钱模式 · 真实回测" if zh else "Best patterns · real backtest"
    h_desc = (f"{patterns.get('n_samples')}样本 / {patterns.get('n_stocks')}只 / {patterns.get('window_days')}天窗口 · 信号日收盘买入持有N天" if zh
              else f"{patterns.get('n_samples')} samples / {patterns.get('n_stocks')} stocks / {patterns.get('window_days')}d")
    hcols = "".join(f"<th>{lab}</th>" for _, lab in HORIZON_COLS)

    # ① 模式定义
    DEF = SETUP_DEF if zh else SETUP_DEF_EN
    defs = "".join(f'<div class="news-row"><span class="news-tag">{setlabel(s)}</span>{d}</div>' for s, d in DEF.items())

    # ② 按模式(多窗口)
    srows = ""
    for s, st in sorted(patterns.get("by_setup", {}).items(), key=lambda kv: -((kv[1].get("t3") or {"win": 0})["win"])):
        srows += f'<tr><td><b>{setlabel(s)}</b></td><td class="num">{st["n"]}</td>' + "".join(_hcell(st.get(hk)) for hk, _ in HORIZON_COLS) + "</tr>"

    # ③ 模式×板块×个股 组合(3-10)
    crows = ""
    for bc in patterns.get("best_combos", [])[:10]:
        stocks = "、".join(f'{x["name"]}<span style="color:var(--txt3)">({x["t3_win"]}%)</span>' for x in bc.get("stocks", [])[:4] if x.get("t3_win") is not None)
        crows += (f'<tr><td><b>{setlabel(bc["setup"])}</b></td><td><span class="news-tag">{sectorlabel(bc["theme"])}</span></td>'
                  f'<td style="white-space:normal;max-width:280px">{stocks}</td><td class="num">{bc["n"]}</td>'
                  + "".join(_hcell(bc.get(hk)) for hk, _ in HORIZON_COLS) + "</tr>")

    L1 = (lambda z, e: z if zh else e)
    return f'''<section>
<div class="sec-h"><span class="n">▲</span><h2>{h_title}</h2><span class="desc">{h_desc}</span></div>
<div class="kbox" style="margin-bottom:10px"><div class="kl">{L1("模式定义(与回测代码一致)","Setup definitions")}</div>{defs}</div>
<div style="font-size:12px;color:var(--cyan);font-weight:700;margin:10px 0 5px">{L1("① 按入场模式 · 各持有窗口胜率/均值","① By setup · win/avg per horizon")}</div>
<div class="tbl-wrap"><table><thead><tr><th>{L1("入场模式","Setup")}</th><th>{L1("样本","n")}</th>{hcols}</tr></thead><tbody>{srows}</tbody></table></div>
<div style="font-size:12px;color:var(--cyan);font-weight:700;margin:14px 0 5px">{L1("② 最佳「模式 × 板块 × 个股」组合(按T+3胜率)","② Best setup × sector × stock")}</div>
<div class="tbl-wrap"><table><thead><tr><th>{L1("模式","Setup")}</th><th>{L1("板块(东财概念)","Sector")}</th><th>{L1("代表个股(括号=该票T+3胜率)","Stocks (T+3 win)")}</th><th>{L1("样本","n")}</th>{hcols}</tr></thead><tbody>{crows}</tbody></table></div>
<div class="note" style="margin-top:8px">{L1("胜率=该模式样本中收正比例,均值=平均收益%;红≥60%、绿&lt;45%。T+60(3月)样本较少(需足够前向交易日),仅供趋势参考。","win=% positive, avg=mean %.")}</div></section>'''


def _pullback_section(pullback, lang):
    """潜在低吸埋伏: strong uptrend names not yet pulled back -> their MA5/MA10 dip-buy target prices.
    Answers 'these strong stocks rarely touch MA10 — if they gap down to X tomorrow, that's the low-buy'."""
    if not pullback or not pullback.get("candidates"):
        return ""
    zh = lang != "en"
    L1 = (lambda z, e: z if zh else e)
    cands = pullback["candidates"][:15]
    trs = ""
    for r in cands:
        net5 = (r.get("net5") or 0) / 10000
        # suggested dip zone: shallow pullback (MA5) for very strong; deeper (MA10) otherwise
        zone = f'MA5 {r["ma5"]}' if abs(r.get("to_ma5", 0)) <= 6 else f'MA5~MA10 {r["ma5"]}~{r["ma10"]}'
        trs += (f'<tr><td class="nm">{r["name"]}<small>{r["code"]}</small></td>'
                f'<td class="num">{r["price"]}</td>'
                f'<td>{CONCEPT_ZH.get(r["theme"], r["theme"]) if zh else r["theme"]}</td>'
                f'<td class="num">+{_n(r.get("cum80"),0)}%</td>'
                f'<td class="num"><b class="down">{r["to_ma5"]}%</b><br><span style="color:var(--txt3)">{r["ma5"]}</span></td>'
                f'<td class="num"><b class="down">{r["to_ma10"]}%</b><br><span style="color:var(--txt3)">{r["ma10"]}</span></td>'
                f'<td class="num {"up" if net5>=0 else "down"}">{("+" if net5>=0 else "")}{net5:.1f}</td>'
                f'<td class="num"><b>{r.get("score","")}</b></td>'
                f'<td style="color:var(--g-buy);font-weight:600">{zone}</td></tr>')
    cols = [L1("强势股","Stock"), L1("现价","Px"), L1("板块(东财)","Sector"), L1("主升浪","Rally"),
            L1("回踩MA5(目标价)","to MA5"), L1("回踩MA10(目标价)","to MA10"), L1("5日净亿","5d"), L1("评分","Score"), L1("建议低吸位","Buy zone")]
    th = "".join(f"<th>{c}</th>" for c in cols)
    return f'''<section>
<div class="sec-h"><span class="n">◈</span><h2>{L1("潜在低吸埋伏 · 回踩目标价","Pullback ambush · dip targets")}</h2><span class="desc">{L1("强势股很少踩MA10→推演:跌到哪是低吸点","project the dip-buy price")}</span></div>
<div class="note" style="margin-bottom:8px">{L1("逻辑:最近强势股很少回踩MA10(甚至MA5都少破),静态「低吸池」常为空。这里反向推演——对<b>多头排列、当前在MA10上方、资金仍在</b>的强势股,算出它<b>回踩MA5/MA10的目标价</b>:<b>如果明天低开/回踩到「建议低吸位」就是好的低吸点</b>,挂单或盯盘埋伏。负数=需要下跌的幅度。","If a strong name gaps down to its MA5/MA10, that's the dip-buy. Negative = drop needed.")}</div>
<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div></section>'''


def _next_batch_section(rows, patterns, lang):
    """CLOSE THE LOOP: which stocks are TODAY firing a historically high-win pattern = next batch.
    Join each actionable stock's CURRENT setup × its sector against the backtest win rates."""
    if not patterns:
        return ""
    zh = lang != "en"
    T2S = {"ambush": "潜伏/低位缩量", "dip": "低吸/回踩MA10", "halfway": "半路/放量", "chase": "打板/涨停"}
    by_combo = patterns.get("by_combo", {})
    by_setup = patterns.get("by_setup", {})
    T = L[lang]
    cands = []
    for r in rows:
        setup = T2S.get(r["tactic"])
        if not setup:
            continue  # only actionable setups (skip high/avoid/watch)
        combo = by_combo.get(f"{setup} @ {r['theme']}")
        src = combo or by_setup.get(setup)
        if not src:
            continue
        t3 = (src.get("t3") or {}).get("win")
        t20 = (src.get("t20") or {}).get("win")
        t20a = (src.get("t20") or {}).get("avg")
        cands.append({**r, "bt_setup": setup, "bt_t3": t3, "bt_t20": t20, "bt_t20a": t20a, "bt_combo": combo is not None})
    if not cands:
        return ""
    cands.sort(key=lambda x: (-(x["bt_t20"] or 0), -(x["bt_t3"] or 0), -x.get("score", 0)))
    top = cands[:15]
    def sl(s):
        return s if zh else SETUP_EN.get(s, s)
    trs = ""
    for i, r in enumerate(top, 1):
        net5 = (r.get('net5') or 0) / 10000
        scope = "板块级" if r["bt_combo"] else "模式级"
        if not zh:
            scope = "sector" if r["bt_combo"] else "setup"
        trs += (f'<tr><td class="num">{i}</td><td class="nm">{r["name"]}<small>{r["code"]}</small></td>'
                f'<td><span class="news-tag">{sl(r["bt_setup"])}</span></td>'
                f'<td>{CONCEPT_ZH.get(r["theme"], r["theme"]) if zh else r["theme"]}</td>'
                f'<td class="num"><b>{r["bt_t3"]}%</b></td>'
                f'<td class="num"><b class="{"up" if (r["bt_t20"] or 0)>=65 else ""}">{r["bt_t20"]}%</b> <span style="color:var(--txt3)">{("+"+str(int(r["bt_t20a"]))) if r.get("bt_t20a") is not None else ""}</span></td>'
                f'<td class="c" style="font-size:9px;color:var(--txt3)">{scope}</td>'
                f'<td class="num"><b>{r.get("score","")}</b></td>'
                f'<td class="num {"up" if net5>=0 else "down"}">{("+" if net5>=0 else "")}{net5:.1f}</td>'
                f'<td class="vph vph-{_vphcls(r.get("vph","na"))}">{T["vph"].get(r.get("vph","na"),"—")}</td></tr>')
    L1 = (lambda z, e: z if zh else e)
    cols = ([L1("#", "#"), L1("票", "Stock"), L1("今日模式", "Setup today"), L1("板块(东财)", "Sector"),
             "T+3", L1("T+20·1月", "T+20"), L1("胜率口径", "scope"), L1("当前评分", "Score"),
             L1("5日净亿", "5d(e8)"), L1("量价", "Vol-Price")])
    th = "".join(f"<th>{c}</th>" for c in cols)
    return f'''<section>
<div class="sec-h"><span class="n">▶</span><h2>{L1("下一批候选 · 回测×今日联立","Next batch · backtest × today")}</h2><span class="desc">{L1("今天正在触发历史高胜率模式的票","stocks firing a historically winning pattern today")}</span></div>
<div class="note" style="margin-bottom:8px">{L1("闭环逻辑:每只票的<b>今日模式</b>(扫描)× 它的<b>板块</b> → 查<b>回测</b>里该「模式×板块」历史胜率 → 排序。「板块级」=有该板块足够样本,「模式级」=用全模式胜率兜底。<b>这才是回测的目的:不是复盘历史,是锁定下一批。</b>","Join today's setup × sector against backtest win-rates.")}</div>
<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div></section>'''


def _top10_section(rows, lang):
    zh = lang != "en"
    LB = {"h": "TOP10 精选" if zh else "TOP10 picks", "d": "综合评分前10(潜伏/低吸优先)" if zh else "by composite score"}
    # prefer actionable tactics, then score
    rank = {"ambush": 0, "dip": 1, "halfway": 2, "chase": 3, "watch": 4, "high": 5, "avoid": 6}
    top = sorted(rows, key=lambda r: (rank.get(r["tactic"], 9), -r.get("score", 0)))[:10]
    cards = ""
    for i, r in enumerate(top, 1):
        cards += f'<div class="t10"><span class="t10-r">{i}</span>{_card(r, L[lang])}</div>'
    return f'''<section>
<div class="sec-h"><span class="n">★</span><h2>{LB["h"]}</h2><span class="desc">{LB["d"]}</span></div>
<div class="picks">{cards}</div></section>'''


def _exec_summary(conclusion, lang):
    """Section 00. The conclusion is written by the AGENT from the real data (not a template).
    `conclusion` is an HTML/markdown-ish string. Empty -> a neutral placeholder (never fabricate)."""
    head = "结论先行 · 操作纲领" if lang != "en" else "Executive summary"
    if not conclusion or not conclusion.strip():
        ph = ("(待 agent 基于本报告的真实数据撰写结论——脚本不臆造)" if lang != "en"
              else "(to be written by the agent from the data below — the script does not fabricate)")
        body = f'<div style="color:var(--txt3);font-style:italic">{ph}</div>'
    else:
        # allow simple line breaks; the agent supplies the analytical narrative
        body = conclusion.replace("\n\n", "</p><p>").replace("\n", "<br>")
        body = f'<div style="font-size:12.5px;color:var(--txt);line-height:1.75"><p>{body}</p></div>'
    return f'''<section>
<div class="sec-h"><span class="n">00</span><h2>{head}</h2></div>
<div class="kbox red" style="border-left-width:4px">{body}</div></section>'''


def render(rows, out_file, title="AI Compute Chain", date="2026-06-16",
           sentiment=None, sent_asof=None, sent_fresh=False, stats=None, freshness=None, lang="zh",
           macro=None, patterns=None, conclusion=None, pullback=None):
    T = L.get(lang, L["zh"])
    sentiment = sentiment or []
    stats = stats or {}
    freshness = freshness or {}
    cnt = Counter(r["tactic"] for r in rows)

    def cc(t):
        return cnt.get(t, 0)

    by_theme = ""
    for th in THEME_ORDER:
        rs = [r for r in rows if r.get('theme') == th]
        if not rs:
            continue
        rs = sorted(rs, key=lambda x: -x.get('score', 0))
        by_theme += f'<tr class="grp"><td colspan="19">▎{T["theme"].get(th, th)} ({len(rs)})</td></tr>\n' + '\n'.join(_full_row(r, T) for r in rs) + '\n'

    sent_rows = ""
    for s in sentiment:
        seal = f"{s['seal']}%" if s.get('seal') else "—"
        mb = f"{s['mb']}" if s.get('mb') else "—"
        b2 = s.get('b2') if s.get('b2') is not None else "—"
        z = s.get('z') if s.get('z') is not None else "—"
        sent_rows += f'<tr><td class="mono">{s["d"]}</td><td class="num">{s.get("up","—")}</td><td class="num">{z}</td><td class="num">{seal}</td><td class="num">{mb}</td><td class="num">{b2}</td></tr>'
    v_head, v_detail = sentiment_verdict(sentiment, T)
    fresh_badge = T["fresh_live"] if sent_fresh else T["fresh_cache"].format(sent_asof)

    vp_date = freshness.get("vp_date", "—")
    mf_date = freshness.get("mf_date", "—")
    price_date = freshness.get("price_date", date)
    mode_lbl = freshness.get("mode", "")
    mode_chip = f'<span class="chip" style="border-color:var(--cyan);color:var(--cyan)"><b>{mode_lbl}</b></span>' if mode_lbl else ''
    vp_lag = "" if vp_date == date else T["vp_lag"].format(vp_date, mf_date)
    tot = stats.get("total", len(rows))
    succ = f"price{stats.get('price',0)} pos{stats.get('cum80',0)} flow{stats.get('net5',0)} vp{stats.get('turn',0)} tech{stats.get('macd',0)} /{tot}"
    failed = stats.get("failed", [])
    fail_txt = T["miss"].format(len(failed), ', '.join(failed[:8]) + ('…' if len(failed) > 8 else '')) if failed else ""

    pools = {t: _pool_table(rows, t, lang) for t in ["ambush", "dip", "halfway", "chase"]}
    tc = T["tc"]
    sec00 = _exec_summary(conclusion, lang)                          # 00 结论先行(agent撰写)
    sec_macro = _macro_section(macro, lang)                          # 01 全球 / 02 外盘 / 03 大盘
    sec_capital = _capital_section(macro, lang)                      # 05 资金面
    sec_patterns = _patterns_section(patterns, lang)                 # 06 回测
    sec_nextbatch = _next_batch_section(rows, patterns, lang)        # 06b 下一批候选(闭环)
    sec_pullback = _pullback_section(pullback, lang)                 # 06c 潜在低吸埋伏(回踩目标价)
    sec_top10 = _top10_section(rows, lang)                           # 08 TOP10

    html = f'''<!DOCTYPE html><html lang="{lang}"><head><meta charset="UTF-8">
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
.wrap{{padding:24px 28px 60px;max-width:1520px;margin:0 auto;}}
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
.kbox.red{{border-left-color:var(--up);}}
.mac-row{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:7px;}}
.mac-l{{font-size:11px;color:var(--cyan);font-weight:700;min-width:52px;}}
.news-row{{font-size:11.5px;color:var(--txt2);padding:5px 0;border-bottom:1px solid var(--line);line-height:1.5;}}
.news-row:last-child{{border-bottom:none;}}
.news-tag{{font-size:9.5px;padding:1px 6px;border-radius:7px;background:#13294a;color:#7fb0ff;margin-right:6px;font-weight:700;}}
.t10{{position:relative;}} .t10-r{{position:absolute;left:-3px;top:-7px;z-index:3;background:var(--gold);color:#0a0e14;border-radius:50%;width:21px;height:21px;display:flex;align-items:center;justify-content:center;font-family:monospace;font-weight:800;font-size:12px;}}
</style></head><body>
<header>
<div class="eyebrow">{T["eyebrow"]}</div>
<h1>{title} · <span class="hl">youzi-scan</span></h1>
<p class="lede">{len(rows)} {T["lede_a"]} {T["lede_b"]}</p>
<div class="meta">
<span class="chip">{T["c_data"]} · <b>DataHub (tushare)</b></span>
{mode_chip}
<span class="chip">{T["c_price"]} · <b>{price_date}</b></span>
<span class="chip">{T["c_vp"]} · <b>{vp_date}</b></span>
<span class="chip">{T["c_flow"]} · <b>{mf_date}</b></span>
<span class="chip">{T["c_cov"]} · <b>{succ}</b></span>
</div>
<div class="tac-bar">
<span class="tac-pill tp-buy">{T["tactic"]["ambush"]} {cc('ambush')}</span>
<span class="tac-pill tp-dip">{T["tactic"]["dip"]} {cc('dip')}</span>
<span class="tac-pill tp-mid">{T["tactic"]["halfway"]} {cc('halfway')}</span>
<span class="tac-pill tp-board">{T["tactic"]["chase"]} {cc('chase')}</span>
<span class="tac-pill tp-no">{T["tactic"]["avoid"]} {cc('avoid')+cc('high')}</span>
<span class="tac-pill" style="background:#161d28;color:var(--txt3)">{T["tactic"]["watch"]} {cc('watch')}</span>
</div></header>
<div class="wrap">
{sec00}{sec_macro}
<section>
<div class="sec-h"><span class="n">04</span><h2>{T["s01"]}</h2><span class="desc">{T["s01d"]} · {fresh_badge}</span></div>
<div class="tbl-wrap" style="margin-bottom:12px"><table>
<thead><tr><th>{tc[0] if False else T["th_date"]}</th><th>{T["th_up"]}</th><th>{T["th_z"]}</th><th>{T["th_seal"]}</th><th>{T["th_mb"]}</th><th>{T["th_b2"]}</th></tr></thead>
<tbody>{sent_rows}</tbody></table></div>
<div class="grid2">
<div class="kbox gold"><div class="kl">{T["cyc_title"]}</div><div class="kv">{v_head}</div>
<div style="font-size:11px;color:var(--txt2)">{v_detail}</div></div>
<div class="kbox green"><div class="kl">{T["for_title"]}</div><div class="kv">{T["for_kv"]}</div>
<div style="font-size:11px;color:var(--txt2)">{T["for_body"]}</div></div>
</div></section>

{sec_capital}
{sec_patterns}
{sec_nextbatch}
{sec_pullback}
<section>
<div class="sec-h"><span class="n">▦</span><h2>{T["s02"]}</h2></div>
<div class="ind-grid">
<div class="ind-c"><h4>{T["i1t"]}</h4><p>{T["i1"]}</p></div>
<div class="ind-c"><h4>{T["i2t"]}</h4><p>{T["i2"]}</p></div>
<div class="ind-c"><h4>{T["i3t"]}</h4><p>{T["i3"]}</p></div>
<div class="ind-c"><h4>{T["i4t"]}</h4><p>{T["i4"]}</p></div>
</div></section>

<section>
<div class="sec-h"><span class="n">07</span><h2>{T["s03"]}</h2><span class="desc">{T["s03d"]}</span></div>
{pools["ambush"] or f'<div class="note">{T["e03"]}</div>'}
</section>

<section>
<div class="sec-h"><span class="n">07</span><h2>{T["s04"]}</h2><span class="desc">{T["s04d"]}</span></div>
{pools["dip"] or f'<div class="note">{T["e04"]}</div>'}
</section>

<section>
<div class="sec-h"><span class="n">07</span><h2>{T["s05"]}</h2><span class="desc">{T["s05d"]}</span></div>
{pools["halfway"] or f'<div class="note">{T["e05"]}</div>'}
</section>

<section>
<div class="sec-h"><span class="n">07</span><h2>{T["s06"]}</h2><span class="desc">{T["s06d"]}</span></div>
{pools["chase"] or f'<div class="note">{T["e06"]}</div>'}
</section>

{sec_top10}
<section>
<div class="sec-h"><span class="n">09</span><h2>{T["s07"].format(len(rows))}</h2><span class="desc">{T["s07d"]}</span></div>
<div class="tbl-wrap"><table>
<thead><tr>{''.join(f'<th>{c}</th>' for c in tc)}</tr></thead>
<tbody>{by_theme}</tbody></table></div>
<div class="note" style="margin-top:10px">{T["legend"]}{fail_txt}</div>
</section>

<section>
<div class="sec-h"><span class="n">10</span><h2>{T["s08"]}</h2></div>
<div class="grid2">
<div class="warn-box"><b>{T["r1t"]}</b><br>{T["r1"]}</div>
<div class="warn-box"><b>{T["r2t"]}</b><br>{T["r2"]}</div>
<div class="warn-box"><b>{T["r3t"]}</b><br>{T["r3"]}</div>
<div class="warn-box"><b>{T["r4t"]}</b><br>{T["r4a"]}{price_date}{T["r4b"]}{vp_date}{T["r4c"]}{mf_date}{vp_lag}{T["r4d"]}</div>
</div></section>

</div>
<footer>
<p>📊 {title} · {T["foot"]} · {date}</p>
<p style="margin-top:6px">{T["disc"]}</p>
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
    print(render(rows, out, lang="zh"))
