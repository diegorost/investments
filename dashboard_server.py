#!/usr/bin/env python3
"""
ETF Dashboard Server
====================
Runs a local web server. Open http://localhost:8000 in your browser.
Click "Update" in the dashboard to fetch fresh data from Yahoo Finance.

Usage:
    python dashboard_server.py

Requirements:
    - Python 3.8+
    - yfinance:  pip install yfinance
"""

import json
import os
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import yfinance as yf
except ImportError:
    print("\n  ERROR: yfinance not installed.")
    print("  Run:  pip install yfinance\n")
    sys.exit(1)

try:
    import requests as _requests
except ImportError:
    _requests = None

# ── Configuration ────────────────────────────────────────────────────────────

ETFS           = ["UPRO", "TQQQ", "TECL", "SOXL", "GC=F", "SI=F", "SPY", "QQQ", "SOXX", "XLK"]
SWINGS_TICKERS = ["QBTX", "MSFU", "PLTU", "JNUG"]
HOLDS_TICKERS  = ["AEM", "IAG", "RGLD", "SILJ", "AG", "CDE"]
START_YEAR = 2022
TOP_N      = 3
GAP_DAYS   = 30
PORT       = 8000
DIR        = os.path.dirname(os.path.abspath(__file__))

# ── Fintual ──────────────────────────────────────────────────────────────────

FINTUAL_COOKIES_FILE = os.path.join(DIR, "fintual_cookies.json")

