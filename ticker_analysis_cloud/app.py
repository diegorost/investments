"""
Ticker Price Dashboard — Cloud (Railway)
=========================================
Flask server adapted for Railway hosting.

Environment variables:
    PORT  — injected automatically by Railway

Deploy:
    1. Push this file + requirements.txt to a GitHub repo
    2. Connect repo to Railway, set start command:
       python ticker_analysis_cloud.py
"""

import os
import json
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("yfinance not installed. Run: pip install yfinance")

try:
    from flask import Flask, request, redirect, Response
except ImportError:
    raise SystemExit("Flask not installed. Run: pip install flask")

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_data(ticker, period):
    ticker = ticker.upper().strip()
    print(f"Fetching {ticker} ({period})...")
    ticker_obj = yf.Ticker(ticker)
    hist = ticker_obj.history(period=period, auto_adjust=True)

    if hist.empty:
        return None, None, None

    try:
        info = ticker_obj.info
        long_name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        long_name = ticker

    print(f"  {long_name} — {len(hist)} trading days loaded")

    rows = []
    for date, row in hist.iterrows():
        rows.append({
            "date":  date.strftime("%m/%d/%Y"),
            "price": round(float(row["Close"]), 4),
            "high":  round(float(row["High"]),  4),
            "low":   round(float(row["Low"]),   4),
            "open":  round(float(row["Open"]),  4),
            "vol":   f"{row['Volume']:,.0f}",
            "change": ""
        })

    data_js = json.dumps(rows)
    return long_name, rows, data_js

# ── HTML builder ──────────────────────────────────────────────────────────────

