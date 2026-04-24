#!/usr/bin/env python3
"""
ETF Dashboard Generator
=======================
Downloads live data from Yahoo Finance and generates etf_lows.html.
No CSV files needed — just run the script.

Usage:
    python generar_dashboard.py

Requirements:
    - Python 3.8+
    - yfinance:  pip install yfinance

Every week (or whenever you want):
    1. Run: python generar_dashboard.py
    2. Open etf_lows.html in your browser
"""

import json
import os
import sys
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("\n  ERROR: yfinance not installed.")
    print("  Run:  pip install yfinance\n")
    sys.exit(1)

# ── Configuration ───────────────────────────────────────────────────────────────

ETFS = ["UPRO", "TQQQ", "TECL", "SOXL"]

# Output file (same folder as this script)
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_lows.html")

# Start year for the lows table and chart
START_YEAR = 2022

# Top N lows per year (table)
TOP_N = 3
MAX_PER_YEAR = 2      # max to show in table (the 2 lowest of the year)
GAP_DAYS = 30         # minimum days between two lows in the same year

# ── Yahoo Finance Download ───────────────────────────────────────────────────────

def fetch_data(etf):
    """Downloads historical daily closes from Yahoo Finance since START_YEAR."""
    print(f"  Downloading {etf}...", end=" ", flush=True)
    ticker = yf.Ticker(etf)
    df = ticker.history(start=f"{START_YEAR}-01-01", interval="1d")
    if df.empty:
        raise ValueError(f"No data returned for {etf}")
    rows = [
        [dt.strftime("%Y-%m-%d"), round(float(close), 3)]
        for dt, close in zip(df.index, df["Close"])
        if not __import__("math").isnan(float(close))
    ]
    rows.sort(key=lambda x: x[0])
    return rows

# ── Lows Calculation ────────────────────────────────────────────────────────────

def compute_lows(rows, start_year=START_YEAR, top_n=TOP_N, max_per_year=MAX_PER_YEAR, gap_days=GAP_DAYS):
    """
    Computes the top_n annual lows since start_year,
    with a maximum of max_per_year per year and gap_days separation.
    Returns dict {year: [[month_abbr, price], ...]}
    """
    by_year = {}
    for date_str, price in rows:
        yr = int(date_str[:4])
        if yr < start_year:
            continue
        by_year.setdefault(yr, []).append((datetime.strptime(date_str, "%Y-%m-%d"), price))

    MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    result = {}
    for yr, pts in sorted(by_year.items()):
        pts.sort(key=lambda x: x[1])  # sort by price ascending
        selected = []
        for dt, price in pts:
            # Check gap with already selected
            too_close = any(abs((dt - s[0]).days) < gap_days for s in selected)
            if too_close:
                continue
            selected.append((dt, price))
            if len(selected) >= top_n:
                break
        # Keep only max_per_year lowest for display (first 2), rest as extra
        result[yr] = [[MONTHS[dt.month], round(price, 2)] for dt, price in selected]
    return result

# ── HTML Builder ────────────────────────────────────────────────────────────────