def fetch_fintual_goals():
    if _requests is None:
        return {"error": "requests library not installed"}
    if not os.path.exists(FINTUAL_COOKIES_FILE):
        return {"error": "fintual_cookies.json not found"}
    try:
        cfg = json.load(open(FINTUAL_COOKIES_FILE))
    except Exception as e:
        return {"error": f"Could not read fintual_cookies.json: {e}"}

    token  = cfg.get("user_token", "")
    email  = cfg.get("user_email", "")
    cookies = cfg.get("cookies", {})

    try:
        r = _requests.get(
            "https://fintual.cl/api/goals",
            params={"user_token": token, "user_email": email},
            cookies=cookies,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
        if r.status_code == 200:
            goals = r.json().get("data", [])
            return {"ok": True, "goals": [
                {
                    "id":        g["id"],
                    "name":      g["attributes"]["name"],
                    "nav":       g["attributes"]["nav"],
                    "deposited": g["attributes"]["deposited"],
                    "profit":    g["attributes"]["profit"],
                    "type":      g["attributes"].get("translated_goal_type", ""),
                }
                for g in goals
            ]}
        else:
            return {"error": f"HTTP {r.status_code} — cookies may have expired. Run update_fintual_cookies.py"}
    except Exception as e:
        return {"error": str(e)}


# ── Data helpers ─────────────────────────────────────────────────────────────

def fetch_data(etf):
    print(f"  Downloading {etf}...", end=" ", flush=True)
    ticker = yf.Ticker(etf)
    df = ticker.history(start=f"{START_YEAR}-01-01", interval="1d")
    if df.empty:
        raise ValueError(f"No data returned for {etf}")
    import math
    rows = [
        [dt.strftime("%Y-%m-%d"), round(float(c), 3)]
        for dt, c in zip(df.index, df["Close"])
        if not math.isnan(float(c))
    ]
    rows.sort(key=lambda x: x[0])
    print(f"OK ({len(rows)} rows, last: ${rows[-1][1]:.2f} {rows[-1][0]})")
    return rows


def compute_lows(rows):
    MONTHS = ["","Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    by_year = {}
    for date_str, price in rows:
        yr = int(date_str[:4])
        if yr < START_YEAR:
            continue
        by_year.setdefault(yr, []).append(
            (datetime.strptime(date_str, "%Y-%m-%d"), price)
        )
    result = {}
    for yr, pts in sorted(by_year.items()):
        pts.sort(key=lambda x: x[1])
        selected = []
        for dt, price in pts:
            if any(abs((dt - s[0]).days) < GAP_DAYS for s in selected):
                continue
            selected.append((dt, price))
            if len(selected) >= TOP_N:
                break
        result[yr] = [[MONTHS[dt.month], round(price, 2)] for dt, price in selected]
    return result


def fetch_all():
    all_data, lows_data, current_prices = {}, {}, {}
    all_tickers = list(dict.fromkeys(ETFS + SWINGS_TICKERS + HOLDS_TICKERS))
    for ticker in all_tickers:
        rows = fetch_data(ticker)
        all_data[ticker]       = rows
        current_prices[ticker] = rows[-1][1]
        if ticker in ETFS:
            lows_data[ticker] = compute_lows(rows)
    return all_data, lows_data, current_prices


def build_html(all_data, lows_data, current_prices):
    last_date = max(rows[-1][0] for rows in all_data.values() if rows)

    def fmt_lows(etf_lows):
        lines = []
        for yr, entries in sorted(etf_lows.items()):
            lines.append(f"    {yr}: {json.dumps(entries, separators=(',',':'))},")
        return "\n".join(lines)

    lows_js_parts = []
    for etf in ETFS:
        inner = fmt_lows(lows_data[etf])
        lows_js_parts.append(f"  \"{etf}\": {{\n{inner}\n  }},")
    lows_js   = "{\n" + "\n".join(lows_js_parts) + "\n}"
    cp_js     = json.dumps({etf: current_prices[etf] for etf in ETFS}, indent=2)
    all_data_js = json.dumps({etf: all_data[etf] for etf in ETFS}, separators=(",",":"))
    swings_data_js = json.dumps(
        {t: all_data[t] for t in SWINGS_TICKERS + HOLDS_TICKERS if t in all_data},
        separators=(",",":")
    )
    default_swings_js = json.dumps(SWINGS_TICKERS)
    default_holds_js  = json.dumps(HOLDS_TICKERS)

    return _render_html(last_date, lows_js, cp_js, all_data_js,
                        swings_data_js, default_swings_js, default_holds_js)


def _render_html(last_date, lows_js, cp_js, all_data_js,
                 swings_data_js, default_swings_js, default_holds_js):
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETF — Top 3 Annual Lows</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0a0c10; --surface:#111318; --border:#1e2330;
    --accent:#e63946; --accent2:#f4a261; --text:#e8eaf0;
    --muted:#4a5068; --green:#2ec4b6;
    --mono:'IBM Plex Mono',monospace; --title:'Syne',sans-serif;
  }}
  body.theme-light {{
    --bg:#f5f5f0; --surface:#ffffff; --border:#ddddd8;
    --accent:#e63946; --accent2:#f4a261; --text:#1a1a1a;
    --muted:#888880; --green:#0a9e8a;
  }}
  body.theme-grey {{
    --bg:#2a2d35; --surface:#343840; --border:#444854;
    --accent:#e63946; --accent2:#f4a261; --text:#d4d6dc;
    --muted:#7a7e8a; --green:#2ec4b6;
  }}
  .theme-btn {{
    width:18px;height:18px;border-radius:50%;border:2px solid transparent;
    cursor:pointer;transition:border-color .15s;flex-shrink:0;
  }}
  .theme-btn.active {{border-color:var(--text)}}
  body.theme-light td{{border-bottom-color:rgba(0,0,0,.07)}}
  body.theme-light .price-tag{{background:rgba(0,0,0,.03)}}
  input[type=date],input:not([type]){{background:var(--surface);color:var(--text);border-color:var(--border)}}
  body.theme-light input{{color-scheme:light}}
  body.theme-grey  input{{color-scheme:dark}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:var(--mono);min-height:100vh;padding:40px 24px 60px}}
  header{{margin-bottom:40px;border-left:3px solid var(--accent);padding-left:16px}}
  header h1{{font-family:var(--title);font-size:clamp(1.6rem,4vw,2.4rem);font-weight:800;letter-spacing:-.5px}}
  header p{{color:var(--muted);font-size:.78rem;margin-top:6px;letter-spacing:.08em}}
  .legend{{display:flex;gap:20px;margin-bottom:28px;flex-wrap:wrap}}
  .legend-item{{display:flex;align-items:center;gap:6px;font-size:.72rem;color:var(--muted)}}
  .legend-dot{{width:8px;height:8px;border-radius:50%}}
  .etf-block{{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:20px 24px;margin-bottom:20px;opacity:0;animation:fadeIn .4s ease forwards}}
  @keyframes fadeIn{{to{{opacity:1}}}}
  .etf-header{{display:flex;align-items:baseline;gap:12px;margin-bottom:16px;flex-wrap:wrap}}
  .etf-name{{font-family:var(--title);font-size:1.3rem;font-weight:800;letter-spacing:-.3px}}
  .current-price{{font-size:.85rem;color:var(--green);font-weight:600}}
  .etf-tag{{font-size:.68rem;color:var(--muted);letter-spacing:.1em;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse;font-size:.78rem}}
  th{{text-align:left;padding:6px 10px;color:var(--muted);font-weight:400;border-bottom:1px solid var(--border);letter-spacing:.06em;font-size:.7rem}}
  td{{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top}}
  .year-col{{color:var(--muted);font-size:.72rem;width:52px;padding-top:10px}}
  .rank-cell{{white-space:nowrap}}
  .price-tag{{display:inline-flex;align-items:center;gap:5px;background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:4px;padding:3px 8px;margin:2px 4px 2px 0;font-size:.75rem}}
  .price-tag.rank1{{border-color:#e63946;color:#e63946}}
  .price-tag.rank2{{border-color:#f4a261;color:#f4a261}}
  .month{{color:var(--muted);font-size:.68rem;margin-right:2px}}
  .ret{{color:var(--green);font-size:.7rem}}
  .empty{{color:var(--border)}}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-bottom:40px;flex-wrap:wrap">
  <header style="margin-bottom:0">
    <h1>ETF Leveraged — Historical Lows</h1>
    <p id="update-status">UPDATED: {last_date} &nbsp;·&nbsp; TOP {TOP_N} ANNUAL LOWS SINCE {START_YEAR} &nbsp;·&nbsp; MIN GAP {GAP_DAYS} DAYS</p>
  </header>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:12px">
    <div style="display:flex;gap:8px;align-items:center">
      <button class="theme-btn active" id="btn-dark"  onclick="setTheme('dark')"  title="Dark"  style="background:#0a0c10"></button>
      <button class="theme-btn"        id="btn-grey"  onclick="setTheme('grey')"  title="Grey"  style="background:#2a2d35"></button>
      <button class="theme-btn"        id="btn-light" onclick="setTheme('light')" title="Light" style="background:#f5f5f0"></button>
    </div>
    <div id="fintual-top" style="text-align:right">
      <div style="font-size:.62rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Fintual · APV-B</div>
      <div id="fintual-nav" style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--text)">—</div>
      <div id="fintual-profit" style="font-size:.75rem;color:var(--green);margin-top:2px">—</div>
    </div>
  </div>
</div>

<script>
function setTheme(t) {{
  document.body.classList.remove('theme-light','theme-grey');
  if(t==='light') document.body.classList.add('theme-light');
  if(t==='grey')  document.body.classList.add('theme-grey');
  ['dark','grey','light'].forEach(x => document.getElementById('btn-'+x).classList.toggle('active', x===t));
}}
(function(){{ setTheme('dark'); }})();
</script>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#e63946"></div> Low #1 of year</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f4a261"></div> Low #2 of year</div>
  <div class="legend-item"><div class="legend-dot" style="background:#2ec4b6"></div> Low #3</div>
</div>

<div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px 24px;margin-bottom:24px">
  <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Select Tickers</div>
  <div id="ticker-checkboxes" style="display:flex;flex-wrap:wrap;gap:16px"></div>
</div>

<div id="tables"></div>

<script>
async function loadFintual() {{
  try {{
    const res  = await fetch('/fintual-data');
    const json = await res.json();
    if(!json.ok || !json.goals.length) return;
    const g   = json.goals[0];
    const pct = ((g.profit / g.deposited) * 100).toFixed(1);
    const fmt = n => '$' + Math.round(n).toLocaleString('es-CL');
    document.getElementById('fintual-nav').textContent    = fmt(g.nav);
    document.getElementById('fintual-profit').textContent = fmt(g.profit) + ' (+' + pct + '%)';
  }} catch(e) {{}}
}}
loadFintual();
</script>

<script>
const currentPrices = {cp_js};
const data = {lows_js};
const rankClass = i => i===0?'rank1':i===1?'rank2':'';
const fmt = n => '$'+n.toFixed(2);
function etfColor(e){{return {{UPRO:'#378ADD',TQQQ:'#2ec4b6',TECL:'#f4a261',SOXL:'#e63946','GC=F':'#FFD700','SI=F':'#C0C0C0',SPY:'#1f77b4',QQQ:'#ff7f0e',SOXX:'#2ca02c',XLK:'#9467bd'}}[e]||'#e8eaf0'}}
let selectedTickers = new Set();

function renderTables(d, cp) {{
  const container = document.getElementById('tables');
  container.innerHTML = '';
  if(selectedTickers.size === 0) {{
    container.innerHTML = '<div style="color:var(--muted);font-size:.9rem;padding:20px;text-align:center">Select at least one ticker to view tables</div>';
    return;
  }}
  let delay = 0;
  for (const [etf, years] of Object.entries(d)) {{
    if(!selectedTickers.has(etf)) continue;
    const block = document.createElement('div');
    block.className = 'etf-block';
    block.style.animationDelay = delay+'ms';
    delay += 60;
    const yearKeys = Object.keys(years).sort();
    const maxRanks = {TOP_N};
    const cpVal = cp[etf];
    let html = `<div class="etf-header">
      <span class="etf-name" style="color:${{etfColor(etf)}}">${{etf}}</span>
      <span class="current-price">$${{cpVal.toFixed(2)}}</span>
      <span class="etf-tag">Top {TOP_N} annual lows · {START_YEAR}–${{new Date().getFullYear()}}</span>
    </div>`;
    html += '<table><thead><tr><th>Year</th>';
    for(let i=1;i<=maxRanks;i++) html+=`<th>#${{i}}</th>`;
    html += '</tr></thead><tbody>';
    for (const yr of yearKeys) {{
      const entries = years[yr];
      html += `<tr><td class="year-col">${{yr}}</td>`;
      for(let i=0;i<maxRanks;i++) {{
        html += '<td class="rank-cell">';
        if(entries[i]){{
          const [month,price]=entries[i];
          const ret=((cpVal-price)/price*100).toFixed(0);
          html+=`<span class="price-tag ${{rankClass(i)}}"><span class="month">${{month}}</span>${{fmt(price)}}<span class="ret">+${{ret}}%</span></span>`;
        }}else{{html+='<span class="empty">—</span>';}}
        html+='</td>';
      }}
      html+='</tr>';
    }}
    html+='</tbody></table>';
    block.innerHTML=html;
    container.appendChild(block);
  }}
}}

// Initialize ticker checkboxes
const tickerDiv = document.getElementById('ticker-checkboxes');
['UPRO','TQQQ','TECL','SOXL'].forEach(etf=>{{
  const label = document.createElement('label');
  label.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none';
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.value = etf;
  checkbox.style.cssText = 'cursor:pointer;width:16px;height:16px;accent-color:'+etfColor(etf);
  checkbox.onchange = ()=>{{
    if(checkbox.checked) selectedTickers.add(etf);
    else selectedTickers.delete(etf);
    renderTables(data, currentPrices);
  }};
  const text = document.createElement('span');
  text.textContent = etf;
  text.style.cssText = 'font-size:.85rem;color:var(--text)';
  label.appendChild(checkbox);
  label.appendChild(text);
  tickerDiv.appendChild(label);
}});

renderTables(data, currentPrices);
</script>

<!-- CHART SECTION -->
<div style="margin-top:48px;border-top:1px solid var(--border);padding-top:36px">
  <div style="border-left:3px solid #f4a261;padding-left:16px;margin-bottom:24px">
    <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:var(--text)">Price Chart</div>
    <div style="font-size:.75rem;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.08em">Select ETFs & period</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:20px">
    <div id="etf-toggles" style="display:flex;flex-wrap:wrap;gap:10px"></div>
    <button id="mode-btn" onclick="toggleMode()" style="background:var(--surface);border:1px solid #4a5068;color:var(--muted);padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.78rem;font-family:inherit;margin-left:8px">% change</button>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px" id="period-buttons"></div>
  <div style="font-size:.72rem;color:var(--muted);margin-bottom:12px">
    Custom range:
    <input type="date" id="date-from" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:3px 6px;font-size:.72rem;border-radius:3px;color-scheme:dark">
    →
    <input type="date" id="date-to" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:3px 6px;font-size:.72rem;border-radius:3px;color-scheme:dark">
    <button onclick="applyCustom()" style="background:var(--border);border:1px solid var(--muted);color:var(--text);padding:3px 10px;font-size:.72rem;border-radius:3px;cursor:pointer;margin-left:4px">Apply</button>
    <button id="update-btn" onclick="triggerUpdate()" style="background:var(--surface);border:1px solid var(--green);color:var(--green);padding:3px 14px;font-size:.72rem;border-radius:3px;cursor:pointer;margin-left:8px;font-family:inherit">↻ Update</button>
  </div>
  <div style="position:relative;width:100%;height:360px">
    <canvas id="priceChart"></canvas>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const allData = {all_data_js};
const etfColors = {{UPRO:'#378ADD',TQQQ:'#2ec4b6',TECL:'#f4a261',SOXL:'#e63946','GC=F':'#FFD700','SI=F':'#C0C0C0',SPY:'#1f77b4',QQQ:'#ff7f0e',SOXX:'#2ca02c',XLK:'#9467bd'}};
const etfList = ['UPRO','TQQQ','TECL','SOXL','GC=F','SI=F','SPY','QQQ','SOXX','XLK'];
let activeEtfs = new Set(['SOXL']);
let chartFrom = '2025-02-01';
let chartTo = new Date().toISOString().slice(0,10);
let chartInstance = null;
let activeBtn = null;
let viewMode = 'price';

const periods = [
  {{label:'1D',days:1}},{{label:'2D',days:2}},{{label:'3D',days:3}},{{label:'4D',days:4}},
  {{label:'1W',days:7}},{{label:'2W',days:14}},{{label:'3W',days:21}},{{label:'1M',months:1}},
  {{label:'3M',months:3}},{{label:'6M',months:6}},{{label:'YTD',ytd:true}},
  {{label:'1Y',months:12}},{{label:'2Y',months:24}},{{label:'All',all:true}}
];

function getDateRange(p) {{
  const to = new Date().toISOString().slice(0,10);
  if(p.all) return ['{START_YEAR}-01-01', to];
  if(p.ytd) return [new Date().getFullYear()+'-01-01', to];
  const from = new Date();
  if(p.days) {{ from.setDate(from.getDate()-p.days); }}
  else {{ from.setMonth(from.getMonth()-p.months); }}
  return [from.toISOString().slice(0,10), to];
}}

function toggleMode() {{
  viewMode = viewMode==='price'?'pct':'price';
  const btn = document.getElementById('mode-btn');
  btn.textContent = viewMode==='pct'?'$ price':'% change';
  btn.style.color = viewMode==='pct'?'#e8eaf0':'#4a5068';
  btn.style.borderColor = viewMode==='pct'?'#e8eaf0':'#4a5068';
  buildChart();
}}

function buildChart() {{
  const refEtf = etfList.find(e=>activeEtfs.has(e))||'UPRO';
  const labels = (allData[refEtf]||allData['UPRO'])
    .filter(([d])=>d>=chartFrom&&d<=chartTo).map(([d])=>d);
  const datasets = etfList.filter(e=>activeEtfs.has(e)).map(e=>{{
    const dm={{}};
    allData[e].forEach(([d,p])=>{{dm[d]=p}});
    const raw=labels.map(d=>dm[d]??null);
    let data=raw;
    if(viewMode==='pct'){{const base=raw.find(v=>v!=null);data=raw.map(v=>v==null?null:+((v/base-1)*100).toFixed(2));}}
    return {{label:e,data,borderColor:etfColors[e],borderWidth:1.8,pointRadius:0,pointHoverRadius:4,tension:.1,fill:false,spanGaps:true}};
  }});
  const crosshairPlugin={{id:'crosshair',afterDraw(chart){{
    if(chart._cx==null) return;
    const{{ctx,chartArea:{{top,bottom,left,right}},scales}}=chart;
    ctx.save();
    ctx.beginPath();ctx.moveTo(chart._cx,top);ctx.lineTo(chart._cx,bottom);
    ctx.strokeStyle='rgba(200,200,200,.35)';ctx.lineWidth=1;ctx.setLineDash([4,3]);ctx.stroke();
    if(chart._cy!=null){{
      ctx.beginPath();ctx.moveTo(left,chart._cy);ctx.lineTo(right,chart._cy);ctx.stroke();
      const yVal=scales.y.getValueForPixel(chart._cy);
      const lbl=viewMode==='pct'?yVal.toFixed(2)+'%':'$'+yVal.toFixed(2);
      const lw=ctx.measureText(lbl).width+10,lh=16;
      ctx.setLineDash([]);ctx.fillStyle='rgba(30,35,48,.92)';
      ctx.strokeStyle='rgba(200,200,200,.35)';ctx.lineWidth=1;
      ctx.beginPath();ctx.rect(left-lw-2,chart._cy-lh/2,lw,lh);ctx.fill();ctx.stroke();
      ctx.fillStyle='#e8eaf0';ctx.font='11px IBM Plex Mono,monospace';
      ctx.textAlign='right';ctx.textBaseline='middle';ctx.fillText(lbl,left-5,chart._cy);
    }}
    ctx.restore();
  }}}};
  if(chartInstance) chartInstance.destroy();
  chartInstance=new Chart(document.getElementById('priceChart'),{{
    type:'line',data:{{labels,datasets}},plugins:[crosshairPlugin],
    options:{{
      responsive:true,maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>viewMode==='pct'?` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(2)}}%`:` ${{ctx.dataset.label}}: $${{ctx.parsed.y.toFixed(2)}}`}}}}}},
      scales:{{
        x:{{ticks:{{autoSkip:false,maxRotation:0,color:'#888',font:{{size:11}},callback(val,idx){{
          const d=labels[idx];if(!d)return'';
          const[yr,mo]=d.split('-');const q=Math.ceil(parseInt(mo)/3);
          const fi=labels.findIndex(l=>{{const[ly,lm]=l.split('-');return ly===yr&&Math.ceil(parseInt(lm)/3)===q;}});
          return idx===fi?yr+'-'+mo:'';
        }}}},grid:{{color:'rgba(128,128,128,.08)'}}}},
        y:{{ticks:{{color:'#888',font:{{size:11}},callback:v=>viewMode==='pct'?v+'%':'$'+v}},grid:{{color:'rgba(128,128,128,.08)'}}}}
      }},
      onHover(evt,_,chart){{
        const rect=chart.canvas.getBoundingClientRect();
        const ca=chart.chartArea;
        const mx=evt.native?evt.native.clientX-rect.left:null;
        const my=evt.native?evt.native.clientY-rect.top:null;
        if(mx!=null&&mx>=ca.left&&mx<=ca.right&&my>=ca.top&&my<=ca.bottom){{chart._cx=mx;chart._cy=my;}}
        else{{chart._cx=null;chart._cy=null;}}
        chart.draw();
      }}
    }}
  }});
  chartInstance.canvas.addEventListener('mouseleave',()=>{{chartInstance._cx=null;chartInstance._cy=null;chartInstance.draw();}});
}}

