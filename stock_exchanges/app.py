import os
import json
import concurrent.futures
from datetime import datetime

import yfinance as yf
from flask import Flask, Response

app = Flask(__name__)

# ── Markets ───────────────────────────────────────────────────────────────────

YAHOO_MARKETS = [
    # US indices & volatility
    {"name": "S&P 500",            "ticker": "^GSPC",    "region": "US",     "flag": "us"},
    {"name": "NASDAQ",             "ticker": "^IXIC",    "region": "US",     "flag": "us"},
    {"name": "Dow Jones",          "ticker": "^DJI",     "region": "US",     "flag": "us"},
    {"name": "VIX",                "ticker": "^VIX",     "region": "US",     "flag": "us"},
    # LATAM
    {"name": "Chile (IPSA)",       "ticker": "^IPSA",    "region": "LATAM",  "flag": "cl"},
    {"name": "Brasil (IBOVESPA)",  "ticker": "^BVSP",    "region": "LATAM",  "flag": "br"},
    {"name": "Argentina (MERVAL)", "ticker": "^MERV",    "region": "LATAM",  "flag": "ar"},
    # Metals
    {"name": "Oro",                "ticker": "GC=F",     "region": "METALS", "icon": "🥇"},
    {"name": "Plata",              "ticker": "SI=F",     "region": "METALS", "icon": "🥈"},
    {"name": "Cobre",              "ticker": "HG=F",     "region": "METALS", "icon": "🟤", "dec": 4},
    # Forex (1 USD = X) — flags: [base, quote]
    {"name": "USD / CLP",          "ticker": "USDCLP=X", "region": "FOREX",  "flags": ["us", "cl"]},
    {"name": "USD / EUR",          "ticker": "USDEUR=X", "region": "FOREX",  "flags": ["us", "eu"], "dec": 4},
    {"name": "USD / JPY",          "ticker": "USDJPY=X", "region": "FOREX",  "flags": ["us", "jp"]},
    {"name": "USD / GBP",          "ticker": "USDGBP=X", "region": "FOREX",  "flags": ["us", "gb"], "dec": 4},
    {"name": "USD / BRL",          "ticker": "USDBRL=X", "region": "FOREX",  "flags": ["us", "br"], "dec": 4},
    {"name": "USD / ARS",          "ticker": "USDARS=X", "region": "FOREX",  "flags": ["us", "ar"]},
]


def _fetch_yahoo_one(market):
    name, ticker = market["name"], market["ticker"]
    d = market.get("dec", 2)
    try:
        fi      = yf.Ticker(ticker).fast_info
        current = fi.last_price
        prev    = fi.previous_close
        if current is None:
            return name, {
                "value": None, "prev": None, "change": None, "pct": None,
                "error": "Sin datos", "region": market["region"],
                "flag": market.get("flag"), "flags": market.get("flags"),
                "icon": market.get("icon"), "dec": d,
            }
        change = (current - prev) if prev else None
        pct    = ((change / prev) * 100) if prev else None
        return name, {
            "value":  round(current, d),
            "prev":   round(prev, d) if prev else None,
            "change": round(change, d) if change is not None else None,
            "pct":    round(pct, 2)   if pct    is not None else None,
            "error":  None,
            "region": market["region"],
            "flag":   market.get("flag"),
            "flags":  market.get("flags"),
            "icon":   market.get("icon"),
            "dec":    d,
        }
    except Exception:
        return name, {
            "value": None, "prev": None, "change": None, "pct": None,
            "error": "Error al obtener datos", "region": market["region"],
            "flag": market.get("flag"), "flags": market.get("flags"),
            "icon": market.get("icon"), "dec": d,
        }


