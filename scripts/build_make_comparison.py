#!/usr/bin/env python3
"""
Builds an interactive chart (single HTML file) comparing two car makes in Ireland over time
(Bundled with irish-car-sales-data skill).

Monthly registrations per model and the national new-car total come from CSO TEM20 in
data/irish_car_sales.db, so re-running after `ensure_data.py --update` refreshes the page.
Views: rolling 12 months, monthly, calendar year and cumulative, as units or market share.

Usage:
    python3 .agents/skills/irish-car-sales-data/scripts/build_make_comparison.py --makes TESLA BYD
    python3 .agents/skills/irish-car-sales-data/scripts/build_make_comparison.py --makes TESLA BYD --out tesla_vs_byd.html --fragment
"""

import os
import sys
import json
import sqlite3
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ensure_data import ensure_database

# Display names for makes stored in upper case.
DISPLAY = {'TESLA': 'Tesla', 'BYD': 'BYD', 'BMW': 'BMW', 'RENAULT': 'Renault', 'VOLKSWAGEN': 'Volkswagen',
           'TOYOTA': 'Toyota', 'HYUNDAI': 'Hyundai', 'KIA': 'Kia', 'SKODA': 'Skoda', 'MG': 'MG',
           'POLESTAR': 'Polestar', 'VOLVO': 'Volvo', 'NISSAN': 'Nissan', 'AUDI': 'Audi'}

def load(conn, makes):
    market = dict(conn.execute("SELECT month_code, units FROM cso_new_private_cars_monthly").fetchall())
    months = sorted(market)
    series = {}
    for make in makes:
        rows = conn.execute("""SELECT month_code, model, SUM(units) FROM cso_make_model_monthly
                               WHERE make = ? GROUP BY month_code, model""", (make,)).fetchall()
        if not rows:
            raise SystemExit(f"No CSO TEM20 data for make '{make}'")
        names = {m for _, m, _ in rows}
        base = lambda m: m.split(' ', 1)[0] if ' ' in m and m.split(' ', 1)[0] in names else m
        by_month = defaultdict(lambda: defaultdict(int))
        for mc, model, u in rows:
            if u:
                by_month[mc][base(model)] += u
        totals = defaultdict(int)
        for mm in by_month.values():
            for m, u in mm.items():
                totals[m] += u
        order = [m for m, _ in sorted(totals.items(), key=lambda kv: -kv[1])]
        first = {m: min(mc for mc, mm in by_month.items() if mm.get(m)) for m in order}
        series[make] = {
            'name': DISPLAY.get(make, make.title()),
            'models': order,
            'firstMonth': first,
            'modelTotals': {m: totals[m] for m in order},
            # one row per month: units per model, in `models` order
            'rows': [[by_month[mc].get(m, 0) for m in order] for mc in months],
        }
    return {'months': months, 'market': [market[m] for m in months], 'series': [series[m] for m in makes]}

def main():
    parser = argparse.ArgumentParser(description="Build an interactive two-make comparison chart.")
    parser.add_argument("--makes", nargs=2, required=True, metavar=("MAKE_A", "MAKE_B"))
    parser.add_argument("--out", help="Output HTML path (default: <a>_vs_<b>.html)")
    parser.add_argument("--fragment", action="store_true", help="Omit <html>/<head>/<body> (for hosts that add their own)")
    parser.add_argument("--db-path", default="data/irish_car_sales.db")
    args = parser.parse_args()

    makes = [m.upper() for m in args.makes]
    ensure_database(args.db_path, verbose=False)
    conn = sqlite3.connect(f"file:{args.db_path}?mode=ro", uri=True)
    data = load(conn, makes)
    conn.close()

    a, b = (s['name'] for s in data['series'])
    head = '' if args.fragment else ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                                     '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
    html = (TEMPLATE.replace('__HEAD__', head)
            .replace('__HEAD_END__', '' if args.fragment else '</head>\n<body>\n')
            .replace('__TAIL__', '' if args.fragment else '</body>\n</html>\n')
            .replace('__A__', a).replace('__B__', b)
            .replace('__DATA__', json.dumps(data, separators=(',', ':'))))
    out = args.out or f"{makes[0].lower()}_vs_{makes[1].lower()}.html"
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    tot = [sum(map(sum, s['rows'])) for s in data['series']]
    print(f"[Comparison] {a} ({tot[0]:,}) vs {b} ({tot[1]:,}), "
          f"{data['months'][0]}–{data['months'][-1]} -> {out}")