function applyCustom() {{
  const f=document.getElementById('date-from').value;
  const t=document.getElementById('date-to').value;
  if(f&&t){{chartFrom=f;chartTo=t;if(activeBtn){{activeBtn.style.color='';activeBtn.style.borderColor='';activeBtn=null;}}buildChart();}}
}}

async function triggerUpdate() {{
  const btn=document.getElementById('update-btn');
  const status=document.getElementById('update-status');
  btn.textContent='↻ Fetching...';btn.disabled=true;btn.style.opacity='.5';
  status.textContent='Contacting server...';
  try {{
    const res=await fetch('/update');
    if(!res.ok) throw new Error('Server error '+res.status);
    const json=await res.json();
    // Merge new data
    Object.assign(allData, json.allData);
    Object.assign(currentPrices, json.currentPrices);
    Object.assign(data, json.lowsData);
    renderTables(json.lowsData, json.currentPrices);
    buildChart();
    status.textContent=`UPDATED: ${{json.lastDate}} · TOP {TOP_N} ANNUAL LOWS SINCE {START_YEAR} · MIN GAP {GAP_DAYS} DAYS`;
    btn.textContent='✓ Updated';
    setTimeout(()=>{{btn.textContent='↻ Update';btn.disabled=false;btn.style.opacity='1';}},2000);
  }} catch(e) {{
    status.textContent='Error: '+e.message;
    btn.textContent='↻ Update';btn.disabled=false;btn.style.opacity='1';
  }}
}}