def build_html(all_data, lows_data, current_prices):
    last_date = max(
        rows[-1][0] if rows else "2022-01-01"
        for rows in all_data.values()
    )

    # Format lows as JS object
    def fmt_lows(etf_lows):
        lines = []
        for yr, entries in sorted(etf_lows.items()):
            entries_js = json.dumps(entries, separators=(",", ":"))
            lines.append(f"    {yr}: {entries_js},")
        return "\n".join(lines)

    lows_js_parts = []
    for etf in ETFS:
        inner = fmt_lows(lows_data[etf])
        lows_js_parts.append(f"  {etf}: {{\n{inner}\n  }},")
    lows_js = "{\n" + "\n".join(lows_js_parts) + "\n}"

    cp_js = json.dumps(current_prices, indent=2)
    all_data_js = json.dumps(
        {etf: all_data[etf] for etf in ETFS},
        separators=(",", ":")
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETF — Top 5 Annual Lows</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0c10;
    --surface: #111318;
    --border: #1e2330;
    --accent: #e63946;
    --accent2: #f4a261;
    --text: #e8eaf0;
    --muted: #4a5068;
    --green: #2ec4b6;
    --mono: 'IBM Plex Mono', monospace;
    --title: 'Syne', sans-serif;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    padding: 40px 24px 60px;
  }}

  header {{
    margin-bottom: 40px;
    border-left: 3px solid var(--accent);
    padding-left: 16px;
  }}

  header h1 {{
    font-family: var(--title);
    font-size: clamp(1.6rem, 4vw, 2.4rem);
    font-weight: 800;
    letter-spacing: -0.5px;
    color: var(--text);
  }}

  header p {{
    color: var(--muted);
    font-size: 0.78rem;
    margin-top: 6px;
    letter-spacing: 0.08em;
  }}

  .legend {{
    display: flex;
    gap: 20px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    color: var(--muted);
  }}

  .legend-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }}

  .etf-block {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 20px 24px;
    margin-bottom: 20px;
    opacity: 0;
    animation: fadeIn 0.4s ease forwards;
  }}

  @keyframes fadeIn {{
    to {{ opacity: 1; }}
  }}

  .etf-header {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}

  .etf-name {{
    font-family: var(--title);
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: -0.3px;
  }}

  .current-price {{
    font-size: 0.85rem;
    color: var(--green);
    font-weight: 600;
  }}

  .etf-tag {{
    font-size: 0.68rem;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }}

  th {{
    text-align: left;
    padding: 6px 10px;
    color: var(--muted);
    font-weight: 400;
    border-bottom: 1px solid var(--border);
    letter-spacing: 0.06em;
    font-size: 0.7rem;
  }}

  td {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(30,35,48,0.5);
    vertical-align: top;
  }}

  .year-col {{
    color: var(--muted);
    font-size: 0.72rem;
    width: 52px;
    padding-top: 10px;
  }}

  .rank-cell {{ white-space: nowrap; }}

  .price-tag {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 8px;
    margin: 2px 4px 2px 0;
    font-size: 0.75rem;
  }}

  .price-tag.rank1 {{ border-color: #e63946; color: #e63946; }}
  .price-tag.rank2 {{ border-color: #f4a261; color: #f4a261; }}

  .month {{ color: var(--muted); font-size: 0.68rem; margin-right: 2px; }}
  .ret {{ color: var(--green); font-size: 0.7rem; }}
  .empty {{ color: var(--border); }}
</style>
</head>
<body>

<header>
  <h1>ETF Leveraged — Historical Lows</h1>
  <p>UPDATED: {last_date} &nbsp;·&nbsp; TOP 5 ANNUAL LOWS SINCE {START_YEAR} &nbsp;·&nbsp; MIN GAP {GAP_DAYS} DÍAS</p>
</header>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#e63946"></div> Low #1 of year</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f4a261"></div> Low #2 of year</div>
  <div class="legend-item"><div class="legend-dot" style="background:#2ec4b6"></div> Lows #3–5</div>
</div>

<div id="tables"></div>

<script>
const currentPrices = {cp_js};

const data = {lows_js};

const rankClass = (i) => i === 0 ? 'rank1' : i === 1 ? 'rank2' : '';
const fmt = (n) => '$' + n.toFixed(2);

const container = document.getElementById('tables');
let delay = 0;

for (const [etf, years] of Object.entries(data)) {{
  const block = document.createElement('div');
  block.className = 'etf-block';
  block.style.animationDelay = delay + 'ms';
  delay += 60;

  const yearKeys = Object.keys(years).sort();
  const maxRanks = 5;
  const cp = currentPrices[etf];

  let html = `<div class="etf-header">
    <span class="etf-name" style="color:${{etfColor(etf)}}">${{etf}}</span>
    <span class="current-price">$${{cp.toFixed(2)}}</span>
    <span class="etf-tag">Top 5 annual lows · {START_YEAR}–{datetime.now().year}</span>
  </div>`;

  html += '<table><thead><tr><th>Year</th>';
  for (let i = 1; i <= maxRanks; i++) html += `<th>#${{i}}</th>`;
  html += '</tr></thead><tbody>';

  for (const yr of yearKeys) {{
    const entries = years[yr];
    html += `<tr><td class="year-col">${{yr}}</td>`;
    for (let i = 0; i < maxRanks; i++) {{
      html += `<td class="rank-cell">`;
      if (entries[i]) {{
        const [month, price] = entries[i];
        const ret = ((cp - price) / price * 100).toFixed(0);
        html += `<span class="price-tag ${{rankClass(i)}}"><span class="month">${{month}}</span>${{fmt(price)}}<span class="ret">+${{ret}}%</span></span>`;
      }} else {{
        html += `<span class="empty">—</span>`;
      }}
      html += `</td>`;
    }}
    html += `</tr>`;
  }}

  html += `</tbody></table>`;
  block.innerHTML = html;
  container.appendChild(block);
}}

function etfColor(e) {{
  return {{UPRO:'#378ADD',TQQQ:'#2ec4b6',TECL:'#f4a261',SOXL:'#e63946'}}[e] || '#e8eaf0';
}}
</script>

<!-- CHART SECTION -->
<div style="margin-top:48px; border-top: 1px solid #1e2330; padding-top: 36px;">
  <div style="border-left: 3px solid #f4a261; padding-left: 16px; margin-bottom: 24px;">
    <div style="font-family:'Syne',sans-serif; font-size:1.3rem; font-weight:800; color:#e8eaf0;">Price Chart</div>
    <div style="font-size:0.75rem; color:#4a5068; margin-top:4px; text-transform:uppercase; letter-spacing:0.08em;">Select ETFs & period</div>
  </div>
  <div style="display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:20px;">
    <div id="etf-toggles" style="display:flex;flex-wrap:wrap;gap:10px;"></div>
    <button id="mode-btn" onclick="toggleMode()" style="background:#111318;border:1px solid #4a5068;color:#4a5068;padding:5px 14px;border-radius:3px;cursor:pointer;font-size:0.78rem;font-family:inherit;margin-left:8px;">% change</button>
  </div>
  <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px;" id="period-buttons"></div>
  <div style="font-size:0.72rem; color:#4a5068; margin-bottom:12px;">
    Custom range:
    <input type="date" id="date-from" style="background:#111318;border:1px solid #1e2330;color:#e8eaf0;padding:3px 6px;font-size:0.72rem;border-radius:3px;color-scheme:dark;">
    →
    <input type="date" id="date-to" style="background:#111318;border:1px solid #1e2330;color:#e8eaf0;padding:3px 6px;font-size:0.72rem;border-radius:3px;color-scheme:dark;">
    <button onclick="applyCustom()" style="background:#1e2330;border:1px solid #4a5068;color:#e8eaf0;padding:3px 10px;font-size:0.72rem;border-radius:3px;cursor:pointer;margin-left:4px;">Apply</button>
  </div>
  <div style="position:relative;width:100%;height:360px;">
    <canvas id="priceChart"></canvas>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const allData = {all_data_js};

const etfColors = {{UPRO:'#378ADD', TQQQ:'#2ec4b6', TECL:'#f4a261', SOXL:'#e63946'}};
const etfList = ['UPRO','TQQQ','TECL','SOXL'];
let activeEtfs = new Set(['TQQQ','SOXL']);
let chartFrom = '2025-02-01';
let chartTo = '{last_date}';
let chartInstance = null;
let activeBtn = null;
let viewMode = 'price';

const periods = [
  {{label:'1D', days:1}},{{label:'2D', days:2}},{{label:'3D', days:3}},{{label:'4D', days:4}},
  {{label:'1W', days:7}},{{label:'2W', days:14}},{{label:'1M', months:1}},
  {{label:'3M', months:3}},{{label:'6M', months:6}},{{label:'YTD', ytd:true}},
  {{label:'1Y', months:12}},{{label:'2Y', months:24}},{{label:'All', all:true}}
];

function getDateRange(p) {{
  const last = '{last_date}';
  const to = new Date(last);
  if (p.all) return ['{str(START_YEAR)}-01-01', last];
  if (p.ytd) {{
    const yr = new Date(last).getFullYear();
    return [yr + '-01-01', last];
  }}
  const from = new Date(to);
  if (p.days) {{
    from.setDate(from.getDate() - p.days);
  }} else {{
    from.setMonth(from.getMonth() - p.months);
  }}
  return [from.toISOString().slice(0,10), last];
}}

function toggleMode() {{
  viewMode = viewMode === 'price' ? 'pct' : 'price';
  const btn = document.getElementById('mode-btn');
  btn.textContent = viewMode === 'pct' ? '$ price' : '% change';
  btn.style.color = viewMode === 'pct' ? '#e8eaf0' : '#4a5068';
  btn.style.borderColor = viewMode === 'pct' ? '#e8eaf0' : '#4a5068';
  buildChart();
}}

function buildChart() {{
  const refEtf = etfList.find(e => activeEtfs.has(e)) || 'UPRO';
  const labels = (allData[refEtf] || allData['UPRO'])
    .filter(([d]) => d >= chartFrom && d <= chartTo)
    .map(([d]) => d);

  const datasets = etfList.filter(e => activeEtfs.has(e)).map(e => {{
    const dateMap = {{}};
    allData[e].forEach(([d,p]) => {{ dateMap[d] = p; }});
    const raw = labels.map(d => dateMap[d] ?? null);
    let data = raw;
    if (viewMode === 'pct') {{
      const base = raw.find(v => v != null);
      data = raw.map(v => v == null ? null : +((v / base - 1) * 100).toFixed(2));
    }}
    return {{
      label: e, data,
      borderColor: etfColors[e], borderWidth: 1.8,
      pointRadius: 0, pointHoverRadius: 4,
      tension: 0.1, fill: false, spanGaps: true,
    }};
  }});

  const crosshairPlugin = {{
    id: 'crosshair',
    afterDraw(chart) {{
      if (chart._crosshairX == null) return;
      const {{ ctx, chartArea: {{ top, bottom, left, right }}, scales }} = chart;
      const x = chart._crosshairX, y = chart._crosshairY;
      ctx.save();
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom);
      ctx.strokeStyle = 'rgba(200,200,200,0.35)'; ctx.lineWidth = 1;
      ctx.setLineDash([4,3]); ctx.stroke();
      if (y != null) {{
        ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
        const yVal = scales.y.getValueForPixel(y);
        const labelText = viewMode === 'pct' ? yVal.toFixed(2)+'%' : '$'+yVal.toFixed(2);
        const lw = ctx.measureText(labelText).width + 10, lh = 16;
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(30,35,48,0.92)';
        ctx.strokeStyle = 'rgba(200,200,200,0.35)'; ctx.lineWidth = 1;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(left - lw - 2, y - lh/2, lw, lh, 3);
        else ctx.rect(left - lw - 2, y - lh/2, lw, lh);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#e8eaf0';
        ctx.font = '11px IBM Plex Mono, monospace';
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        ctx.fillText(labelText, left - 5, y);
      }}
      ctx.restore();
    }}
  }};

  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(document.getElementById('priceChart'), {{
    type: 'line',
    data: {{ labels, datasets }},
    plugins: [crosshairPlugin],
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: ctx => viewMode === 'pct'
          ? ` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(2)}}%`
          : ` ${{ctx.dataset.label}}: $${{ctx.parsed.y.toFixed(2)}}` }} }}
      }},
      scales: {{
        x: {{
          ticks: {{ autoSkip: false, maxRotation: 0, color:'#888', font:{{size:11}},
            callback(val, idx) {{
              const d = labels[idx];
              if (!d) return '';
              const [yr, mo] = d.split('-');
              const quarter = Math.ceil(parseInt(mo) / 3);
              const firstIdx = labels.findIndex(l => {{
                const [ly, lm] = l.split('-');
                return ly === yr && Math.ceil(parseInt(lm)/3) === quarter;
              }});
              return idx === firstIdx ? yr + '-' + mo : '';
            }}
          }},
          grid: {{ color:'rgba(128,128,128,0.08)' }}
        }},
        y: {{
          ticks: {{ color:'#888', font:{{size:11}},
            callback: v => viewMode === 'pct' ? v+'%' : '$'+v }},
          grid: {{ color:'rgba(128,128,128,0.08)' }}
        }}
      }},
      onHover(evt, _, chart) {{
        const rect = chart.canvas.getBoundingClientRect();
        const ca = chart.chartArea;
        const mx = evt.native ? evt.native.clientX - rect.left : null;
        const my = evt.native ? evt.native.clientY - rect.top : null;
        if (mx != null && mx >= ca.left && mx <= ca.right && my >= ca.top && my <= ca.bottom) {{
          chart._crosshairX = mx; chart._crosshairY = my;
        }} else {{
          chart._crosshairX = null; chart._crosshairY = null;
        }}
        chart.draw();
      }}
    }}
  }});

  chartInstance.canvas.addEventListener('mouseleave', () => {{
    chartInstance._crosshairX = null; chartInstance._crosshairY = null;
    chartInstance.draw();
  }});
}}