TEMPLATE = r"""__HEAD__<title>__A__ vs __B__ in Ireland</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: headline tiles, one control row, a single-axis line chart with crosshair, then the model mix for the hovered period. */
:root{
  --ground:#f3f4f1;
  --panel:#ffffff;
  --ink:#16191d;
  --ink-2:#4a5058;
  --muted:#7b828b;
  --rule:#dcdfdb;
  --s1:#2a78d6;   /* series 1 (validated categorical slot 1) */
  --s2:#eb6834;   /* series 2 (validated categorical slot 2) */
  --focus:#16191d;
  --display:"Barlow Condensed","Arial Narrow",system-ui,sans-serif;
  --body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#121518;--panel:#1a1e22;--ink:#eceeea;--ink-2:#b5bbc1;--muted:#868d95;--rule:#2c3237;
    --s1:#3987e5;--s2:#d95926;--focus:#eceeea;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#121518;--panel:#1a1e22;--ink:#eceeea;--ink-2:#b5bbc1;--muted:#868d95;--rule:#2c3237;
  --s1:#3987e5;--s2:#d95926;--focus:#eceeea;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.55 var(--body);padding:0 20px}
.wrap{max-width:1000px;margin:0 auto;padding-block:40px 64px;display:flex;flex-direction:column;gap:28px}
.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font:700 clamp(38px,6.5vw,62px)/.95 var(--display);margin:8px 0 10px;letter-spacing:-.01em;text-wrap:balance}
h1 .a{color:var(--s1)} h1 .b{color:var(--s2)}
.lede{max-width:64ch;color:var(--ink-2);margin:0}
h2{font:600 24px/1.1 var(--display);margin:0;text-wrap:balance}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:4px}
.tile .k{font:500 11px/1.3 var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.tile .row{display:flex;align-items:baseline;gap:8px;font-variant-numeric:tabular-nums}
.tile .v{font:600 28px/1.1 var(--display)}
.tile .who{font-size:13px;color:var(--ink-2);display:inline-flex;align-items:center;gap:6px}
.key{display:inline-block;width:14px;height:3px;border-radius:2px}
.key.a{background:var(--s1)} .key.b{background:var(--s2)}
.tile .sub{font-size:12.5px;color:var(--muted)}

.controls{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:center}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:6px;overflow:hidden;background:var(--panel)}
.seg button{font:500 13px var(--body);color:var(--ink-2);background:transparent;border:0;padding:7px 12px;cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--panel)}
.seg button:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
.ctl-label{font:500 11px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-right:8px}

.card{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:18px 18px 12px;position:relative}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--ink-2);margin-bottom:6px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend .tick{width:2px;height:12px;display:inline-block;background:var(--muted)}
.chart-scroll{overflow-x:auto}
svg.chart{display:block;width:100%;min-width:640px;height:auto;touch-action:pan-y}
.chart text{fill:var(--muted);font:11.5px var(--mono)}
.chart .grid{stroke:var(--rule)} .chart .base{stroke:var(--ink-2)}
.chart .line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .s1{stroke:var(--s1)} .chart .s2{stroke:var(--s2)}
.chart .f1{fill:var(--s1)} .chart .f2{fill:var(--s2)}
.chart .dot{stroke:var(--panel);stroke-width:2}
.chart .xhair{stroke:var(--ink-2);stroke-width:1;stroke-dasharray:3 3}
.chart .end{font:600 12px var(--mono);fill:var(--ink)}
.chart .ann{font:500 11px var(--mono);fill:var(--ink-2)}
.chart .launch{stroke-width:2}
.chart .bar-hit{cursor:pointer}
.chart .pin{stroke:var(--ink);stroke-width:1}
.race{display:flex;align-items:center;gap:14px;margin:4px 0 8px;flex-wrap:wrap}
.play{font:600 13px var(--body);color:var(--panel);background:var(--ink);border:0;border-radius:6px;padding:8px 14px;cursor:pointer;min-width:118px}
.play:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.play:disabled{opacity:.4;cursor:default}
#race-scrub{flex:1;min-width:160px;accent-color:var(--ink)}
.race-when{font:500 12.5px var(--mono);color:var(--ink-2);min-width:150px;text-align:right;font-variant-numeric:tabular-nums}
.chart .clock{font:700 46px var(--display);fill:var(--ink);opacity:.14}
.chart .lead{font:600 13px var(--body);fill:var(--ink-2)}
.tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:8px 10px;font-size:12.5px;box-shadow:0 4px 14px rgb(0 0 0 / .12);min-width:150px}
.tip .t{font:500 11px var(--mono);color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em}
.tip .r{display:flex;align-items:center;gap:8px;font-variant-numeric:tabular-nums}
.tip .r b{font-weight:600;min-width:58px;text-align:right}
.tip .r span{color:var(--ink-2)}
.hint{font-size:12.5px;color:var(--muted);margin-top:6px}

.mix{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.mix h3{font:600 18px/1.2 var(--display);margin:0 0 10px;display:flex;align-items:center;gap:8px}
.mix h3 small{font:500 12px var(--mono);color:var(--muted)}
.mix ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.mrow{display:grid;grid-template-columns:110px 1fr 56px;gap:10px;align-items:center;font-size:13.5px}
.mrow .bar{height:10px;border-radius:0 3px 3px 0;min-width:2px}
.mrow .n{text-align:right;font:500 12.5px var(--mono);font-variant-numeric:tabular-nums}
.mrow.zero{color:var(--muted)}
.empty{font-size:13px;color:var(--muted)}
details{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:14px 18px}
summary{cursor:pointer;font-weight:600}
.tbl-scroll{overflow-x:auto;margin-top:12px}
table{border-collapse:collapse;width:100%;font:13px var(--mono);font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:500}
.sources{font-size:13px;color:var(--ink-2);max-width:78ch;margin:0}
@media (max-width:640px){.mix{grid-template-columns:1fr}.card{padding:14px 12px 10px}}
</style>
__HEAD_END__
<div class="wrap">
  <header>
    <div class="eyebrow">Ireland · new private car registrations</div>
    <h1><span class="a">__A__</span> vs <span class="b">__B__</span></h1>
    <p class="lede" id="lede"></p>
  </header>

  <section class="tiles" id="tiles" aria-label="Headline figures"></section>

  <section aria-labelledby="h-chart" style="display:flex;flex-direction:column;gap:14px">
    <h2 id="h-chart">Registrations over time</h2>
    <div class="controls">
      <div><span class="ctl-label" id="l-view">View</span>
        <div class="seg" role="group" aria-labelledby="l-view" id="ctl-view">
          <button id="v-rolling" data-v="rolling" aria-pressed="true">Rolling 12 months</button>
          <button id="v-monthly" data-v="monthly" aria-pressed="false">Monthly</button>
          <button id="v-annual" data-v="annual" aria-pressed="false">By year</button>
          <button id="v-cumulative" data-v="cumulative" aria-pressed="false">Cumulative</button>
        </div></div>
      <div><span class="ctl-label" id="l-metric">Measure</span>
        <div class="seg" role="group" aria-labelledby="l-metric" id="ctl-metric">
          <button id="m-units" data-m="units" aria-pressed="true">Cars</button>
          <button id="m-share" data-m="share" aria-pressed="false">Share of market</button>
        </div></div>
      <div><span class="ctl-label" id="l-range">From</span>
        <div class="seg" role="group" aria-labelledby="l-range" id="ctl-range">
          <button id="r-2019" data-r="2019" aria-pressed="true">2019</button>
          <button id="r-2022" data-r="2022" aria-pressed="false">2022</button>
          <button id="r-all" data-r="all" aria-pressed="false">2014</button>
        </div></div>
    </div>
    <div class="card" id="card">
      <div class="legend">
        <span><i class="key a"></i>__A__</span>
        <span><i class="key b"></i>__B__</span>
        <span><i class="tick"></i>Model's first registration</span>
      </div>
      <div class="race">
        <button id="race-play" class="play" aria-label="Play race">▶ Play race</button>
        <input id="race-scrub" type="range" min="0" max="1" step="0.001" value="1" aria-label="Race position">
        <span id="race-when" class="race-when" aria-live="off"></span>
      </div>
      <div class="chart-scroll"><svg class="chart" id="chart" viewBox="0 0 900 380" role="img" aria-labelledby="h-chart"></svg></div>
      <div class="tip" id="tip" hidden></div>
      <div class="hint" id="hint">Press Play to race the lines through time, or drag the slider. Hover or use the arrow keys to read values; click to pin a period. The model mix below follows the chart.</div>
    </div>
  </section>

  <section aria-labelledby="h-mix" style="display:flex;flex-direction:column;gap:12px">
    <h2 id="h-mix">Model mix: <span id="mix-period"></span></h2>
    <div class="card"><div class="mix" id="mix"></div></div>
  </section>

  <details>
    <summary>Table view: registrations by year and model</summary>
    <div class="tbl-scroll"><table id="tbl"></table></div>
  </details>

  <p class="sources"><strong>Data:</strong> CSO Ireland table TEM20, <em>New Private Cars Licensed for the First Time by Make and Model</em> (CC BY 4.0), <span id="coverage"></span>. Market share is against all new private cars. CSO counts registrations of models it lists by name and can differ from SIMI's or the brands' own figures. Some makes sell plug-in hybrids as well as electric cars, so neither line is a pure EV count.</p>
</div>

<script>
const D=__DATA__;
const MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const MONTHS_LONG=["January","February","March","April","May","June","July","August","September","October","November","December"];
const fmt=n=>Math.round(n).toLocaleString("en-IE");
const S=D.series, N=D.months.length;
const yearOf=mc=>Math.floor(mc/100), monOf=mc=>mc%100;
const mlabel=mc=>`${MONTHS[monOf(mc)-1]} ${yearOf(mc)}`;
const last=D.months[N-1], lastYear=yearOf(last), lastMon=monOf(last);
S.forEach(s=>s.total=s.rows.map(r=>r.reduce((a,b)=>a+b,0)));

/* ---------- derived figures ---------- */
const sumRange=(arr,i0,i1)=>{let t=0;for(let i=i0;i<=i1;i++)t+=arr[i];return t};
const idxOfYear=y=>D.months.map((m,i)=>[m,i]).filter(([m])=>yearOf(m)===y).map(([,i])=>i);
function yearTotals(s){const o={};D.months.forEach((m,i)=>{o[yearOf(m)]=(o[yearOf(m)]||0)+s.total[i]});return o}
const YT=S.map(yearTotals);
const marketYT={};D.months.forEach((m,i)=>marketYT[yearOf(m)]=(marketYT[yearOf(m)]||0)+D.market[i]);
const cum=S.map(s=>{let c=0;return s.total.map(v=>c+=v)});
const roll=arr=>arr.map((_,i)=>i<11?null:sumRange(arr,i-11,i));
const rollS=S.map(s=>roll(s.total)), rollM=roll(D.market);
// First month where series B's rolling 12-month total passes series A's after A led.
function crossover(){for(let i=12;i<N;i++){const a=rollS[0][i],b=rollS[1][i],pa=rollS[0][i-1],pb=rollS[1][i-1];
  if(a!=null&&pa!=null&&pa>0&&pb>0&&((pa>=pb&&b>a)||(pb>=pa&&a>b)))return i}return -1}
const cross=crossover();

/* ---------- lede + tiles ---------- */
const ytd=y=>S.map((s,k)=>{const idx=idxOfYear(y).filter(i=>monOf(D.months[i])<=lastMon);return sumRange(s.total,idx[0],idx[idx.length-1])});
const ytdNow=ytd(lastYear), ytdPrev=ytd(lastYear-1);
const peakYear=S.map((s,k)=>Object.entries(YT[k]).filter(([y])=>+y<lastYear||lastMon===12).reduce((a,b)=>b[1]>a[1]?b:a));
const leader=ytdNow[0]>=ytdNow[1]?0:1, other=1-leader;
document.getElementById("lede").textContent=
  `${S[0].name}'s first registration in the data is ${mlabel(D.months[S[0].total.findIndex(v=>v>0)])}; ${S[1].name}'s is ${mlabel(D.months[S[1].total.findIndex(v=>v>0)])}. `+
  `In ${MONTHS_LONG[0]}–${MONTHS_LONG[lastMon-1]} ${lastYear}, ${S[leader].name} registered ${fmt(ytdNow[leader])} cars against ${S[other].name}'s ${fmt(ytdNow[other])}.`+
  (cross>=0?` On a rolling 12-month basis the lead changed hands in ${MONTHS_LONG[monOf(D.months[cross])-1]} ${yearOf(D.months[cross])}.`:"");
document.getElementById("coverage").textContent=`${mlabel(D.months[0])} to ${mlabel(last)}`;

function tile(k,label,vals,sub){
  const t=document.createElement("div");t.className="tile";
  t.innerHTML=`<div class="k"></div>`+vals.map((v,i)=>`<div class="row"><span class="v">${v}</span><span class="who"><i class="key ${i?"b":"a"}"></i>${S[i].name}</span></div>`).join("")+(sub?`<div class="sub"></div>`:"");
  t.querySelector(".k").textContent=label; if(sub)t.querySelector(".sub").textContent=sub;
  document.getElementById("tiles").appendChild(t);
}
const chg=(a,b)=>b?((a-b)/b*100>0?"+":"")+((a-b)/b*100).toFixed(0)+"%":"new";
tile(0,`${lastYear} to ${MONTHS[lastMon-1]}`,ytdNow.map(fmt),`vs same months ${lastYear-1}: ${S[0].name} ${chg(ytdNow[0],ytdPrev[0])}, ${S[1].name} ${chg(ytdNow[1],ytdPrev[1])}`);
tile(1,`Market share ${lastYear}`,ytdNow.map(v=>(100*v/sumRange(D.market,...(()=>{const ix=idxOfYear(lastYear);return[ix[0],ix[ix.length-1]]})())).toFixed(1)+"%"),"of all new private cars");
tile(2,"Best full year",peakYear.map(([y,v])=>fmt(v)),`${S[0].name} in ${peakYear[0][0]}, ${S[1].name} in ${peakYear[1][0]}`);
tile(3,"All registrations to date",cum.map(c=>fmt(c[N-1])),`${S[0].name} since ${mlabel(D.months[S[0].total.findIndex(v=>v>0)])}, ${S[1].name} since ${mlabel(D.months[S[1].total.findIndex(v=>v>0)])}`);

/* ---------- state ---------- */
const state={view:"rolling",metric:"units",from:"2019",pin:null,hover:null};
function bindSeg(id,key){
  const g=document.getElementById(id);
  g.addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
    g.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",x===b));
    state[key]=b.dataset.v||b.dataset.m||b.dataset.r;state.pin=null;state.hover=null;stopRace(true);render()});
}
bindSeg("ctl-view","view");bindSeg("ctl-metric","metric");bindSeg("ctl-range","from");

/* Points for the current view: [{label, key, i0, i1, vals:[a,b]}] where i0..i1 is the month window
   the point summarises (used for the model mix). */
function points(){
  const startYear=state.from==="all"?yearOf(D.months[0]):+state.from;
  const pts=[];
  if(state.view==="annual"){
    for(let y=startYear;y<=lastYear;y++){const ix=idxOfYear(y);if(!ix.length)continue;
      const i0=ix[0],i1=ix[ix.length-1],m=sumRange(D.market,i0,i1);
      const v=S.map(s=>sumRange(s.total,i0,i1));
      pts.push({label:i1-i0<11?`${y} (${MONTHS[0]}–${MONTHS[monOf(D.months[i1])-1]})`:String(y),short:String(y),i0,i1,partial:i1-i0<11,
        vals:state.metric==="share"?v.map(x=>100*x/m):v});}
    return pts;
  }
  D.months.forEach((mc,i)=>{
    if(yearOf(mc)<startYear)return;
    let v,i0=i,i1=i,lab=mlabel(mc);
    if(state.view==="monthly"){v=S.map(s=>s.total[i]);if(state.metric==="share")v=v.map(x=>100*x/D.market[i])}
    else if(state.view==="rolling"){if(i<11)return;i0=i-11;v=S.map((s,k)=>rollS[k][i]);
      if(state.metric==="share")v=v.map(x=>100*x/rollM[i]);lab=`12 months to ${mlabel(mc)}`}
    else{i0=0;v=S.map((s,k)=>cum[k][i]);if(state.metric==="share")v=v.map(x=>100*x/sumRange(D.market,0,i));lab=`To ${mlabel(mc)}`}
    pts.push({label:lab,short:mlabel(mc),mc,i0,i1,vals:v});
  });
  return pts;
}

/* ---------- chart ---------- */
const svg=document.getElementById("chart"),NS="http://www.w3.org/2000/svg";
const W=900,H=380,L=58,R=70,T=20,B=320;
function el(tag,a,p=svg){const e=document.createElementNS(NS,tag);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e}
// Smallest 1/2/2.5/5 x 10^n step that covers v in at most 5 steps.
function niceMax(v){if(v<=0)return{max:1,step:.25};const mag=10**Math.floor(Math.log10(v/5));
  for(const s of[1,2,2.5,5,10]){const step=s*mag;if(step*5>=v)return{max:Math.ceil(v/step-1e-9)*step,step}}}
const tip=document.getElementById("tip"),card=document.getElementById("card");
let PTS=[],X=null,DRAW=null;
const RACE={f:null,playing:false,raf:0,last:0};

function fmtVal(v){return state.metric==="share"?v.toFixed(v<1?2:1)+"%":fmt(v)}
function render(){
  svg.replaceChildren();
  PTS=points();
  const max=Math.max(...PTS.flatMap(p=>p.vals)),{max:YM,step}=niceMax(max*1.04);
  const y=v=>B-(v/YM)*(B-T);
  for(let v=0;v<=YM+1e-9;v+=step){
    el("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:v?"grid":"base"});
    el("text",{x:L-8,y:y(v)+4,"text-anchor":"end"}).textContent=state.metric==="share"?(+v.toFixed(2))+"%":fmt(v);
  }
  const n=PTS.length;
  scrub.disabled=state.view==="annual";DRAW=null;
  if(state.view==="annual"){
    const band=(W-L-R)/n,bw=Math.min(26,band*.32),gap=2;
    X=i=>L+band*i+band/2;
    PTS.forEach((p,i)=>{
      p.vals.forEach((v,k)=>{const x=X(i)+(k?gap/2:-bw-gap/2),h=B-y(v),r=Math.min(3,h/2);
        const d=`M${x},${B} V${B-h+r} q0,-${r} ${r},-${r} h${bw-2*r} q${r},0 ${r},${r} V${B} Z`;
        el("path",{d,class:"f"+(k+1),opacity:p.partial?.55:1});});
      el("text",{x:X(i),y:B+20,"text-anchor":"middle"}).textContent=p.short+(p.partial?"*":"");
    });
    if(PTS.some(p=>p.partial))el("text",{x:W-R,y:B+40,"text-anchor":"end",class:"ann"}).textContent=`* ${MONTHS[0]}–${MONTHS[lastMon-1]} only`;
  }else{
    X=i=>L+(n<2?0:(W-L-R)*i/(n-1));
    // year ticks
    PTS.forEach((p,i)=>{if(monOf(p.mc)===1||i===0){el("line",{x1:X(i),x2:X(i),y1:B,y2:B+5,class:"base"});
      el("text",{x:X(i),y:B+20,"text-anchor":i===0?"start":"middle"}).textContent=monOf(p.mc)===1?yearOf(p.mc):p.short}});
    const clock=el("text",{x:L+14,y:T+44,class:"clock"});
    const lead=el("text",{x:L+16,y:T+66,class:"lead"});
    const paths=S.map((s,k)=>el("path",{class:"line s"+(k+1)}));
    const heads=S.map((s,k)=>el("circle",{r:4,class:"dot f"+(k+1)}));
    const labels=S.map(()=>el("text",{class:"end"}));
    // model launch ticks (models with >= 3% of the make's total), revealed as the race reaches them
    const reveal=[];
    S.forEach((s,k)=>{const tot=Object.values(s.modelTotals).reduce((a,b)=>a+b,0);
      s.models.forEach(m=>{if(s.modelTotals[m]<tot*.03)return;const i=PTS.findIndex(p=>p.mc===s.firstMonth[m]);if(i<0)return;
        const t=el("line",{x1:X(i),x2:X(i),y1:B-2-k*9,y2:B-9-k*9,class:"launch s"+(k+1)});
        const ti=document.createElementNS(NS,"title");ti.textContent=`${s.name} ${m}: first registered ${mlabel(s.firstMonth[m])}`;t.appendChild(ti);
        reveal.push([i,[t]])})});
    // crossover marker
    if(state.view==="rolling"&&cross>=0&&state.metric==="units"){const i=PTS.findIndex(p=>p.mc===D.months[cross]);
      if(i>=0){const yy=y(PTS[i].vals[0]);
        reveal.push([i,[el("circle",{cx:X(i),cy:yy,r:5,fill:"none",stroke:"var(--ink)","stroke-width":1.5}),
          Object.assign(el("text",{x:X(i)-8,y:yy-12,"text-anchor":"end",class:"ann"}),{textContent:"Lead changes hands"})]])}}
    const at=(f,k)=>{const i=Math.floor(f),t=f-i;const a=PTS[i].vals[k];return i+1<n?a+(PTS[i+1].vals[k]-a)*t:a};
    // Draws everything up to fractional point index f (0..n-1).
    DRAW=f=>{
      f=Math.max(0,Math.min(n-1,f));const i=Math.floor(f),hx=X(0)+(X(Math.min(n-1,1))-X(0))*f;
      S.forEach((s,k)=>{
        let d="";for(let j=0;j<=i;j++)d+=`${j?"L":"M"}${X(j).toFixed(1)},${y(PTS[j].vals[k]).toFixed(1)}`;
        const hy=y(at(f,k));if(f>i)d+=`L${hx.toFixed(1)},${hy.toFixed(1)}`;
        paths[k].setAttribute("d",d);heads[k].setAttribute("cx",hx);heads[k].setAttribute("cy",hy);
      });
      const hv=S.map((s,k)=>at(f,k)),ly=hv.map(v=>y(v));
      if(Math.abs(ly[0]-ly[1])<14){const mid=(ly[0]+ly[1])/2,up=ly[0]<ly[1]?0:1;ly[up]=mid-7;ly[1-up]=mid+7}
      labels.forEach((t,k)=>{t.setAttribute("x",hx+8);t.setAttribute("y",ly[k]+4);t.textContent=fmtVal(hv[k])});
      const p=PTS[Math.round(f)];clock.textContent=p.short;
      const gap=Math.abs(hv[0]-hv[1]),ld=hv[0]>=hv[1]?0:1;
      lead.textContent=gap<(state.metric==="share"?.005:.5)?"Level":`${S[ld].name} ahead by ${state.metric==="share"?gap.toFixed(2)+" pts":fmt(gap)}`;
      reveal.forEach(([ix,els])=>els.forEach(e=>e.setAttribute("visibility",ix<=f+1e-9?"visible":"hidden")));
      document.getElementById("race-when").textContent=p.label;
    };
    DRAW(RACE.f==null?n-1:RACE.f);
  }
  const xh=el("line",{y1:T,y2:B,class:"xhair",visibility:"hidden"});
  const hl=S.map((s,k)=>el("circle",{r:4.5,class:"dot f"+(k+1),visibility:"hidden"}));
  const pinL=el("line",{y1:T,y2:B,class:"pin",visibility:"hidden"});
  const hit=el("rect",{x:L-10,y:T,width:W-L-R+20,height:B-T+30,fill:"transparent",tabindex:0,"aria-label":"Chart reading area. Use left and right arrow keys to move between periods."});
  const show=i=>{
    if(RACE.playing)return;
    if(RACE.f!=null)i=Math.min(i,Math.floor(RACE.f));   // don't reveal periods the race hasn't reached
    state.hover=i;const p=PTS[i];
    if(state.view!=="annual"){xh.setAttribute("x1",X(i));xh.setAttribute("x2",X(i));xh.setAttribute("visibility","visible");
      hl.forEach((c,k)=>{c.setAttribute("cx",X(i));c.setAttribute("cy",y(p.vals[k]));c.setAttribute("visibility","visible")})}
    tip.hidden=false;tip.replaceChildren();
    const t=document.createElement("div");t.className="t";t.textContent=p.label;tip.appendChild(t);
    p.vals.map((v,k)=>[v,k]).sort((a,b)=>b[0]-a[0]).forEach(([v,k])=>{const r=document.createElement("div");r.className="r";
      r.innerHTML=`<i class="key ${k?"b":"a"}"></i><b></b><span></span>`;r.querySelector("b").textContent=fmtVal(v);r.querySelector("span").textContent=S[k].name;tip.appendChild(r)});
    const sx=svg.getBoundingClientRect(),cx=sx.left+X(i)/W*sx.width-card.getBoundingClientRect().left;
    const tw=tip.offsetWidth;tip.style.left=Math.max(8,Math.min(card.clientWidth-tw-8,cx+(cx>card.clientWidth/2?-tw-14:14)))+"px";
    tip.style.top=(sx.top-card.getBoundingClientRect().top+30)+"px";
    if(state.pin==null)renderMix(i);
  };
  const hide=()=>{xh.setAttribute("visibility","hidden");hl.forEach(c=>c.setAttribute("visibility","hidden"));tip.hidden=true;state.hover=null;renderMix(state.pin??(RACE.f!=null?Math.round(RACE.f):PTS.length-1))};
  const idxAt=e=>{const r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*W;
    let best=0,bd=1e9;PTS.forEach((p,i)=>{const d=Math.abs(X(i)-vx);if(d<bd){bd=d;best=i}});return best};
  hit.addEventListener("pointermove",e=>show(idxAt(e)));
  hit.addEventListener("pointerleave",hide);
  hit.addEventListener("click",e=>{const i=idxAt(e);state.pin=state.pin===i?null:i;
    pinL.setAttribute("visibility",state.pin==null?"hidden":"visible");
    if(state.pin!=null){pinL.setAttribute("x1",X(i));pinL.setAttribute("x2",X(i))}renderMix(state.pin??i)});
  hit.addEventListener("focus",()=>show(state.hover??PTS.length-1));
  hit.addEventListener("blur",hide);
  hit.addEventListener("keydown",e=>{
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();show(Math.max(0,Math.min(PTS.length-1,(state.hover??PTS.length-1)+(e.key==="ArrowRight"?1:-1))))}
    if(e.key==="Enter"||e.key===" "){e.preventDefault();const i=state.hover??PTS.length-1;state.pin=state.pin===i?null:i;
      pinL.setAttribute("visibility",state.pin==null?"hidden":"visible");pinL.setAttribute("x1",X(i));pinL.setAttribute("x2",X(i));renderMix(i)}
  });
  mixIdx=-1;renderMix(RACE.f!=null?Math.round(RACE.f):PTS.length-1);
}

/* ---------- race ---------- */
const playBtn=document.getElementById("race-play"),scrub=document.getElementById("race-scrub");
const reduceMotion=matchMedia("(prefers-reduced-motion: reduce)").matches;
let mixIdx=-1;
function setFrame(f){
  RACE.f=f;DRAW&&DRAW(f);scrub.value=PTS.length>1?f/(PTS.length-1):1;
  const i=Math.round(f);if(i!==mixIdx){mixIdx=i;renderMix(i)}
}
function setPlayLabel(){playBtn.textContent=RACE.playing?"❚❚ Pause":(RACE.f!=null&&RACE.f<PTS.length-1?"▶ Resume":"▶ Play race");
  playBtn.setAttribute("aria-label",RACE.playing?"Pause race":"Play race")}
function stopRace(reset){RACE.playing=false;cancelAnimationFrame(RACE.raf);if(reset){RACE.f=null;mixIdx=-1;scrub.value=1}setPlayLabel()}
function tick(now){
  if(!RACE.playing)return;
  const n=PTS.length,dur=Math.min(16000,Math.max(7000,n*110));   // whole race in 7-16 s
  const dt=RACE.last==null?0:Math.max(0,Math.min(64,now-RACE.last));RACE.last=now;
  let f=RACE.f+dt/dur*(n-1);
  if(reduceMotion)f=Math.floor(RACE.f)+1;                         // step a period at a time, no tweening
  if(f>=n-1){setFrame(n-1);stopRace(false);return}
  setFrame(f);
  RACE.raf=reduceMotion?setTimeout(()=>requestAnimationFrame(tick),350):requestAnimationFrame(tick);
}
playBtn.addEventListener("click",()=>{
  if(RACE.playing){stopRace(false);return}
  if(state.view==="annual")document.getElementById("v-rolling").click();   // the race runs on the line views
  tip.hidden=true;state.pin=null;
  if(RACE.f==null||RACE.f>=PTS.length-1)setFrame(0);
  RACE.playing=true;RACE.last=null;setPlayLabel();RACE.raf=requestAnimationFrame(tick);
});
scrub.addEventListener("input",()=>{
  if(state.view==="annual")return;
  if(RACE.playing)stopRace(false);
  setFrame(+scrub.value*(PTS.length-1));setPlayLabel();
});

/* ---------- model mix ---------- */
function renderMix(i){
  const p=PTS[i];if(!p)return;
  document.getElementById("mix-period").textContent=p.label.replace(/^To /,"all registrations to ");
  const box=document.getElementById("mix");box.replaceChildren();
  const vals=S.map(s=>s.models.map((m,j)=>[m,sumRange(s.rows.map(r=>r[j]),p.i0,p.i1)]).filter(([,v])=>v>0));
  const mx=Math.max(1,...vals.flat().map(([,v])=>v));
  S.forEach((s,k)=>{
    const col=document.createElement("div");
    const h=document.createElement("h3");h.innerHTML=`<i class="key ${k?"b":"a"}"></i><span></span><small></small>`;
    h.querySelector("span").textContent=s.name;h.querySelector("small").textContent=fmt(vals[k].reduce((a,[,v])=>a+v,0))+" cars";col.appendChild(h);
    if(!vals[k].length){const e=document.createElement("p");e.className="empty";e.textContent="No registrations in this period.";col.appendChild(e)}
    else{const ol=document.createElement("ol");
      vals[k].sort((a,b)=>b[1]-a[1]).forEach(([m,v])=>{const li=document.createElement("li");li.className="mrow";
        li.innerHTML=`<span class="nm"></span><span><i class="bar" style="display:block;width:${100*v/mx}%;background:var(--s${k+1})"></i></span><span class="n">${fmt(v)}</span>`;
        li.querySelector(".nm").textContent=m;ol.appendChild(li)});col.appendChild(ol)}
    box.appendChild(col);
  });
}

/* ---------- table ---------- */
(function(){
  const years=[...new Set(D.months.map(yearOf))].filter(y=>S.some((s,k)=>YT[k][y]>0));
  const tb=document.getElementById("tbl");
  let h=`<thead><tr><th>Model</th>${years.map(y=>`<th>${y}${y===lastYear&&lastMon<12?"*":""}</th>`).join("")}</tr></thead><tbody>`;
  S.forEach((s,k)=>{
    s.models.forEach((m,j)=>{h+=`<tr><td>${s.name} ${m}</td>`+years.map(y=>{const ix=idxOfYear(y);const v=sumRange(s.rows.map(r=>r[j]),ix[0],ix[ix.length-1]);return`<td>${v?fmt(v):"–"}</td>`}).join("")+"</tr>"});
    h+=`<tr><td><strong>${s.name} total</strong></td>`+years.map(y=>`<td><strong>${fmt(YT[k][y]||0)}</strong></td>`).join("")+"</tr>";
  });
  h+=`<tr><td>All new cars</td>`+years.map(y=>`<td>${fmt(marketYT[y])}</td>`).join("")+"</tr></tbody>";
  if(lastMon<12)h+=`<caption style="caption-side:bottom;text-align:left;padding-top:8px;color:var(--muted)">* ${lastYear} covers ${MONTHS_LONG[0]} to ${MONTHS_LONG[lastMon-1]}.</caption>`;
  tb.innerHTML=h;
})();

render();
</script>
__TAIL__"""

if __name__ == '__main__':
    main()