// ETF toggle buttons
const toggleDiv=document.getElementById('etf-toggles');
etfList.forEach(e=>{{
  const btn=document.createElement('button');
  btn.textContent=e;
  const on=()=>`background:${{etfColors[e]}}22;border:1px solid ${{etfColors[e]}};color:${{etfColors[e]}};`;
  const off=()=>`background:var(--surface);border:1px solid ${{etfColors[e]}}66;color:${{etfColors[e]}}88;`;
  btn.style.cssText=(activeEtfs.has(e)?on():off())+'padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.78rem;font-family:inherit;';
  btn.onclick=()=>{{
    if(activeEtfs.has(e)){{if(activeEtfs.size>1)activeEtfs.delete(e);else return;}}
    else activeEtfs.add(e);
    btn.style.cssText=(activeEtfs.has(e)?on():off())+'padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.78rem;font-family:inherit;';
    buildChart();
  }};
  toggleDiv.appendChild(btn);
}});

// Period buttons
const periodDiv=document.getElementById('period-buttons');
periods.forEach(p=>{{
  const btn=document.createElement('button');
  btn.textContent=p.label;
  btn.style.cssText='background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:4px 12px;border-radius:3px;cursor:pointer;font-size:.75rem;font-family:inherit;';
  btn.onclick=()=>{{
    [chartFrom,chartTo]=getDateRange(p);
    document.getElementById('date-from').value=chartFrom;
    document.getElementById('date-to').value=chartTo;
    if(activeBtn){{activeBtn.style.color='';activeBtn.style.borderColor='';}}
    btn.style.color='#e8eaf0';btn.style.borderColor='#4a5068';
    activeBtn=btn;buildChart();
  }};
  periodDiv.appendChild(btn);
}});