function applyCustom() {{
  const f = document.getElementById('date-from').value;
  const t = document.getElementById('date-to').value;
  if (f && t) {{
    chartFrom = f; chartTo = t;
    if (activeBtn) {{ activeBtn.style.color='#4a5068'; activeBtn.style.borderColor='#1e2330'; activeBtn=null; }}
    buildChart();
  }}
}}

// ETF toggle buttons
const toggleDiv = document.getElementById('etf-toggles');
etfList.forEach(e => {{
  const btn = document.createElement('button');
  btn.textContent = e;
  const on = () => `background:${{etfColors[e]}}22;border:1px solid ${{etfColors[e]}};color:${{etfColors[e]}};`;
  const off = () => `background:#111318;border:1px solid ${{etfColors[e]}}66;color:${{etfColors[e]}}88;`;
  btn.style.cssText = (activeEtfs.has(e) ? on() : off()) + 'padding:5px 14px;border-radius:3px;cursor:pointer;font-size:0.78rem;font-family:inherit;';
  btn.onclick = () => {{
    if (activeEtfs.has(e)) {{ if (activeEtfs.size > 1) activeEtfs.delete(e); else return; }}
    else activeEtfs.add(e);
    btn.style.cssText = (activeEtfs.has(e) ? on() : off()) + 'padding:5px 14px;border-radius:3px;cursor:pointer;font-size:0.78rem;font-family:inherit;';
    buildChart();
  }};
  toggleDiv.appendChild(btn);
}});

