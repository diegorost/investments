import os
import json
import concurrent.futures
from datetime import datetime

import yfinance as yf
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, Response

app = Flask(__name__)

# ── Yahoo Finance ─────────────────────────────────────────────────────────────

YAHOO_MARKETS = [
    {"name": "S&P 500",            "ticker": "^GSPC",  "region": "US"},
    {"name": "NASDAQ",             "ticker": "^IXIC",  "region": "US"},
    {"name": "Dow Jones",          "ticker": "^DJI",   "region": "US"},
    {"name": "Canadá (TSX)",       "ticker": "^GSPTSE","region": "US"},
    {"name": "México (IPC)",       "ticker": "^MXX",   "region": "LATAM"},
    {"name": "Chile (IPSA)",       "ticker": "^IPSA",  "region": "LATAM"},
    {"name": "Colombia (COLCAP)",  "ticker": "^COLCAP","region": "LATAM"},
    {"name": "Brasil (IBOVESPA)",  "ticker": "^BVSP",  "region": "LATAM"},
    {"name": "Argentina (MERVAL)", "ticker": "^MERV",  "region": "LATAM"},
]

def _fetch_yahoo_one(market):
    name, ticker = market["name"], market["ticker"]
    try:
        fi      = yf.Ticker(ticker).fast_info
        current = fi.last_price
        prev    = fi.previous_close
        if current is None:
            return name, {"value": None, "change": None, "pct": None,
                          "error": "Sin datos", "region": market["region"]}
        change = (current - prev) if prev else None
        pct    = ((change / prev) * 100) if prev else None
        return name, {
            "value":  round(current, 2),
            "change": round(change, 2) if change is not None else None,
            "pct":    round(pct, 2)    if pct    is not None else None,
            "error":  None,
            "region": market["region"],
        }
    except Exception:
        return name, {"value": None, "change": None, "pct": None,
                      "error": "Error al obtener datos", "region": market["region"]}