document.getElementById('date-from').value=chartFrom;
document.getElementById('date-to').value=chartTo;
buildChart();
</script>

<!-- SWINGS & HOLDS CHART SECTION -->
<div style="margin-top:48px;border-top:1px solid var(--border);padding-top:36px">
  <div style="border-left:3px solid #2ec4b6;padding-left:16px;margin-bottom:24px">
    <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:var(--text)">Quick Swings &amp; Holds</div>
    <div style="font-size:.75rem;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.08em">Click to toggle · × to remove · type &amp; add new tickers</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:32px;margin-bottom:20px">
    <div>
      <div style="font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Quick Swings</div>
      <div id="swings-toggles" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px"></div>
      <div style="display:flex;gap:6px">
        <input id="swings-add-input" placeholder="TICKER" maxlength="10" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:4px 8px;font-size:.75rem;border-radius:3px;width:90px;font-family:inherit">
        <button onclick="addTicker('swings')" style="background:var(--border);border:1px solid var(--green);color:var(--green);padding:4px 10px;font-size:.75rem;border-radius:3px;cursor:pointer;font-family:inherit">+ Add</button>
      </div>
    </div>
    <div>
      <div style="font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Holding</div>
      <div id="holds-toggles" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px"></div>
      <div style="display:flex;gap:6px">
        <input id="holds-add-input" placeholder="TICKER" maxlength="10" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:4px 8px;font-size:.75rem;border-radius:3px;width:90px;font-family:inherit">
        <button onclick="addTicker('holds')" style="background:var(--border);border:1px solid var(--green);color:var(--green);padding:4px 10px;font-size:.75rem;border-radius:3px;cursor:pointer;font-family:inherit">+ Add</button>
      </div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:12px">
    <div id="swings-period-buttons" style="display:flex;flex-wrap:wrap;gap:8px"></div>
    <button id="swings-mode-btn" onclick="toggleSwingsMode()" style="background:var(--surface);border:1px solid #4a5068;color:var(--muted);padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.78rem;font-family:inherit;margin-left:8px">% change</button>
  </div>
  <div style="font-size:.72rem;color:var(--muted);margin-bottom:12px">
    Custom range:
    <input type="date" id="swings-date-from" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:3px 6px;font-size:.72rem;border-radius:3px;color-scheme:dark">
    →
    <input type="date" id="swings-date-to" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:3px 6px;font-size:.72rem;border-radius:3px;color-scheme:dark">
    <button onclick="applySwingsCustom()" style="background:var(--border);border:1px solid var(--muted);color:var(--text);padding:3px 10px;font-size:.72rem;border-radius:3px;cursor:pointer;margin-left:4px">Apply</button>
  </div>
  <div id="swings-loading" style="display:none;color:var(--green);font-size:.78rem;padding:6px 0">Fetching ticker data...</div>
  <div style="position:relative;width:100%;height:360px">
    <canvas id="swingsChart"></canvas>
  </div>