// Period buttons
const periodDiv = document.getElementById('period-buttons');
periods.forEach(p => {{
  const btn = document.createElement('button');
  btn.textContent = p.label;
  btn.style.cssText = 'background:#111318;border:1px solid #1e2330;color:#4a5068;padding:4px 12px;border-radius:3px;cursor:pointer;font-size:0.75rem;font-family:inherit;';
  btn.onclick = () => {{
    [chartFrom, chartTo] = getDateRange(p);
    document.getElementById('date-from').value = chartFrom;
    document.getElementById('date-to').value = chartTo;
    if (activeBtn) {{ activeBtn.style.color='#4a5068'; activeBtn.style.borderColor='#1e2330'; }}
    btn.style.color='#e8eaf0'; btn.style.borderColor='#4a5068';
    activeBtn = btn;
    buildChart();
  }};
  periodDiv.appendChild(btn);
}});

document.getElementById('date-from').value = chartFrom;
document.getElementById('date-to').value = chartTo;
buildChart();
</script>
</body>
</html>
"""
    return html


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  ETF Dashboard Generator")
    print("=" * 50)
    print(f"  Fetching data from Yahoo Finance...\n")

    all_data = {}
    lows_data = {}
    current_prices = {}

    for etf in ETFS:
        try:
            rows = fetch_data(etf)
            all_data[etf] = rows
            current_prices[etf] = rows[-1][1]
            lows_data[etf] = compute_lows(rows)
            print(f"OK — {len(rows)} rows, last price: ${current_prices[etf]:.2f} ({rows[-1][0]})")
        except Exception as e:
            print(f"\n  ERROR fetching {etf}: {e}")
            raise

    print(f"\n  Generating HTML...")
    html = build_html(all_data, lows_data, current_prices)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"  ✓ Saved: {OUTPUT_FILE} ({size_kb:.0f} KB)")
    print(f"\n  Open the file in your browser to view the dashboard.")
    print("=" * 50)


if __name__ == "__main__":
    main()