def fetch_yahoo():
    order = [m["name"] for m in YAHOO_MARKETS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        raw = dict(ex.map(_fetch_yahoo_one, YAHOO_MARKETS))
    return {
        "markets": [{"name": n, **raw[n]} for n in order],
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── Investing.com ─────────────────────────────────────────────────────────────

INVESTING_URL = "https://es.investing.com/indices/americas-indices"

INVESTING_COUNTRIES = {
    "Argentina", "Brasil", "Canadá", "Estados Unidos",
    "Chile", "México", "Colombia",
    "Brazil", "Canada", "United States", "Mexico",  # English fallbacks
}

def _parse_num(s):
    if not s:
        return None
    s = s.replace(",", "").replace("%", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def fetch_investing():
    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        resp = scraper.get(
            INVESTING_URL,
            headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"},
            timeout=25,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        table = (
            soup.find("table", {"id": "cr1"}) or
            soup.find("table", class_=lambda c: c and "genTbl" in c)
        )
        if not table:
            return {
                "markets": [],
                "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "error": "Tabla no encontrada — posible bloqueo JS de Cloudflare",
            }

        markets      = []
        curr_country = None
        curr_region  = "OTHER"

        for row in table.find_all("tr"):
            cls = row.get("class", [])
            # Country header rows typically have a specific class or a single spanning cell
            if "theTitle" in cls or "region" in cls:
                curr_country = row.get_text(strip=True)
                curr_region  = "US" if curr_country in {
                    "Estados Unidos", "Canadá", "United States", "Canada"
                } else "LATAM"
                continue

            cells = row.find_all("td")
            if len(cells) < 6 or curr_country not in INVESTING_COUNTRIES:
                continue

            name = cells[0].get_text(strip=True)
            val  = _parse_num(cells[1].get_text(strip=True))
            chg  = _parse_num(cells[4].get_text(strip=True))
            pct  = _parse_num(cells[5].get_text(strip=True))

            if not name:
                continue

            markets.append({
                "name":    name,
                "country": curr_country,
                "region":  curr_region,
                "value":   val,
                "change":  chg,
                "pct":     pct,
                "error":   None,
            })

        if not markets:
            return {
                "markets": [],
                "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "error": "Sin datos — la página probablemente requiere JS para renderizar",
            }

        return {
            "markets": markets,
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

    except Exception as e:
        return {
            "markets": [],
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "error": str(e),
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
  .container { max-width: 820px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; flex-wrap: wrap; gap: 12px; }
  h1 { font-size: 1.5rem; font-weight: 700; color: #fff; letter-spacing: -.01em; }
  .meta { font-size: 0.78rem; color: #555; display: flex; align-items: center; gap: 12px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #4ade80; flex-shrink: 0; }
  .dot.loading { background: #f59e0b; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
  .refresh-btn { background: none; border: 1px solid #2a2d3a; border-radius: 6px; color: #666; font-size: 0.78rem; padding: 5px 12px; cursor: pointer; transition: border-color .2s, color .2s; }
  .refresh-btn:hover { border-color: #4f8ef7; color: #4f8ef7; }
  /* Tabs */
  .tabs { display: flex; gap: 4px; margin-bottom: 28px; border-bottom: 1px solid #1a1d27; }
  .tab-btn { background: none; border: none; border-bottom: 2px solid transparent; color: #555; font-size: 0.88rem; font-weight: 600; padding: 8px 18px 10px; cursor: pointer; transition: color .2s, border-color .2s; margin-bottom: -1px; }
  .tab-btn:hover { color: #aaa; }
  .tab-btn.active { color: #fff; border-bottom-color: #4f8ef7; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  /* Table */
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
  .country-tag { font-size: 0.72rem; color: #444; margin-left: 6px; font-weight: 400; }
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

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('yahoo')">Yahoo Finance</button>
    <button class="tab-btn"        onclick="switchTab('investing')">Investing.com</button>
  </div>

  <div id="tab-yahoo"     class="tab-panel active"><div class="empty-msg">Cargando…</div></div>
  <div id="tab-investing" class="tab-panel">        <div class="empty-msg">Haz clic en Actualizar para cargar.</div></div>
</div>

<script>
let activeTab   = 'yahoo';
let cache       = { yahoo: null, investing: null };
let loadedOnce  = { yahoo: false, investing: false };

const fmt  = (n, d) => n == null ? '<span class="na">—</span>'
  : n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sign = n => n > 0 ? '+' : '';
const cls  = n => n == null ? '' : n >= 0 ? 'pos' : 'neg';

function renderSection(title, markets, showCountry = false) {
  if (!markets.length) return '';
  const rows = markets.map(m => {
    const nameCell = showCountry && m.country
      ? `${m.name}<span class="country-tag">${m.country}</span>`
      : m.name;
    const valCell = (m.error && m.value == null)
      ? `<span class="unavail">${m.error}</span>`
      : `<span class="value">${fmt(m.value, 2)}</span>`;
    const chgCell = m.change == null ? '<span class="na">—</span>'
      : `<span class="${cls(m.change)}">${sign(m.change)}${fmt(m.change, 2)}</span>`;
    const pctCell = m.pct == null ? '<span class="na">—</span>'
      : `<span class="${cls(m.pct)}">${sign(m.pct)}${fmt(m.pct, 2)}%</span>`;
    return `<tr>
      <td class="market-name">${nameCell}</td>
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

function renderYahoo(data) {
  const us    = data.markets.filter(m => m.region === 'US');
  const latam = data.markets.filter(m => m.region === 'LATAM');
  document.getElementById('tab-yahoo').innerHTML =
    renderSection('Estados Unidos / Canadá', us) +
    renderSection('América Latina', latam);
}

function renderInvesting(data) {
  const el = document.getElementById('tab-investing');
  if (data.error && !data.markets.length) {
    el.innerHTML = `<div class="empty-msg">⚠️ ${data.error}</div>`;
    return;
  }
  const us    = data.markets.filter(m => m.region === 'US');
  const latam = data.markets.filter(m => m.region === 'LATAM');
  const other = data.markets.filter(m => m.region === 'OTHER');
  el.innerHTML =
    renderSection('Estados Unidos / Canadá', us,    true) +
    renderSection('América Latina',           latam, true) +
    (other.length ? renderSection('Otros', other, true) : '');
}

function setMeta(updated) {
  document.getElementById('updated').textContent = 'Actualizado: ' + updated;
  document.getElementById('dot').className = 'dot';
}

function setLoading() {
  document.getElementById('dot').className = 'dot loading';
}

async function loadTab(tab) {
  setLoading();
  try {
    const res  = await fetch('/api/' + tab);
    const data = await res.json();
    cache[tab] = data;
    loadedOnce[tab] = true;
    if (tab === 'yahoo')     renderYahoo(data);
    if (tab === 'investing') renderInvesting(data);
    setMeta(data.updated);
  } catch {
    document.getElementById('updated').textContent = 'Error de conexión';
    document.getElementById('dot').className = 'dot loading';
  }
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach((b, i) =>
    b.classList.toggle('active', ['yahoo','investing'][i] === tab));
  document.querySelectorAll('.tab-panel').forEach(p =>
    p.classList.toggle('active', p.id === 'tab-' + tab));
  if (cache[tab]) {
    setMeta(cache[tab].updated);
  } else {
    loadTab(tab);
  }
}

function reload() { loadTab(activeTab); }

// Initial load + auto-refresh
loadTab('yahoo');
setInterval(() => loadTab(activeTab), 60000);
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

@app.route("/api/investing")
def api_investing():
    return Response(json.dumps(fetch_investing()), mimetype="application/json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