</div>

<script>
const swingsHoldsAllData = {swings_data_js};
const defaultSwings = {default_swings_js};
const defaultHolds  = {default_holds_js};

const shPalette = ['#FF6B6B','#4ECDC4','#45B7D1','#FFA07A','#A29BFE','#55EFC4','#FFEAA7','#74B9FF','#E17055','#00CEC9','#6C5CE7','#FD79A8','#00B894','#FDCB6E'];
const shColorMap = {{}};
let shColorIdx = 0;
function shColor(t) {{
  if(!shColorMap[t]) shColorMap[t] = shPalette[shColorIdx++ % shPalette.length];
  return shColorMap[t];
}}

let swingsTickers = [...defaultSwings];
let holdsTickers  = [...defaultHolds];
let shActive = new Set([...swingsTickers, ...holdsTickers]);
let shViewMode = 'price';
const _shNow = new Date(); _shNow.setMonth(_shNow.getMonth()-3);
let shFrom = _shNow.toISOString().slice(0,10);
let shTo   = new Date().toISOString().slice(0,10);
let shChartInstance = null;
let shActiveBtn = null;

function shSave() {{
  localStorage.setItem('swingsTickers', JSON.stringify(swingsTickers));
  localStorage.setItem('holdsTickers',  JSON.stringify(holdsTickers));
}}
function shLoad() {{
  try {{
    const s = localStorage.getItem('swingsTickers');
    const h = localStorage.getItem('holdsTickers');
    if(s) swingsTickers = JSON.parse(s);
    if(h) holdsTickers  = JSON.parse(h);
  }} catch(e) {{}}
}}

function renderToggles() {{
  renderGroup('swings-toggles', swingsTickers, 'swings');
  renderGroup('holds-toggles',  holdsTickers,  'holds');
}}
function renderGroup(id, tickers, group) {{
  const div = document.getElementById(id);
  div.innerHTML = '';
  tickers.forEach(t => {{
    const color = shColor(t);
    const wrap  = document.createElement('div');
    wrap.style.cssText = 'display:inline-flex;align-items:center;';
    const btn = document.createElement('button');
    btn.textContent = t;
    const isOn = shActive.has(t);
    const onCSS  = () => `background:${{color}}22;border:1px solid ${{color}};color:${{color}};border-right:none;border-radius:3px 0 0 3px;padding:5px 10px;cursor:pointer;font-size:.78rem;font-family:inherit;`;
    const offCSS = () => `background:var(--surface);border:1px solid ${{color}}44;color:${{color}}88;border-right:none;border-radius:3px 0 0 3px;padding:5px 10px;cursor:pointer;font-size:.78rem;font-family:inherit;`;
    btn.style.cssText = isOn ? onCSS() : offCSS();
    btn.onclick = () => {{
      if(shActive.has(t)) shActive.delete(t); else shActive.add(t);
      btn.style.cssText = shActive.has(t) ? onCSS() : offCSS();
      buildSwingsChart();
    }};
    const del = document.createElement('button');
    del.textContent = '×';
    del.title = 'Remove';
    del.style.cssText = `background:var(--surface);border:1px solid ${{color}}44;color:var(--muted);border-radius:0 3px 3px 0;padding:5px 7px;cursor:pointer;font-size:.9rem;font-family:inherit;line-height:1;`;
    del.onclick = () => {{
      if(group==='swings') swingsTickers = swingsTickers.filter(x=>x!==t);
      else holdsTickers = holdsTickers.filter(x=>x!==t);
      shActive.delete(t);
      shSave(); renderToggles(); buildSwingsChart();
    }};
    wrap.appendChild(btn); wrap.appendChild(del);
    div.appendChild(wrap);
  }});
}}