def fetch_yahoo():
    order = [m["name"] for m in YAHOO_MARKETS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        raw = dict(ex.map(_fetch_yahoo_one, YAHOO_MARKETS))

    markets = [{"name": n, **raw[n]} for n in order]

    # Compute GSR (Gold-Silver Ratio) from fetched metal prices
    gold, silver = raw.get("Oro", {}), raw.get("Plata", {})
    gv, sv = gold.get("value"), silver.get("value")
    gp, sp = gold.get("prev"),  silver.get("prev")
    if gv and sv:
        gsr_val    = gv / sv
        gsr_prev   = (gp / sp) if gp and sp else None
        gsr_change = (gsr_val - gsr_prev)          if gsr_prev else None
        gsr_pct    = (gsr_change / gsr_prev * 100) if gsr_change is not None else None
        gsr_entry  = {
            "name":   "Ratio Oro/Plata (GSR)",
            "icon":   "📊",
            "value":  round(gsr_val, 2),
            "change": round(gsr_change, 2) if gsr_change is not None else None,
            "pct":    round(gsr_pct, 2)    if gsr_pct    is not None else None,
            "error":  None,
            "region": "METALS",
            "dec":    2,
        }
        plata_idx = next((i for i, m in enumerate(markets) if m["name"] == "Plata"), None)
        if plata_idx is not None:
            markets.insert(plata_idx + 1, gsr_entry)

    return {
        "markets": markets,
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bolsas del Mundo</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; padding: 40px 20px; }
  .container { max-width: 1100px; margin: 0 auto; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 40px; align-items: start; }
  @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; flex-wrap: wrap; gap: 12px; }
  h1 { font-size: 1.5rem; font-weight: 700; color: #fff; letter-spacing: -.01em; }
  .meta { font-size: 0.78rem; color: #555; display: flex; align-items: center; gap: 12px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #4ade80; flex-shrink: 0; }
  .dot.loading { background: #f59e0b; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
  .refresh-btn { background: none; border: 1px solid #2a2d3a; border-radius: 6px; color: #666; font-size: 0.78rem; padding: 5px 12px; cursor: pointer; transition: border-color .2s, color .2s; }
  .refresh-btn:hover { border-color: #4f8ef7; color: #4f8ef7; }
  .section { margin-bottom: 32px; }
  .section-title { font-size: 0.7rem; text-transform: uppercase; letter-spacing: .12em; color: #444; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #1a1d27; }
  table { width: 100%; border-collapse: collapse; }
  thead th { font-size: 0.7rem; color: #444; text-transform: uppercase; letter-spacing: .07em; padding: 0 6px 10px; text-align: left; }
  thead th:not(:first-child) { text-align: right; }
  tbody tr:hover td { background: #13151f; }
  tbody td { padding: 11px 6px; border-bottom: 1px solid #13151f; font-size: 0.94rem; transition: background .12s; }
  tbody tr:last-child td { border-bottom: none; }
  tbody td:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
  .market-name { font-weight: 600; color: #ddd; }
  .value { color: #b0b8c8; }
  .pos { color: #4ade80; }
  .neg { color: #f87171; }
  .na { color: #2a2d3a; }
  .unavail { color: #333; font-size: 0.8rem; }
  .empty-msg { padding: 48px 0; text-align: center; color: #333; font-size: 0.88rem; line-height: 1.6; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Bolsas del Mundo</h1>
    <div class="meta">
      <span class="dot loading" id="dot"></span>
      <span id="updated">Cargando…</span>
      <button class="refresh-btn" onclick="reload()">&#8635; Actualizar</button>
    </div>
  </header>

  <div id="content"><div class="empty-msg">Cargando…</div></div>
</div>

<script>
const fmt  = (n, d) => n == null ? '<span class="na">—</span>'
  : n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sign = n => n > 0 ? '+' : '';
const cls  = n => n == null ? '' : n >= 0 ? 'pos' : 'neg';

function renderSection(title, markets) {
  if (!markets.length) return '';
  const rows = markets.map(m => {
    const d = m.dec || 2;
    const valCell = (m.error && m.value == null)
      ? `<span class="unavail">${m.error}</span>`
      : `<span class="value">${fmt(m.value, d)}</span>`;
    const chgCell = m.change == null ? '<span class="na">—</span>'
      : `<span class="${cls(m.change)}">${sign(m.change)}${fmt(m.change, d)}</span>`;
    const pctCell = m.pct == null ? '<span class="na">—</span>'
      : `<span class="${cls(m.pct)}">${sign(m.pct)}${fmt(m.pct, 2)}%</span>`;
    const iconHtml = m.icon ? `<span style="margin-right:7px;font-size:1.05em;vertical-align:middle">${m.icon}</span>` : '';
    const flagList = m.flags || (m.flag ? [m.flag] : []);
    const flagsHtml = flagList.map((f, i) =>
      `<img src="https://flagcdn.com/20x15/${f}.png" width="20" height="15" style="vertical-align:middle;border-radius:2px;${i < flagList.length - 1 ? 'margin-right:3px' : 'margin-right:7px'}">`
    ).join('');
    return `<tr>
      <td class="market-name">${iconHtml}${flagsHtml}${m.name}</td>
      <td>${valCell}</td><td>${chgCell}</td><td>${pctCell}</td>
    </tr>`;
  }).join('');
  return `<div class="section">
    <div class="section-title">${title}</div>
    <table>
      <thead><tr><th>Mercado</th><th>Valor</th><th>Variación</th><th>% Cambio</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function render(data) {
  const us     = data.markets.filter(m => m.region === 'US');
  const latam  = data.markets.filter(m => m.region === 'LATAM');
  const metals = data.markets.filter(m => m.region === 'METALS');
  const forex  = data.markets.filter(m => m.region === 'FOREX');
  document.getElementById('content').innerHTML = `
    <div class="grid">
      <div>
        ${renderSection('Estados Unidos', us)}
        ${renderSection('América Latina', latam)}
      </div>
      <div>
        ${renderSection('Metales', metals)}
        ${renderSection('Divisas (1 USD = X)', forex)}
      </div>
    </div>`;
  document.getElementById('updated').textContent = 'Actualizado: ' + data.updated;
  document.getElementById('dot').className = 'dot';
}

async function load() {
  document.getElementById('dot').className = 'dot loading';
  try {
    const res  = await fetch('/api/yahoo');
    const data = await res.json();
    render(data);
  } catch {
    document.getElementById('updated').textContent = 'Error de conexión';
  }
}

function reload() { load(); }

load();
setInterval(load, 60000);
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")

@app.route("/api/yahoo")
def api_yahoo():
    return Response(json.dumps(fetch_yahoo()), mimetype="application/json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
