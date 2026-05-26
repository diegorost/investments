import os
import json
import concurrent.futures
from datetime import datetime

import yfinance as yf
from flask import Flask, Response

app = Flask(__name__)

MARKETS = [
    {"name": "S&P 500",              "ticker": "^GSPC",     "region": "US"},
    {"name": "NASDAQ",               "ticker": "^IXIC",     "region": "US"},
    {"name": "Dow Jones",            "ticker": "^DJI",      "region": "US"},
    {"name": "México (IPC)",         "ticker": "^MXX",      "region": "LATAM"},
    {"name": "Chile (IPSA)",         "ticker": "^IPSA",     "region": "LATAM"},
    {"name": "Colombia (COLCAP)",    "ticker": "^COLCAP",   "region": "LATAM"},
    {"name": "Brasil (IBOVESPA)",    "ticker": "^BVSP",     "region": "LATAM"},
    {"name": "Argentina (MERVAL)",   "ticker": "^MERV",     "region": "LATAM"},
    {"name": "Perú (S&P BVL)",      "ticker": "^SPBLPGPT", "region": "LATAM"},
]

_NAME_TO_REGION = {m["name"]: m["region"] for m in MARKETS}
_ORDER = [m["name"] for m in MARKETS]


def _fetch_one(market):
    name, ticker = market["name"], market["ticker"]
    if ticker is None:
        return name, {"value": None, "change": None, "pct": None, "error": "Sin bolsa en Yahoo Finance"}
    try:
        closes = yf.Ticker(ticker).history(period="5d")["Close"].dropna()
        if closes.empty:
            return name, {"value": None, "change": None, "pct": None, "error": "Sin datos"}
        current = float(closes.iloc[-1])
        if len(closes) >= 2:
            prev = float(closes.iloc[-2])
            change = current - prev
            pct = (change / prev) * 100
        else:
            change = pct = None
        return name, {
            "value": round(current, 2),
            "change": round(change, 2) if change is not None else None,
            "pct": round(pct, 2) if pct is not None else None,
            "error": None,
        }
    except Exception:
        return name, {"value": None, "change": None, "pct": None, "error": "Error al obtener datos"}


def fetch_all():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        raw = dict(ex.map(_fetch_one, MARKETS))
    return {
        "markets": [
            {"name": n, "region": _NAME_TO_REGION[n], **raw[n]}
            for n in _ORDER
        ],
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bolsas del Mundo</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; padding: 40px 20px; }
  .container { max-width: 780px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 36px; flex-wrap: wrap; gap: 12px; }
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
  tbody tr { border-radius: 6px; }
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
  #loading { text-align: center; padding: 80px 0; color: #333; font-size: 0.9rem; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Bolsas del Mundo</h1>
    <div class="meta">
      <span class="dot loading" id="dot"></span>
      <span id="updated">Cargando…</span>
      <button class="refresh-btn" onclick="load()">&#8635; Actualizar</button>
    </div>
  </header>
  <div id="content"><div id="loading">Obteniendo datos de mercado…</div></div>
</div>
<script>
const fmt = (n, d) => n === null || n === undefined
  ? '<span class="na">—</span>'
  : n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

const sign = n => (n > 0 ? '+' : '');
const cls  = n => n === null ? '' : n >= 0 ? 'pos' : 'neg';

function renderSection(title, markets) {
  if (!markets.length) return '';
  const rows = markets.map(m => {
    const valCell = (m.error && m.value === null)
      ? `<span class="unavail">${m.error}</span>`
      : `<span class="value">${fmt(m.value, 2)}</span>`;
    const chgCell = m.change === null
      ? '<span class="na">—</span>'
      : `<span class="${cls(m.change)}">${sign(m.change)}${fmt(m.change, 2)}</span>`;
    const pctCell = m.pct === null
      ? '<span class="na">—</span>'
      : `<span class="${cls(m.pct)}">${sign(m.pct)}${fmt(m.pct, 2)}%</span>`;
    return `<tr>
      <td class="market-name">${m.name}</td>
      <td>${valCell}</td>
      <td>${chgCell}</td>
      <td>${pctCell}</td>
    </tr>`;
  }).join('');

  return `<div class="section">
    <div class="section-title">${title}</div>
    <table>
      <thead><tr><th>Mercado</th><th>Valor</th><th>Variación</th><th>% Cambio</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function render(data) {
  const us    = data.markets.filter(m => m.region === 'US');
  const latam = data.markets.filter(m => m.region === 'LATAM');
  document.getElementById('content').innerHTML =
    renderSection('Estados Unidos', us) +
    renderSection('América Latina', latam);
  document.getElementById('updated').textContent = 'Actualizado: ' + data.updated;
  document.getElementById('dot').className = 'dot';
}

async function load() {
  document.getElementById('dot').className = 'dot loading';
  try {
    const res  = await fetch('/api/data');
    const data = await res.json();
    render(data);
  } catch {
    document.getElementById('updated').textContent = 'Error de conexión';
    document.getElementById('dot').className = 'dot loading';
  }
}

load();
setInterval(load, 60000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/api/data")
def api_data():
    return Response(json.dumps(fetch_all()), mimetype="application/json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