function buildSwingsChart() {{
  const active = [...swingsTickers, ...holdsTickers].filter(t => shActive.has(t) && swingsHoldsAllData[t]);
  if(!active.length) return;
  const labels = swingsHoldsAllData[active[0]].filter(([d])=>d>=shFrom&&d<=shTo).map(([d])=>d);
  const datasets = active.map(t => {{
    const dm = {{}};
    swingsHoldsAllData[t].forEach(([d,p]) => {{ dm[d]=p; }});
    const raw = labels.map(d => dm[d]??null);
    let dat = raw;
    if(shViewMode==='pct') {{ const base=raw.find(v=>v!=null); dat=raw.map(v=>v==null?null:+((v/base-1)*100).toFixed(2)); }}
    return {{label:t, data:dat, borderColor:shColor(t), borderWidth:1.8, pointRadius:0, pointHoverRadius:4, tension:.1, fill:false, spanGaps:true}};
  }});
  const xhair = {{id:'shXhair', afterDraw(chart) {{
    if(chart._cx==null) return;
    const {{ctx, chartArea:{{top,bottom,left,right}}, scales}} = chart;
    ctx.save();
    ctx.beginPath(); ctx.moveTo(chart._cx,top); ctx.lineTo(chart._cx,bottom);
    ctx.strokeStyle='rgba(200,200,200,.35)'; ctx.lineWidth=1; ctx.setLineDash([4,3]); ctx.stroke();
    if(chart._cy!=null) {{
      ctx.beginPath(); ctx.moveTo(left,chart._cy); ctx.lineTo(right,chart._cy); ctx.stroke();
      const yVal = scales.y.getValueForPixel(chart._cy);
      const lbl  = shViewMode==='pct' ? yVal.toFixed(2)+'%' : '$'+yVal.toFixed(2);
      const lw=ctx.measureText(lbl).width+10, lh=16;
      ctx.setLineDash([]); ctx.fillStyle='rgba(30,35,48,.92)';
      ctx.strokeStyle='rgba(200,200,200,.35)'; ctx.lineWidth=1;
      ctx.beginPath(); ctx.rect(left-lw-2,chart._cy-lh/2,lw,lh); ctx.fill(); ctx.stroke();
      ctx.fillStyle='#e8eaf0'; ctx.font='11px IBM Plex Mono,monospace';
      ctx.textAlign='right'; ctx.textBaseline='middle'; ctx.fillText(lbl,left-5,chart._cy);
    }}
    ctx.restore();
  }}}};
  if(shChartInstance) shChartInstance.destroy();
  shChartInstance = new Chart(document.getElementById('swingsChart'), {{
    type:'line', data:{{labels,datasets}}, plugins:[xhair],
    options:{{
      responsive:true, maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}}, tooltip:{{callbacks:{{label:ctx=>shViewMode==='pct'?` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(2)}}%`:` ${{ctx.dataset.label}}: $${{ctx.parsed.y.toFixed(2)}}`}}}}}},
      scales:{{
        x:{{ticks:{{autoSkip:false,maxRotation:0,color:'#888',font:{{size:11}},callback(val,idx){{
          const d=labels[idx]; if(!d) return '';
          const[yr,mo]=d.split('-'); const q=Math.ceil(parseInt(mo)/3);
          const fi=labels.findIndex(l=>{{const[ly,lm]=l.split('-');return ly===yr&&Math.ceil(parseInt(lm)/3)===q;}});
          return idx===fi?yr+'-'+mo:'';
        }}}}, grid:{{color:'rgba(128,128,128,.08)'}}}},
        y:{{ticks:{{color:'#888',font:{{size:11}},callback:v=>shViewMode==='pct'?v+'%':'$'+v}}, grid:{{color:'rgba(128,128,128,.08)'}}}}
      }},
      onHover(evt,_,chart) {{
        const rect=chart.canvas.getBoundingClientRect(); const ca=chart.chartArea;
        const mx=evt.native?evt.native.clientX-rect.left:null;
        const my=evt.native?evt.native.clientY-rect.top:null;
        if(mx!=null&&mx>=ca.left&&mx<=ca.right&&my>=ca.top&&my<=ca.bottom) {{chart._cx=mx;chart._cy=my;}}
        else {{chart._cx=null;chart._cy=null;}}
        chart.draw();
      }}
    }}
  }});
  shChartInstance.canvas.addEventListener('mouseleave',()=>{{shChartInstance._cx=null;shChartInstance._cy=null;shChartInstance.draw();}});
}}

function toggleSwingsMode() {{
  shViewMode = shViewMode==='price'?'pct':'price';
  const btn = document.getElementById('swings-mode-btn');
  btn.textContent = shViewMode==='pct'?'$ price':'% change';
  btn.style.color = shViewMode==='pct'?'#e8eaf0':'#4a5068';
  btn.style.borderColor = shViewMode==='pct'?'#e8eaf0':'#4a5068';
  buildSwingsChart();
}}

function applySwingsCustom() {{
  const f=document.getElementById('swings-date-from').value;
  const t=document.getElementById('swings-date-to').value;
  if(f&&t) {{ shFrom=f; shTo=t; if(shActiveBtn){{shActiveBtn.style.color='';shActiveBtn.style.borderColor='';shActiveBtn=null;}} buildSwingsChart(); }}
}}