def build_html(ticker, long_name, rows, data_js, period="1y"):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    n = len(rows)

    period_options = ""
    for val, label in [("1mo","1M"), ("3mo","3M"), ("6mo","6M"), ("1y","1Y"), ("2y","2Y"), ("5y","5Y"), ("10y","10Y"), ("max","Max")]:
        selected = ' selected' if val == period else ''
        period_options += f'<option value="{val}"{selected}>{label}</option>'

    search_bar = f"""
<form class="ticker-search" method="GET" action="/dashboard">
  <input type="text" name="ticker" value="{ticker}" placeholder="Ticker symbol…" autocomplete="off" autocapitalize="characters" spellcheck="false">
  <button type="submit" class="apply-btn">Search</button>
</form>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ticker} — Price Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #09090f; --panel: #111118; --border: #1e1e2e;
    --accent: #f0c040; --accent2: #e05a5a; --accent3: #5ab4e0;
    --text: #e8e8f0; --muted: #6b6b88; --green: #4ade80; --red: #f87171;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Syne', sans-serif; min-height: 100vh; padding: 32px 24px; }}
  .header {{ display: flex; align-items: baseline; gap: 16px; margin-bottom: 20px; }}
  .header h1 {{ font-size: 2.8rem; font-weight: 800; letter-spacing: -1px; color: var(--accent); line-height: 1; }}
  .header .sub {{ font-family: 'Space Mono', monospace; font-size: 0.75rem; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; }}
  .ticker-search {{ display: flex; gap: 8px; align-items: center; flex-wrap: nowrap; }}
  .ticker-search input[type="text"] {{
    font-family: 'Space Mono', monospace; font-size: 0.85rem; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; padding: 9px 14px; background: var(--panel);
    border: 1px solid var(--border); color: var(--accent); border-radius: 4px;
    outline: none; width: 140px; transition: border-color 0.15s;
  }}
  .ticker-search input[type="text"]:focus {{ border-color: var(--accent); }}
  .ticker-search select {{
    font-family: 'Space Mono', monospace; font-size: 0.75rem; padding: 9px 12px;
    background: var(--panel); border: 1px solid var(--border); color: var(--text);
    border-radius: 4px; outline: none; cursor: pointer; transition: border-color 0.15s;
  }}
  .ticker-search select:focus {{ border-color: var(--accent); }}
  .topbar {{ display: flex; flex-wrap: nowrap; gap: 10px; align-items: center; margin-bottom: 24px; overflow-x: auto; }}
  .preset-btns {{ display: flex; gap: 6px; }}
  .btn {{ font-family: 'Space Mono', monospace; font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; padding: 7px 14px; border: 1px solid var(--border); background: var(--panel); color: var(--muted); cursor: pointer; border-radius: 4px; transition: all 0.15s; text-transform: uppercase; }}
  .btn:hover {{ border-color: var(--accent); color: var(--accent); }}
  .btn.active {{ border-color: var(--accent); background: rgba(240,192,64,0.1); color: var(--accent); }}
  .date-inputs {{ display: flex; align-items: center; gap: 8px; margin-left: auto; }}
  .date-inputs label {{ font-family: 'Space Mono', monospace; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}
  .date-inputs input[type="date"] {{ font-family: 'Space Mono', monospace; font-size: 0.75rem; padding: 7px 10px; background: var(--panel); border: 1px solid var(--border); color: var(--text); border-radius: 4px; outline: none; cursor: pointer; transition: border-color 0.15s; }}
  .date-inputs input[type="date"]:focus {{ border-color: var(--accent); }}
  .apply-btn {{ font-family: 'Space Mono', monospace; font-size: 0.7rem; font-weight: 700; padding: 7px 16px; background: var(--accent); color: #09090f; border: none; border-radius: 4px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; transition: opacity 0.15s; }}
  .apply-btn:hover {{ opacity: 0.85; }}
  .chart-panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 24px; margin-bottom: 24px; position: relative; }}
  .chart-panel canvas {{ max-height: 400px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .stat-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 18px 20px; transition: border-color 0.15s; }}
  .stat-card:hover {{ border-color: var(--accent); }}
  .stat-label {{ font-family: 'Space Mono', monospace; font-size: 0.65rem; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }}
  .stat-value {{ font-size: 1.6rem; font-weight: 800; line-height: 1; }}
  .stat-sub {{ font-family: 'Space Mono', monospace; font-size: 0.65rem; color: var(--muted); margin-top: 4px; }}
  .stat-card.high .stat-value {{ color: var(--green); }}
  .stat-card.low .stat-value {{ color: var(--red); }}
  .stat-card.range .stat-value {{ color: var(--accent3); }}
  .stat-card.count .stat-value {{ color: var(--accent); }}
  .stat-card.change-pos .stat-value {{ color: var(--green); }}
  .stat-card.change-neg .stat-value {{ color: var(--red); }}
  .table-section h2 {{ font-size: 0.8rem; font-family: 'Space Mono', monospace; letter-spacing: 3px; text-transform: uppercase; color: var(--muted); margin-bottom: 16px; }}
  .top-tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 640px) {{
    .top-tables {{ grid-template-columns: 1fr; }}
    .header h1 {{ font-size: 2rem; }}
    .date-inputs {{ margin-left: 0; }}
    .controls {{ flex-direction: column; align-items: flex-start; }}
    .ticker-search {{ gap: 6px; }}
  }}
  table {{ width: 100%; border-collapse: collapse; font-family: 'Space Mono', monospace; font-size: 0.72rem; }}
  thead th {{ text-align: left; padding: 10px 12px; font-size: 0.62rem; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); }}
  tbody tr {{ transition: background 0.1s; }}
  tbody tr:hover {{ background: rgba(240,192,64,0.04); }}
  tbody td {{ padding: 9px 12px; border-bottom: 1px solid rgba(30,30,46,0.6); color: var(--text); }}
  .rank {{ color: var(--muted); font-size: 0.6rem; }}
  .tbl-high {{ color: var(--green); font-weight: 700; }}
  .tbl-low {{ color: var(--red); font-weight: 700; }}
  .table-panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }}
  .table-panel h3 {{ font-size: 0.7rem; font-family: 'Space Mono', monospace; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 14px; }}
  .table-panel.highs h3 {{ color: var(--green); }}
  .table-panel.lows h3 {{ color: var(--red); }}
  .divider {{ height: 1px; background: var(--border); margin: 28px 0; }}
  .generated {{ font-family: 'Space Mono', monospace; font-size: 0.6rem; color: var(--muted); text-align: right; margin-top: 32px; }}
  .error-msg {{ font-family: 'Space Mono', monospace; font-size: 0.9rem; color: var(--red); background: var(--panel); border: 1px solid var(--red); border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; }}
</style>
</head>
<body>

<div class="header">
  <h1>{ticker}</h1>
  <div>
    <div class="sub">{long_name}</div>
    <div class="sub">Price History Dashboard</div>
  </div>
</div>

<div class="topbar">
{search_bar}
  <div class="preset-btns">
    <button class="btn" onclick="setPreset('1W')">1W</button>
    <button class="btn" onclick="setPreset('2W')">2W</button>
    <button class="btn" onclick="setPreset('3W')">3W</button>
    <button class="btn" onclick="setPreset('1Y')">1Y</button>
    <button class="btn" onclick="setPreset('3Y')">3Y</button>
    <button class="btn" onclick="setPreset('5Y')">5Y</button>
    <button class="btn" onclick="setPreset('10Y')">10Y</button>
    <button class="btn" onclick="setPreset('MAX')">MAX</button>
  </div>
  <div class="mode-toggle" style="display:flex;gap:6px;">
    <button class="btn active" id="btnPrice" onclick="setMode('price')">$ Price</button>
    <button class="btn" id="btnPct" onclick="setMode('pct')">% Change</button>
  </div>
  <button class="btn" id="btnReset" onclick="resetZoom()" style="display:none; border-color:#5ab4e0; color:#5ab4e0;">↩ Reset Zoom</button>
  <div class="date-inputs">
    <label>From</label>
    <input type="date" id="dateFrom">
    <label>To</label>
    <input type="date" id="dateTo">
    <button class="apply-btn" onclick="applyCustomRange()">Apply</button>
  </div>
</div>

<div class="stats-grid" id="statsGrid"></div>

<div id="indicatorsGrid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px;"></div>

<div class="chart-panel">
  <canvas id="priceChart"></canvas>
</div>

<div class="chart-panel" style="margin-top:16px;">
  <div style="font-family:'Space Mono',monospace;font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:12px;">Drawdown from Period High</div>
  <canvas id="drawdownChart" style="max-height:180px;"></canvas>
</div>

<div class="divider"></div>

<div class="table-section">
  <h2>Top Highs &amp; Lows in Selected Period</h2>
  <div class="top-tables">
    <div class="table-panel highs">
      <h3>▲ Top 10 Highest Intraday Highs</h3>
      <table>
        <thead><tr><th>#</th><th>Date</th><th>High</th><th>Close</th><th>Open</th></tr></thead>
        <tbody id="highsTable"></tbody>
      </table>
    </div>
    <div class="table-panel lows">
      <h3>▼ Top 10 Lowest Intraday Lows</h3>
      <table>
        <thead><tr><th>#</th><th>Date</th><th>Low</th><th>Close</th><th>Open</th></tr></thead>
        <tbody id="lowsTable"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="generated">Generated {now} · yfinance · {n} trading days</div>

<script>
const RAW = {data_js};

function parseDate(str) {{
  const [m,d,y] = str.split('/');
  return new Date(+y, +m-1, +d);
}}

const allData = RAW.map(r => ({{
  date: parseDate(r.date),
  dateStr: r.date,
  price: parseFloat(r.price),
  high:  parseFloat(r.high),
  low:   parseFloat(r.low),
  open:  parseFloat(r.open),
  vol:   r.vol
}})).sort((a,b) => a.date - b.date);

function computeSMA(arr, period) {{
  return arr.map((_, i) => {{
    if (i < period - 1) return null;
    return arr.slice(i - period + 1, i + 1).reduce((s, v) => s + v, 0) / period;
  }});
}}

function computeEMA(arr, period) {{
  const k = 2 / (period + 1);
  const out = new Array(arr.length).fill(null);
  out[period - 1] = arr.slice(0, period).reduce((s, v) => s + v, 0) / period;
  for (let i = period; i < arr.length; i++)
    out[i] = arr[i] * k + out[i - 1] * (1 - k);
  return out;
}}

function computeRSI(arr, period) {{
  const out = new Array(arr.length).fill(null);
  if (arr.length < period + 1) return out;
  let ag = 0, al = 0;
  for (let i = 1; i <= period; i++) {{
    const d = arr[i] - arr[i - 1];
    if (d > 0) ag += d; else al -= d;
  }}
  ag /= period; al /= period;
  out[period] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  for (let i = period + 1; i < arr.length; i++) {{
    const d = arr[i] - arr[i - 1];
    ag = (ag * (period - 1) + (d > 0 ? d : 0)) / period;
    al = (al * (period - 1) + (d < 0 ? -d : 0)) / period;
    out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  }}
  return out;
}}

(function() {{
  const cls = allData.map(d => d.price);
  const s20 = computeSMA(cls, 20), s50 = computeSMA(cls, 50), s200 = computeSMA(cls, 200);
  const e12 = computeEMA(cls, 12), e26 = computeEMA(cls, 26);
  const r14 = computeRSI(cls, 14);
  allData.forEach((d, i) => {{
    d.sma20 = s20[i]; d.sma50 = s50[i]; d.sma200 = s200[i];
    d.ema12 = e12[i]; d.ema26 = e26[i];
    d.rsi14 = r14[i];
  }});
}})();

const minDate = allData[0].date;
const maxDate = allData[allData.length-1].date;

function toInputDate(d) {{ return d.toISOString().split('T')[0]; }}

document.getElementById('dateFrom').value = toInputDate(minDate);
document.getElementById('dateTo').value   = toInputDate(maxDate);
document.getElementById('dateFrom').min = toInputDate(minDate);
document.getElementById('dateFrom').max = toInputDate(maxDate);
document.getElementById('dateTo').min   = toInputDate(minDate);
document.getElementById('dateTo').max   = toInputDate(maxDate);

let chart = null;
let drawdownChart = null;
let chartMode = 'price';
let lastFrom = null, lastTo = null;

function setMode(mode) {{
  chartMode = mode;
  document.getElementById('btnPrice').classList.toggle('active', mode === 'price');
  document.getElementById('btnPct').classList.toggle('active', mode === 'pct');
  if (lastFrom && lastTo) render(lastFrom, lastTo);
}}

function getFilteredData(from, to) {{
  return allData.filter(r => r.date >= from && r.date <= to);
}}

function setPreset(p) {{
  document.querySelectorAll('.preset-btns .btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  const to = maxDate;
  let from = new Date(maxDate);
  if      (p === '1W')  from.setDate(from.getDate()-7);
  else if (p === '2W')  from.setDate(from.getDate()-14);
  else if (p === '3W')  from.setDate(from.getDate()-21);
  else if (p === '1Y')  from.setFullYear(from.getFullYear()-1);
  else if (p === '3Y')  from.setFullYear(from.getFullYear()-3);
  else if (p === '5Y')  from.setFullYear(from.getFullYear()-5);
  else if (p === '10Y') from.setFullYear(from.getFullYear()-10);
  else                  {{ from = minDate; }}
  document.getElementById('dateFrom').value = toInputDate(from);
  document.getElementById('dateTo').value   = toInputDate(to);
  render(from, to);
}}

function applyCustomRange() {{
  document.querySelectorAll('.preset-btns .btn').forEach(b => b.classList.remove('active'));
  const from = new Date(document.getElementById('dateFrom').value + 'T00:00:00');
  const to   = new Date(document.getElementById('dateTo').value   + 'T00:00:00');
  render(from, to);
}}

function resetZoom() {{
  document.getElementById('dateFrom').value = toInputDate(minDate);
  document.getElementById('dateTo').value   = toInputDate(maxDate);
  document.querySelectorAll('.preset-btns .btn').forEach((b,i) => b.classList.toggle('active', i===5));
  document.getElementById('btnReset').style.display = 'none';
  render(minDate, maxDate);
}}

function fmtPrice(v) {{ return '$' + v.toFixed(2); }}
function fmtDate(d)  {{ return d.toLocaleDateString('en-US', {{month:'short', day:'numeric', year:'numeric'}}); }}

function render(from, to) {{
  lastFrom = from; lastTo = to;
  const isFullRange = from <= minDate && to >= maxDate;
  document.getElementById('btnReset').style.display = isFullRange ? 'none' : 'inline-block';

  const data = getFilteredData(from, to);
  if (data.length === 0) return;

  const topHighRow = data.reduce((a,b) => b.high > a.high ? b : a);
  const topLowRow  = data.reduce((a,b) => b.low  < a.low  ? b : a);
  const first = data[0].price, last = data[data.length-1].price;
  const pctChange = (last - first) / first * 100;
  const isPos = pctChange >= 0;

  document.getElementById('statsGrid').innerHTML = `
    <div class="stat-card high">
      <div class="stat-label">Period High</div>
      <div class="stat-value">$${{topHighRow.high.toFixed(2)}}</div>
      <div class="stat-sub">${{fmtDate(topHighRow.date)}}</div>
    </div>
    <div class="stat-card low">
      <div class="stat-label">Period Low</div>
      <div class="stat-value">$${{topLowRow.low.toFixed(2)}}</div>
      <div class="stat-sub">${{fmtDate(topLowRow.date)}}</div>
    </div>
    <div class="stat-card range">
      <div class="stat-label">High / Low Range</div>
      <div class="stat-value">$${{(topHighRow.high - topLowRow.low).toFixed(2)}}</div>
      <div class="stat-sub">${{((topHighRow.high - topLowRow.low) / topLowRow.low * 100).toFixed(1)}}% spread</div>
    </div>
    <div class="stat-card ${{isPos ? 'change-pos' : 'change-neg'}}">
      <div class="stat-label">Period Return</div>
      <div class="stat-value">${{isPos?'+':''}}${{pctChange.toFixed(1)}}%</div>
      <div class="stat-sub">${{fmtPrice(first)}} → ${{fmtPrice(last)}}</div>
    </div>
    <div class="stat-card count">
      <div class="stat-label">Trading Days</div>
      <div class="stat-value">${{data.length}}</div>
      <div class="stat-sub">${{fmtDate(data[0].date)}} – ${{fmtDate(data[data.length-1].date)}}</div>
    </div>
  `;

  const labels = data.map(d => d.date);
  const base = data[0].price;
  const isPct = chartMode === 'pct';
  const toVal = (v) => isPct ? ((v - base) / base * 100) : v;
  const closePrices = data.map(d => toVal(d.price));

  if (chart) chart.destroy();
  const ctx = document.getElementById('priceChart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 400);
  gradient.addColorStop(0, 'rgba(240,192,64,0.25)');
  gradient.addColorStop(1, 'rgba(240,192,64,0.01)');

  chart = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{
          label: 'Close',
          data: closePrices,
          borderColor: '#f0c040',
          backgroundColor: gradient,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#f0c040',
          fill: true,
          tension: 0.2,
          order: 1
        }},
        {{
          label: 'High',
          data: data.map(d => toVal(d.high)),
          borderColor: '#4ade80',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          borderDash: [4, 3],
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#4ade80',
          fill: false,
          tension: 0.2,
          order: 2
        }},
        {{
          label: 'Open',
          data: data.map(d => toVal(d.open)),
          borderColor: '#f0c040',
          backgroundColor: 'transparent',
          borderWidth: 1,
          borderDash: [2, 4],
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#f0c040',
          fill: false,
          tension: 0.2,
          order: 3
        }},
        {{
          label: 'Low',
          data: data.map(d => toVal(d.low)),
          borderColor: '#f87171',
          backgroundColor: 'transparent',
          borderWidth: 1,
          borderDash: [3, 3],
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#f87171',
          fill: false,
          tension: 0.2,
          order: 4
        }},
        {{
          label: 'SMA 20',
          data: data.map(d => d.sma20 != null ? toVal(d.sma20) : null),
          borderColor: '#5ab4e0',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#5ab4e0',
          fill: false,
          tension: 0.2,
          spanGaps: false,
          order: 5
        }},
        {{
          label: 'SMA 50',
          data: data.map(d => d.sma50 != null ? toVal(d.sma50) : null),
          borderColor: '#c084fc',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#c084fc',
          fill: false,
          tension: 0.2,
          spanGaps: false,
          order: 6
        }},
        {{
          label: 'EMA 12',
          data: data.map(d => d.ema12 != null ? toVal(d.ema12) : null),
          borderColor: '#fb923c',
          backgroundColor: 'transparent',
          borderWidth: 1,
          borderDash: [5, 2],
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#fb923c',
          fill: false,
          tension: 0.2,
          spanGaps: false,
          order: 7
        }},
        {{
          label: 'EMA 26',
          data: data.map(d => d.ema26 != null ? toVal(d.ema26) : null),
          borderColor: '#e879f9',
          backgroundColor: 'transparent',
          borderWidth: 1,
          borderDash: [5, 2],
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#e879f9',
          fill: false,
          tension: 0.2,
          spanGaps: false,
          order: 8
        }},
        {{
          label: 'SMA 200',
          data: data.map(d => d.sma200 != null ? toVal(d.sma200) : null),
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#f59e0b',
          fill: false,
          tension: 0.2,
          spanGaps: false,
          order: 9
        }}
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{
          display: true, position: 'top', align: 'end',
          labels: {{ color: '#6b6b88', font: {{ family: 'Space Mono', size: 10 }}, boxWidth: 24, boxHeight: 2, padding: 16 }}
        }},
        tooltip: {{
          backgroundColor: '#111118', borderColor: '#1e1e2e', borderWidth: 1,
          titleColor: '#f0c040', bodyColor: '#e8e8f0',
          titleFont: {{ family: 'Space Mono', size: 11 }},
          bodyFont:  {{ family: 'Space Mono', size: 11 }},
          padding: 12,
          callbacks: {{
            title: (items) => fmtDate(new Date(items[0].parsed.x)),
            label: (item) => isPct
              ? ` ${{item.dataset.label}}: ${{item.parsed.y >= 0 ? '+' : ''}}${{item.parsed.y.toFixed(2)}}%`
              : ` ${{item.dataset.label}}: $${{item.parsed.y.toFixed(2)}}`
          }}
        }}
      }},
      scales: {{
        x: {{
          type: 'time',
          time: {{ unit: data.length > 500 ? 'year' : data.length > 120 ? 'month' : 'week' }},
          grid: {{ color: '#1e1e2e' }},
          ticks: {{ color: '#6b6b88', font: {{ family: 'Space Mono', size: 10 }} }}
        }},
        y: {{
          grid: {{ color: '#1e1e2e' }},
          ticks: {{
            color: '#6b6b88',
            font: {{ family: 'Space Mono', size: 10 }},
            callback: v => isPct ? (v >= 0 ? '+' : '') + v.toFixed(1) + '%' : '$' + v.toFixed(0)
          }}
        }}
      }}
    }}
  }});

  // Drawdown chart
  let peak = data[0].price;
  const ddValues = data.map(d => {{
    if (d.price > peak) peak = d.price;
    return +((( d.price - peak) / peak) * 100).toFixed(4);
  }});

  if (drawdownChart) drawdownChart.destroy();
  const ddCtx = document.getElementById('drawdownChart').getContext('2d');
  const ddGrad = ddCtx.createLinearGradient(0, 0, 0, 180);
  ddGrad.addColorStop(0, 'rgba(248,113,113,0.0)');
  ddGrad.addColorStop(1, 'rgba(248,113,113,0.28)');

  drawdownChart = new Chart(ddCtx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: 'Drawdown',
        data: ddValues,
        borderColor: '#f87171',
        backgroundColor: ddGrad,
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: '#f87171',
        fill: true,
        tension: 0.2
      }}]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#111118', borderColor: '#1e1e2e', borderWidth: 1,
          titleColor: '#f0c040', bodyColor: '#e8e8f0',
          titleFont: {{ family: 'Space Mono', size: 11 }},
          bodyFont:  {{ family: 'Space Mono', size: 11 }},
          padding: 12,
          callbacks: {{
            title: (items) => fmtDate(new Date(items[0].parsed.x)),
            label: (item) => ` Drawdown: ${{item.parsed.y.toFixed(2)}}%`
          }}
        }}
      }},
      scales: {{
        x: {{
          type: 'time',
          time: {{ unit: data.length > 500 ? 'year' : data.length > 120 ? 'month' : 'week' }},
          grid: {{ color: '#1e1e2e' }},
          ticks: {{ color: '#6b6b88', font: {{ family: 'Space Mono', size: 10 }} }}
        }},
        y: {{
          max: 0,
          grid: {{ color: '#1e1e2e' }},
          ticks: {{
            color: '#6b6b88',
            font: {{ family: 'Space Mono', size: 10 }},
            callback: v => v.toFixed(0) + '%'
          }}
        }}
      }}
    }}
  }});

  // Indicator cards
  const lastD = [...data].reverse().find(d => d.rsi14 != null) || data[data.length - 1];
  const curP  = data[data.length - 1].price;
  const iRsi  = lastD ? lastD.rsi14  : null;
  const iS20  = lastD ? lastD.sma20  : null;
  const iS50  = lastD ? lastD.sma50  : null;
  const iS200 = lastD ? lastD.sma200 : null;
  const iE12  = lastD ? lastD.ema12  : null;
  const iE26  = lastD ? lastD.ema26  : null;
  const vsS20  = iS20  != null ? (curP - iS20)  / iS20  * 100 : null;
  const vsS50  = iS50  != null ? (curP - iS50)  / iS50  * 100 : null;
  const vsS200 = iS200 != null ? (curP - iS200) / iS200 * 100 : null;
  const rsiClr = iRsi == null ? '#6b6b88' : iRsi >= 70 ? '#f87171' : iRsi <= 30 ? '#4ade80' : '#f0c040';
  const signClr = (v) => v == null ? '#6b6b88' : v >= 0 ? '#4ade80' : '#f87171';
  const fmtPct  = (v) => v != null ? (v >= 0 ? '+' : '') + v.toFixed(2) + '%' : '—';

  document.getElementById('indicatorsGrid').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">RSI (14)</div>
      <div class="stat-value" style="color:${{rsiClr}};font-size:1.35rem">${{iRsi != null ? iRsi.toFixed(1) : '—'}}</div>
      <div class="stat-sub">${{iRsi != null ? (iRsi >= 70 ? 'Overbought' : iRsi <= 30 ? 'Oversold' : 'Neutral') : 'N/A'}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">SMA 20</div>
      <div class="stat-value" style="color:#5ab4e0;font-size:1.25rem">${{iS20 != null ? '$' + iS20.toFixed(2) : '—'}}</div>
      <div class="stat-sub" style="color:${{signClr(vsS20)}}">${{vsS20 != null ? fmtPct(vsS20) + ' vs price' : ''}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">SMA 50</div>
      <div class="stat-value" style="color:#c084fc;font-size:1.25rem">${{iS50 != null ? '$' + iS50.toFixed(2) : '—'}}</div>
      <div class="stat-sub" style="color:${{signClr(vsS50)}}">${{vsS50 != null ? fmtPct(vsS50) + ' vs price' : ''}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">SMA 200</div>
      <div class="stat-value" style="color:#f59e0b;font-size:1.25rem">${{iS200 != null ? '$' + iS200.toFixed(2) : '—'}}</div>
      <div class="stat-sub" style="color:${{signClr(vsS200)}}">${{vsS200 != null ? fmtPct(vsS200) + ' vs price' : ''}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">EMA 12</div>
      <div class="stat-value" style="color:#fb923c;font-size:1.25rem">${{iE12 != null ? '$' + iE12.toFixed(2) : '—'}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">EMA 26</div>
      <div class="stat-value" style="color:#e879f9;font-size:1.25rem">${{iE26 != null ? '$' + iE26.toFixed(2) : '—'}}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">vs SMA 20</div>
      <div class="stat-value" style="font-size:1.35rem;color:${{signClr(vsS20)}}">${{fmtPct(vsS20)}}</div>
      <div class="stat-sub">price vs SMA 20</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">vs SMA 50</div>
      <div class="stat-value" style="font-size:1.35rem;color:${{signClr(vsS50)}}">${{fmtPct(vsS50)}}</div>
      <div class="stat-sub">price vs SMA 50</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">vs SMA 200</div>
      <div class="stat-value" style="font-size:1.35rem;color:${{signClr(vsS200)}}">${{fmtPct(vsS200)}}</div>
      <div class="stat-sub">price vs SMA 200</div>
    </div>
  `;

  const crosshairPlugin = {{
    id: 'crosshair',
    afterDraw(chart) {{
      if (chart._crosshairX == null) return;
      const {{ ctx, chartArea: {{ top, bottom, left, right }}, scales }} = chart;
      const x = chart._crosshairX, y = chart._crosshairY;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(240,192,64,0.45)';
      ctx.beginPath(); ctx.moveTo(x, top);  ctx.lineTo(x, bottom); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y);  ctx.stroke();
      const price = scales.y.getValueForPixel(y);
      const priceLabel = chartMode === 'pct'
        ? (price >= 0 ? '+' : '') + price.toFixed(2) + '%'
        : '$' + price.toFixed(2);
      const labelW = 72, labelH = 18;
      ctx.fillStyle = 'rgba(240,192,64,0.9)';
      ctx.fillRect(left - labelW - 4, y - labelH / 2, labelW, labelH);
      ctx.fillStyle = '#09090f';
      ctx.font = '10px Space Mono, monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(priceLabel, left - 8, y);
      ctx.restore();
    }}
  }};
  Chart.register(crosshairPlugin);

  const canvas = document.getElementById('priceChart');
  let drag = {{ active: false, startX: null, endX: null }};

  function getChartDate(px) {{ return chart.scales.x.getValueForPixel(px); }}
  function clampToChart(x) {{
    const ca = chart.chartArea;
    return Math.max(ca.left, Math.min(ca.right, x));
  }}

  const selPlugin = {{
    id: 'selectionOverlay',
    afterDraw(c) {{
      if (!drag.active || drag.startX == null || drag.endX == null) return;
      const {{ ctx, chartArea: {{ top, bottom }} }} = c;
      const x1 = Math.min(drag.startX, drag.endX);
      const x2 = Math.max(drag.startX, drag.endX);
      ctx.save();
      ctx.fillStyle = 'rgba(90, 180, 224, 0.12)';
      ctx.fillRect(x1, top, x2 - x1, bottom - top);
      ctx.strokeStyle = 'rgba(90, 180, 224, 0.6)';
      ctx.lineWidth = 1; ctx.setLineDash([]);
      ctx.beginPath(); ctx.moveTo(x1, top); ctx.lineTo(x1, bottom); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x2, top); ctx.lineTo(x2, bottom); ctx.stroke();
      const fmt = (ms) => new Date(ms).toLocaleDateString('en-US', {{month:'short', day:'numeric', year:'numeric'}});
      ctx.font = '10px Space Mono, monospace';
      ctx.fillStyle = 'rgba(90,180,224,0.9)';
      ctx.textAlign = 'center';
      ctx.fillText(fmt(getChartDate(x1)), x1, top - 6);
      ctx.fillText(fmt(getChartDate(x2)), x2, top - 6);
      ctx.restore();
    }}
  }};
  Chart.register(selPlugin);

  canvas.onmousedown = (e) => {{
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ca = chart.chartArea;
    if (x >= ca.left && x <= ca.right) {{
      drag.active = true;
      drag.startX = clampToChart(x);
      drag.endX = drag.startX;
      canvas.style.cursor = 'crosshair';
    }}
  }};

  canvas.onmousemove = (e) => {{
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const ca = chart.chartArea;
    if (drag.active) {{
      drag.endX = clampToChart(x);
      chart._crosshairX = null; chart._crosshairY = null;
    }} else {{
      if (x >= ca.left && x <= ca.right && y >= ca.top && y <= ca.bottom) {{
        chart._crosshairX = x; chart._crosshairY = y;
        canvas.style.cursor = 'crosshair';
      }} else {{
        chart._crosshairX = null; chart._crosshairY = null;
        canvas.style.cursor = 'default';
      }}
    }}
    chart.draw();
  }};

  canvas.onmouseup = (e) => {{
    if (!drag.active) return;
    drag.active = false;
    canvas.style.cursor = 'default';
    const x1 = Math.min(drag.startX, drag.endX);
    const x2 = Math.max(drag.startX, drag.endX);
    drag.startX = null; drag.endX = null;
    chart.draw();
    if (x2 - x1 < 10) return;
    const from = new Date(getChartDate(x1));
    const to   = new Date(getChartDate(x2));
    document.getElementById('dateFrom').value = toInputDate(from);
    document.getElementById('dateTo').value   = toInputDate(to);
    document.querySelectorAll('.preset-btns .btn').forEach(b => b.classList.remove('active'));
    render(from, to);
  }};

  canvas.onmouseleave = () => {{
    if (drag.active) {{ drag.active = false; drag.startX = null; drag.endX = null; }}
    chart._crosshairX = null; chart._crosshairY = null;
    chart.draw();
  }};

  const top10highs = [...data].sort((a,b) => b.high - a.high).slice(0,10);
  const top10lows  = [...data].sort((a,b) => a.low  - b.low ).slice(0,10);

  document.getElementById('highsTable').innerHTML = top10highs.map((r,i) => `
    <tr>
      <td class="rank">#${{i+1}}</td>
      <td>${{fmtDate(r.date)}}</td>
      <td class="tbl-high">$${{r.high.toFixed(2)}}</td>
      <td>$${{r.price.toFixed(2)}}</td>
      <td style="color:var(--accent3)">$${{r.open.toFixed(2)}}</td>
    </tr>`).join('');

  document.getElementById('lowsTable').innerHTML = top10lows.map((r,i) => `
    <tr>
      <td class="rank">#${{i+1}}</td>
      <td>${{fmtDate(r.date)}}</td>
      <td class="tbl-low">$${{r.low.toFixed(2)}}</td>
      <td>$${{r.price.toFixed(2)}}</td>
      <td style="color:var(--accent3)">$${{r.open.toFixed(2)}}</td>
    </tr>`).join('');
}}

const initFrom = new Date(maxDate);
initFrom.setFullYear(initFrom.getFullYear() - 1);
document.getElementById('dateFrom').value = toInputDate(initFrom);
render(initFrom, maxDate);
</script>
</body>
</html>"""

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def index():
    return redirect("/dashboard?ticker=GC%3DF&period=1y")

@app.route("/dashboard")
def dashboard():
    ticker = request.args.get("ticker", "GC=F").upper().strip()
    period = "max"

    long_name, rows, data_js = fetch_data(ticker, period)

    if rows is None:
        error_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Error</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;800&display=swap" rel="stylesheet">
<style>
  body {{ background:#09090f; color:#e8e8f0; font-family:'Syne',sans-serif; padding:48px 32px; }}
  .error {{ color:#f87171; font-family:'Space Mono',monospace; font-size:0.9rem;
            background:#111118; border:1px solid #f87171; border-radius:8px; padding:20px 24px; margin-bottom:24px; }}
  a {{ color:#f0c040; font-family:'Space Mono',monospace; font-size:0.8rem; }}
</style></head><body>
<div class="error">No data found for ticker: <strong>{ticker}</strong><br>
Check the symbol and try again.</div>
<a href="javascript:history.back()">← Go back</a>
</body></html>"""
        return Response(error_html, status=404, mimetype="text/html")

    html = build_html(ticker, long_name, rows, data_js, period=period)
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nTicker Dashboard running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