async function addTicker(group) {{
  const input = document.getElementById(group==='swings'?'swings-add-input':'holds-add-input');
  const ticker = input.value.trim().toUpperCase();
  if(!ticker) return;
  const list = group==='swings' ? swingsTickers : holdsTickers;
  if(list.includes(ticker)) {{ input.value=''; return; }}
  const loading = document.getElementById('swings-loading');
  loading.style.display = 'block';
  try {{
    const res  = await fetch('/ticker-data?ticker='+encodeURIComponent(ticker));
    const json = await res.json();
    if(!json.ok) throw new Error(json.error||'Not found');
    swingsHoldsAllData[ticker] = json.data;
    if(group==='swings') swingsTickers.push(ticker);
    else holdsTickers.push(ticker);
    shActive.add(ticker);
    shSave(); renderToggles(); buildSwingsChart();
  }} catch(e) {{
    alert('Could not fetch '+ticker+': '+e.message);
  }} finally {{
    loading.style.display='none';
    input.value='';
  }}
}}

// Period buttons
const shPeriodDiv = document.getElementById('swings-period-buttons');
periods.forEach(p => {{
  const btn = document.createElement('button');
  btn.textContent = p.label;
  btn.style.cssText = 'background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:4px 12px;border-radius:3px;cursor:pointer;font-size:.75rem;font-family:inherit;';
  btn.onclick = () => {{
    [shFrom,shTo] = getDateRange(p);
    document.getElementById('swings-date-from').value = shFrom;
    document.getElementById('swings-date-to').value   = shTo;
    if(shActiveBtn) {{ shActiveBtn.style.color=''; shActiveBtn.style.borderColor=''; }}
    btn.style.color='#e8eaf0'; btn.style.borderColor='#4a5068';
    shActiveBtn=btn; buildSwingsChart();
  }};
  shPeriodDiv.appendChild(btn);
}});

// Enter key support
document.getElementById('swings-add-input').addEventListener('keydown', e=>{{ if(e.key==='Enter') addTicker('swings'); }});
document.getElementById('holds-add-input').addEventListener('keydown',  e=>{{ if(e.key==='Enter') addTicker('holds');  }});

// Init — load persisted lists, fetch any extra tickers not in default data
shLoad();
[...swingsTickers,...holdsTickers].forEach(shColor);
shActive = new Set([...swingsTickers,...holdsTickers]);
document.getElementById('swings-date-from').value = shFrom;
document.getElementById('swings-date-to').value   = shTo;

const _defaultSet    = new Set([...defaultSwings,...defaultHolds]);
const _extraTickers  = [...swingsTickers,...holdsTickers].filter(t=>!_defaultSet.has(t)&&!swingsHoldsAllData[t]);
if(_extraTickers.length) {{
  const loading = document.getElementById('swings-loading');
  loading.style.display = 'block';
  Promise.all(_extraTickers.map(t =>
    fetch('/ticker-data?ticker='+encodeURIComponent(t))
      .then(r=>r.json()).then(j=>{{ if(j.ok) swingsHoldsAllData[t]=j.data; }}).catch(()=>{{}})
  )).then(()=>{{ loading.style.display='none'; renderToggles(); buildSwingsChart(); }});
}} else {{
  renderToggles();
  buildSwingsChart();
}}
</script>
</body>
</html>"""


# ── HTTP Server ───────────────────────────────────────────────────────────────

# Cache — loaded once at startup, refreshed on /update
_cache = {"html": None, "all_data": {}, "lows_data": {}, "current_prices": {}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log spam

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/update":
            self._serve_update()
        elif self.path == "/fintual-data":
            self._serve_fintual()
        elif self.path.startswith("/ticker-data"):
            qs     = parse_qs(urlparse(self.path).query)
            ticker = qs.get("ticker", [""])[0].strip().upper()
            if ticker:
                self._serve_ticker_data(ticker)
            else:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        html = _cache["html"]
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_update(self):
        print("\n  [Update requested] Fetching data from Yahoo Finance...")
        try:
            all_data, lows_data, current_prices = fetch_all()
            last_date = max(rows[-1][0] for rows in all_data.values() if rows)

            # Rebuild HTML and update cache
            _cache["html"] = build_html(all_data, lows_data, current_prices)
            _cache["all_data"]       = all_data
            _cache["lows_data"]      = lows_data
            _cache["current_prices"] = current_prices

            payload = json.dumps({
                "ok": True,
                "lastDate": last_date,
                "allData": all_data,
                "lowsData": {etf: {str(yr): entries for yr, entries in lows.items()}
                             for etf, lows in lows_data.items()},
                "currentPrices": current_prices,
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(payload))
            self.end_headers()
            self.wfile.write(payload)
            print(f"  [Update done] Last date: {last_date}")
        except Exception as e:
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(err))
            self.end_headers()
            self.wfile.write(err)
            print(f"  [Update ERROR] {e}")

    def _serve_fintual(self):
        payload = json.dumps(fetch_fintual_goals()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_ticker_data(self, ticker):
        try:
            rows = fetch_data(ticker)
            _cache["all_data"][ticker] = rows
            payload = json.dumps({"ok": True, "ticker": ticker, "data": rows}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(payload))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(err))
            self.end_headers()
            self.wfile.write(err)
            print(f"  [Ticker fetch ERROR] {ticker}: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  ETF Dashboard Server")
    print("=" * 50)
    print(f"\n  Fetching initial data from Yahoo Finance...\n")

    all_data, lows_data, current_prices = fetch_all()
    _cache["html"]           = build_html(all_data, lows_data, current_prices)
    _cache["all_data"]       = all_data
    _cache["lows_data"]      = lows_data
    _cache["current_prices"] = current_prices

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  Server running at {url}")
    print(f"  Click '↻ Update' in the dashboard to refresh data.")
    print(f"  Press Ctrl+C to stop.\n")

    # Open browser after a short delay
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
