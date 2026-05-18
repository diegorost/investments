import re
import json
import webbrowser
from pathlib import Path

import openpyxl
import xlrd

GGCC_PATH = r"C:\Users\diego\OneDrive\Gastos Comunes"

MONTH_ABBR = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEPT": 9, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

CATEGORIES = ["ADMINISTRACIÓN", "MANTENCIÓN", "USO CONSUMO", "REPARACIÓN", "EQUIPAMIENTO"]
VALUE_COL = 8


def parse_filename(name: str) -> tuple[int, int] | None:
    stem = Path(name).stem.upper()
    m = re.search(r"GC\s+D\d+\s+([A-Z]+)(\d{2})$", stem)
    if not m:
        return None
    month = MONTH_ABBR.get(m.group(1))
    if month is None:
        return None
    return 2000 + int(m.group(2)), month


def read_rows(path: Path) -> list[list]:
    if path.suffix.lower() == ".xls":
        wb = xlrd.open_workbook(str(path))
        ws = wb.sheet_by_index(0)
        return [[ws.cell_value(i, j) for j in range(ws.ncols)] for i in range(ws.nrows)]
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb.active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def get_cell(row: list, col: int):
    return row[col] if col < len(row) else None


def extract_ggcc(path: Path) -> dict | None:
    try:
        rows = read_rows(path)
    except Exception as e:
        print(f"  Error {path.name}: {e}")
        return None

    cat_row_idx: dict[str, int] = {}
    total_row_idx = None
    gasto_comun_val = None
    tap_val = None
    deductions = 0.0  # saldo anterior + morosidad to subtract from TAP

    for i, row in enumerate(rows):
        cell0 = str(get_cell(row, 0) or "").upper()
        txt = " ".join(str(v or "") for v in row).upper()

        for cat in CATEGORIES:
            if cat in cell0 and cat not in cat_row_idx:
                cat_row_idx[cat] = i

        if "TOTAL GASTOS COMUNES" in cell0:
            total_row_idx = i

        # GASTO COMÚN personal (base, without carry-forwards)
        if (re.search(r"GASTO\s+COM", txt)
                and "GASTOS DE" not in txt
                and "TOTAL" not in txt
                and "EDIFICIO" not in txt
                and "SUB" not in txt
                and gasto_comun_val is None):
            val = get_cell(row, VALUE_COL)
            if isinstance(val, (int, float)) and val > 0:
                gasto_comun_val = float(val)

        # TOTAL A PAGAR: first occurrence
        if "TOTAL A PAGAR" in txt and tap_val is None:
            val = get_cell(row, VALUE_COL)
            if isinstance(val, (int, float)) and val > 0:
                tap_val = float(val)

        # Amounts to subtract: saldo anterior or morosidad al X de Y
        if re.search(r"SALDO\s+ANTERIOR", txt) or re.search(r"MOROSIDAD\s+AL\s+\d", txt):
            val = get_cell(row, VALUE_COL)
            if isinstance(val, (int, float)) and val > 0:
                deductions += float(val)

    def next_subtotal(start: int) -> float | None:
        for row in rows[start:]:
            t = " ".join(str(v or "") for v in row).upper()
            if "SUB-TOTAL" in t or "SUBTOTAL" in t:
                val = get_cell(row, VALUE_COL)
                if isinstance(val, (int, float)) and val >= 0:
                    return float(val)
        return None

    result: dict[str, float | None] = {}
    for cat, idx in cat_row_idx.items():
        result[cat] = next_subtotal(idx + 1)

    if total_row_idx is not None:
        val = get_cell(rows[total_row_idx], VALUE_COL)
        result["TOTAL"] = float(val) if isinstance(val, (int, float)) else None
    else:
        result["TOTAL"] = None

    result["PERSONAL"] = gasto_comun_val
    result["TAP"] = (tap_val - deductions) if tap_val is not None else None
    return result


def scan_all() -> list[dict]:
    root = Path(GGCC_PATH)
    records = []
    files = sorted(root.rglob("GC D602 *.xls*"))
    print(f"Encontrados {len(files)} archivos Excel...")
    for f in files:
        parsed = parse_filename(f.name)
        if parsed is None:
            continue
        year, month = parsed
        data = extract_ggcc(f)
        if data is None:
            continue
        records.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "filename": f.name,
            **data,
        })
    records.sort(key=lambda r: (r["year"], r["month"]))
    print(f"Procesados {len(records)} meses.")
    return records


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es" data-theme="terminal">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gastos Comunes D602</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
<style>
:root {
  --bg: #f5f5f7; --surface: #ffffff; --text: #1d1d1f;
  --muted: #6e6e73; --grid: #f0f0f5; --border: #e0e0e5;
  --tip: rgba(255,255,255,0.97); --tip-text: #1d1d1f;
  --btn: #e8e8ed; --btn-text: #1d1d1f; --btn-active: #1d1d1f; --btn-active-text: #fff;
  --font-body: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
  --font-mono: -apple-system, sans-serif;
}
[data-theme="dark"] {
  --bg: #000; --surface: #1c1c1e; --text: #f5f5f7;
  --muted: #98989d; --grid: #2c2c2e; --border: #3a3a3c;
  --tip: rgba(28,28,30,0.98); --tip-text: #f5f5f7;
  --btn: #2c2c2e; --btn-text: #f5f5f7; --btn-active: #f5f5f7; --btn-active-text: #000;
  --font-body: -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: -apple-system, sans-serif;
}
[data-theme="terminal"] {
  --bg: #09090f; --surface: #111118; --text: #e8e8f0;
  --muted: #6b6b88; --grid: #1e1e2e; --border: #1e1e2e;
  --tip: rgba(17,17,24,0.98); --tip-text: #e8e8f0;
  --btn: #1e1e2e; --btn-text: #6b6b88; --btn-active: #f0c040; --btn-active-text: #09090f;
  --font-body: 'Syne', sans-serif;
  --font-mono: 'Space Mono', monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: var(--font-body);
  background: var(--bg); color: var(--text);
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; padding: 48px 24px 64px;
  transition: background .25s, color .25s, font-family .1s;
}
header { text-align: center; margin-bottom: 36px; width: 100%; max-width: 1140px; position: relative; }
header h1 { font-size: 32px; font-weight: 700; letter-spacing: -0.5px; }
[data-theme="terminal"] header h1 { color: #f0c040; letter-spacing: 1px; font-size: 28px; text-transform: uppercase; }
header p  { font-size: 15px; color: var(--muted); margin-top: 6px; }
[data-theme="terminal"] header p  { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; }
[data-theme="terminal"] .card .label { font-family: 'Space Mono', monospace; font-size: 10px; letter-spacing: 2px; }
[data-theme="terminal"] .card .value { font-family: 'Syne', sans-serif; font-weight: 800; }
[data-theme="terminal"] .card.blue .value { color: #f0c040; }
[data-theme="terminal"] .card.green .value { color: #4ade80; }
[data-theme="terminal"] .card.red .value { color: #f87171; }
[data-theme="terminal"] .chart-title { font-family: 'Space Mono', monospace; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; color: #f0c040; }
[data-theme="terminal"] .chart-sub { font-family: 'Space Mono', monospace; font-size: 10px; letter-spacing: 1px; }
[data-theme="terminal"] button { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 1px; border-radius: 4px; }
[data-theme="terminal"] .card { border: 1px solid #1e1e2e; border-radius: 8px; }
[data-theme="terminal"] .chart-wrap { border: 1px solid #1e1e2e; border-radius: 8px; }
.header-controls {
  position: absolute; top: 0; right: 0;
  display: flex; gap: 8px; align-items: center;
}
.chart-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 4px;
}
.chart-header-left {}
.btn-group { display: flex; gap: 4px; }
button {
  background: var(--btn); color: var(--btn-text);
  border: none; border-radius: 20px; padding: 7px 16px;
  font-size: 13px; font-weight: 500; cursor: pointer;
  font-family: inherit; transition: background .2s, color .2s;
}
button.active { background: var(--btn-active); color: var(--btn-active-text); }
.cards {
  display: flex; gap: 16px; margin-bottom: 36px; flex-wrap: wrap; justify-content: center;
}
.card {
  background: var(--surface); border-radius: 18px; padding: 20px 28px;
  min-width: 155px; box-shadow: 0 2px 12px rgba(0,0,0,.06);
  transition: background .25s;
}
.card .label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.card .value { font-size: 24px; font-weight: 600; margin-top: 4px; letter-spacing: -0.5px; }
.card.blue  .value { color: #0071e3; }
.card.red   .value { color: #ff3b30; }
.card.green .value { color: #34c759; }
.chart-wrap {
  background: var(--surface); border-radius: 22px; padding: 32px 32px 24px;
  box-shadow: 0 2px 20px rgba(0,0,0,.07); width: 100%; max-width: 1140px;
  transition: background .25s; margin-bottom: 36px;
}
.chart-title { font-size: 17px; font-weight: 600; margin-bottom: 4px; }
.chart-sub   { font-size: 13px; color: var(--muted); margin-bottom: 24px; }
canvas { width: 100% !important; }
</style>
</head>
<body>

<header>
  <h1>Gastos Comunes</h1>
  <p>Departamento D602 &mdash; Evolución mensual</p>
  <div class="header-controls">
    <button id="btn-theme" onclick="cycleTheme()" title="Cambiar tema">☀️</button>
  </div>
</header>

<div class="cards">
  <div class="card blue">
    <div class="label">Último total edificio</div>
    <div class="value" id="c-total">—</div>
  </div>
  <div class="card blue">
    <div class="label">Último total a pagar</div>
    <div class="value" id="c-personal">—</div>
  </div>
  <div class="card red">
    <div class="label">Mayor categoría</div>
    <div class="value" id="c-top-cat">—</div>
  </div>
  <div class="card">
    <div class="label">Mayor categoría $</div>
    <div class="value" id="c-top-val">—</div>
  </div>
  <div class="card green">
    <div class="label">Crecimiento total</div>
    <div class="value" id="c-growth">—</div>
  </div>
  <div class="card">
    <div class="label">Meses registrados</div>
    <div class="value" id="c-count">—</div>
  </div>
</div>

<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-header-left">
      <div class="chart-title">Gastos del Edificio por Categoría</div>
      <div class="chart-sub" id="sub1">Valores en pesos CLP por categoría mensual</div>
    </div>
    <div class="btn-group">
      <button id="btn1-clp" class="active" onclick="setMode1('clp')">CLP</button>
      <button id="btn1-pct" onclick="setMode1('pct')">%</button>
      <button id="btn1-reset" onclick="resetZoom(chart1, 'btn1-reset')" style="display:none">↩</button>
    </div>
  </div>
  <canvas id="chart1" height="340"></canvas>
</div>

<div class="chart-wrap">
  <div class="chart-header">
    <div class="chart-header-left">
      <div class="chart-title">Gasto Común — Depto D602</div>
      <div class="chart-sub" id="sub2">Gasto común proporcional al dominio (sin agua caliente ni carry-forwards)</div>
    </div>
    <div class="btn-group">
      <button id="btn2-clp" class="active" onclick="setMode2('clp')">CLP</button>
      <button id="btn2-pct" onclick="setMode2('pct')">%</button>
      <button id="btn2-reset" onclick="resetZoom(chart2, 'btn2-reset')" style="display:none">↩</button>
    </div>
  </div>
  <canvas id="chart2" height="240"></canvas>
</div>

<script>
const RAW = __DATA__;

// ── helpers ──────────────────────────────────────────────
const fmtCLP = v => {
  if (v == null) return '—';
  if (v >= 1e6) return '$' + (v/1e6).toFixed(2) + 'M';
  return '$' + Math.round(v/1000) + 'K';
};
const fmtPct  = v => v == null ? '—' : v.toFixed(0) + '%';
const fmtPct3 = v => v == null ? '—' : v.toFixed(0) + '%';

let mode1 = 'clp', mode2 = 'clp';

// ── static setup ─────────────────────────────────────────
const CAT_KEYS   = ['ADMINISTRACIÓN','MANTENCIÓN','USO CONSUMO','REPARACIÓN','EQUIPAMIENTO','TOTAL'];
const CAT_LABELS = ['Administración','Mantención','Uso y Consumo','Reparación','Equipamiento','Total Gastos Comunes'];
const COLORS_LIGHT    = ['#0071e3','#34c759','#ff9f0a','#ff3b30','#af52de','#1d1d1f'];
const COLORS_DARK     = ['#0071e3','#34c759','#ff9f0a','#ff3b30','#af52de','#f5f5f7'];
const COLORS_TERMINAL = ['#f0c040','#4ade80','#5ab4e0','#f87171','#c084fc','#e8e8f0'];
const DASHES = [[],[],[],[],[],[6,4]];

function getThemePalette() {
  const t = document.documentElement.getAttribute('data-theme');
  if (t === 'terminal') return COLORS_TERMINAL;
  if (t === 'dark')     return COLORS_DARK;
  return COLORS_LIGHT;
}
function getChart2Color() {
  return document.documentElement.getAttribute('data-theme') === 'terminal'
    ? '#f0c040' : '#0071e3';
}

const labels = RAW.map(r => r.label);

// ── cards ────────────────────────────────────────────────
const last = RAW[RAW.length - 1];
document.getElementById('c-total').textContent    = fmtCLP(last?.TOTAL);
document.getElementById('c-personal').textContent = fmtCLP(last?.PERSONAL);
document.getElementById('c-count').textContent    = RAW.length;

const topCats = CAT_KEYS.slice(0,5).map(k => ({k, v: last?.[k] ?? 0}));
topCats.sort((a,b) => b.v - a.v);
document.getElementById('c-top-cat').textContent = CAT_LABELS[CAT_KEYS.indexOf(topCats[0].k)];
document.getElementById('c-top-val').textContent = fmtCLP(topCats[0].v);

const firstTotal = RAW.find(r => r.TOTAL != null)?.TOTAL;
const lastTotal  = [...RAW].reverse().find(r => r.TOTAL != null)?.TOTAL;
if (firstTotal && lastTotal)
  document.getElementById('c-growth').textContent = '+' + ((lastTotal/firstTotal-1)*100).toFixed(0) + '%';

// ── chart colours adapt to theme ─────────────────────────
function getThemeColor() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'terminal' ? '#e8e8f0' : t === 'dark' ? '#f5f5f7' : '#1d1d1f';
}
function getMutedColor() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'terminal' ? '#6b6b88' : t === 'dark' ? '#98989d' : '#6e6e73';
}
function getGridColor() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'terminal' ? '#1e1e2e' : t === 'dark' ? '#2c2c2e' : '#f0f0f5';
}
function getTipBg() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'terminal' ? 'rgba(17,17,24,0.98)' : t === 'dark' ? 'rgba(28,28,30,0.98)' : 'rgba(255,255,255,0.97)';
}
function getTipBorder() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'terminal' ? '#1e1e2e' : t === 'dark' ? '#3a3a3c' : '#e0e0e5';
}
function getTipTitle() {
  return document.documentElement.getAttribute('data-theme') === 'terminal'
    ? '#f0c040' : getThemeColor();
}
function getMonoFont() {
  return document.documentElement.getAttribute('data-theme') === 'terminal'
    ? "'Space Mono', monospace" : '-apple-system, sans-serif';
}

// ── data builders ────────────────────────────────────────
function buildCLPdata(key) {
  return RAW.map(r => r[key] ?? null);
}
function buildPCTdata(key) {
  return RAW.map(r => {
    if (r[key] == null || !r.TOTAL) return null;
    return +(r[key] / r.TOTAL * 100).toFixed(2);
  });
}

function getData1(key) {
  return mode1 === 'clp' ? buildCLPdata(key) : buildPCTdata(key);
}
function fmt1(v) { return mode1 === 'clp' ? fmtCLP(v) : fmtPct(v); }
function fmt2(v) { return mode2 === 'clp' ? fmtCLP(v) : fmtPct(v); }

// ── common chart options ──────────────────────────────────
function zoomCfg(btnId) {
  return {
    zoom: {
      drag: {
        enabled: true,
        backgroundColor: 'rgba(240,192,64,0.12)',
        borderColor: '#f0c040',
        borderWidth: 1,
      },
      mode: 'x',
      onZoom: () => { document.getElementById(btnId).style.display = 'inline-block'; }
    }
  };
}

function resetZoom(chart, btnId) {
  chart.resetZoom();
  document.getElementById(btnId).style.display = 'none';
}

function commonOptions(yCallback, fmtFn) {
  return {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top', align: 'end',
        labels: {
          boxWidth: 12, boxHeight: 12, borderRadius: 6,
          usePointStyle: true, pointStyle: 'circle',
          font: { size: 12, family: '-apple-system, sans-serif' },
          color: getThemeColor(), padding: 16,
        }
      },
      tooltip: {
        backgroundColor: getTipBg(),
        titleColor: getTipTitle(), bodyColor: getThemeColor(),
        borderColor: getTipBorder(), borderWidth: 1,
        padding: 12, cornerRadius: 12,
        titleFont: { weight: '600', size: 13, family: getMonoFont() },
        callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtFn(ctx.parsed.y)}` }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: getMutedColor(), font: { size: 10 }, maxRotation: 0,
          callback: function(val, idx) {
            const lbl = labels[idx];
            return lbl && lbl.endsWith('-01') ? lbl.slice(0,4) : '';
          }
        },
        border: { display: false }
      },
      y: {
        grid: { color: getGridColor() },
        ticks: { color: getMutedColor(), font: { size: 11 }, callback: yCallback },
        border: { display: false }
      }
    }
  };
}

// ── chart 1: categorías ──────────────────────────────────
const ctx1 = document.getElementById('chart1').getContext('2d');
const datasets1 = CAT_KEYS.map((key, i) => {
  const pal = getThemePalette();
  const col = key === 'TOTAL' ? getThemeColor() : pal[i];
  return {
    label: CAT_LABELS[i],
    data: getData1(key),
    borderColor: col,
    borderWidth: key === 'TOTAL' ? 2.5 : 1.8,
    backgroundColor: 'transparent',
    fill: false, tension: 0.3,
    pointRadius: 0, pointHoverRadius: 5,
    pointHoverBackgroundColor: col,
    borderDash: DASHES[i],
    spanGaps: true,
  };
});

const chart1opts = commonOptions(v => fmt1(v), fmt1);
chart1opts.plugins.zoom = zoomCfg('btn1-reset').zoom;
const chart1 = new Chart(ctx1, {
  type: 'line',
  data: { labels, datasets: datasets1 },
  options: chart1opts
});

// ── chart 2: gasto personal ──────────────────────────────
const ctx2 = document.getElementById('chart2').getContext('2d');
const c2init = getChart2Color();
const blueGrad = ctx2.createLinearGradient(0, 0, 0, 280);
blueGrad.addColorStop(0, c2init + '2e');
blueGrad.addColorStop(1, c2init + '00');

const chart2 = new Chart(ctx2, {
  type: 'line',
  data: {
    labels,
    datasets: [{
      label: 'Gasto común D602',
      data: buildCLPdata('PERSONAL'),
      borderColor: '#0071e3',
      borderWidth: 2.5,
      backgroundColor: blueGrad,
      fill: true, tension: 0.35,
      pointRadius: 0, pointHoverRadius: 5,
      pointHoverBackgroundColor: '#0071e3',
      spanGaps: true,
    }]
  },
  options: {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top', align: 'end',
        labels: {
          boxWidth: 12, boxHeight: 12, borderRadius: 6,
          usePointStyle: true, pointStyle: 'circle',
          font: { size: 12, family: '-apple-system, sans-serif' },
          color: getThemeColor(), padding: 16,
        }
      },
      tooltip: {
        backgroundColor: getTipBg(),
        titleColor: getThemeColor(), bodyColor: getThemeColor(),
        borderColor: getTipBorder(), borderWidth: 1,
        padding: 12, cornerRadius: 12,
        titleFont: { weight: '600', size: 13 },
        callbacks: { label: ctx => ` Gasto común: ${fmtCLP(ctx.parsed.y)}` }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: getMutedColor(), font: { size: 10 }, maxRotation: 0,
          callback: function(val, idx) {
            const lbl = labels[idx];
            return lbl && lbl.endsWith('-01') ? lbl.slice(0,4) : '';
          }
        },
        border: { display: false }
      },
      y: {
        min: 0,
        grid: { color: getGridColor() },
        ticks: { color: getMutedColor(), font: { size: 11 }, callback: v => fmtCLP(v) },
        border: { display: false }
      }
    },
    plugins: {
      zoom: zoomCfg('btn2-reset').zoom
    }
  }
});

// ── mode toggle chart 1 (CLP / %) ───────────────────────
function setMode1(m) {
  mode1 = m;
  document.getElementById('btn1-clp').classList.toggle('active', m === 'clp');
  document.getElementById('btn1-pct').classList.toggle('active', m === 'pct');
  document.getElementById('sub1').textContent =
    m === 'clp' ? 'Valores en pesos CLP por categoría mensual'
                : '% de cada categoría sobre el total mensual';
  datasets1.forEach((ds, i) => {
    const key = CAT_KEYS[i];
    ds.data = getData1(key);
    ds.hidden = (key === 'TOTAL' && m === 'pct');
    if (m === 'pct' && key !== 'TOTAL') {
      const firstVal = ds.data.find(v => v != null) ?? 0;
      const hex = ds.borderColor.replace('#','');
      ds.fill = { value: firstVal };
      ds.backgroundColor = '#' + hex + '30';
    } else {
      ds.fill = false;
      ds.backgroundColor = 'transparent';
    }
  });
  chart1.options.scales.y.ticks.callback = v => fmt1(v);
  chart1.update();
}

// ── mode toggle chart 2 (CLP / % del total edificio) ────
function setMode2(m) {
  mode2 = m;
  document.getElementById('btn2-clp').classList.toggle('active', m === 'clp');
  document.getElementById('btn2-pct').classList.toggle('active', m === 'pct');
  const firstVal = RAW.find(r => r.PERSONAL != null)?.PERSONAL;
  document.getElementById('sub2').textContent =
    m === 'clp' ? 'Gasto común proporcional al dominio (sin agua caliente ni carry-forwards)'
                : 'Crecimiento acumulado desde el primer mes (base = 100)';
  const ds = chart2.data.datasets[0];
  if (m === 'clp') {
    ds.data = buildCLPdata('PERSONAL');
    chart2.options.scales.y.min = 0;
    chart2.options.scales.y.ticks.callback = v => fmtCLP(v);
    chart2.options.plugins.tooltip.callbacks.label = ctx => ` Gasto común: ${fmtCLP(ctx.parsed.y)}`;
  } else {
    ds.data = RAW.map(r => (r.PERSONAL != null && firstVal)
      ? +(r.PERSONAL / firstVal * 100).toFixed(4) : null);
    chart2.options.scales.y.min = undefined;
    chart2.options.scales.y.ticks.callback = v => fmtPct3(v);
    chart2.options.plugins.tooltip.callbacks.label = ctx => ` Índice base 100: ${fmtPct3(ctx.parsed.y)}`;
  }
  chart2.update();
}

// ── theme cycle ───────────────────────────────────────────
const THEMES = ['light','dark','terminal'];
const THEME_ICONS = { light:'🌙', dark:'💻', terminal:'☀️' };

function applyThemeToChart(chart) {
  chart.options.plugins.legend.labels.color  = getThemeColor();
  chart.options.plugins.legend.labels.font   = { family: getMonoFont(), size: 12 };
  chart.options.plugins.tooltip.backgroundColor = getTipBg();
  chart.options.plugins.tooltip.titleColor   = getTipTitle();
  chart.options.plugins.tooltip.bodyColor    = getThemeColor();
  chart.options.plugins.tooltip.borderColor  = getTipBorder();
  chart.options.plugins.tooltip.titleFont    = { weight:'600', size:13, family: getMonoFont() };
  chart.options.scales.x.ticks.color = getMutedColor();
  chart.options.scales.x.ticks.font  = { size:10, family: getMonoFont() };
  chart.options.scales.y.ticks.color = getMutedColor();
  chart.options.scales.y.ticks.font  = { size:11, family: getMonoFont() };
  chart.options.scales.y.grid.color  = getGridColor();
  chart.update();
}

function cycleTheme() {
  const html = document.documentElement;
  const cur  = html.getAttribute('data-theme') || 'light';
  const next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
  html.setAttribute('data-theme', next);
  document.getElementById('btn-theme').textContent = THEME_ICONS[next];

  // update dataset colors for chart1
  const pal = getThemePalette();
  datasets1.forEach((ds, i) => {
    const key = CAT_KEYS[i];
    const col = key === 'TOTAL' ? getThemeColor() : pal[i];
    ds.borderColor = col;
    ds.pointHoverBackgroundColor = col;
    if (ds.fill && ds.fill !== false)
      ds.backgroundColor = col + '28';
  });

  // update chart2 line color
  const c2col = getChart2Color();
  const c2ds  = chart2.data.datasets[0];
  c2ds.borderColor = c2col;
  c2ds.pointHoverBackgroundColor = c2col;
  const c2ctx = document.getElementById('chart2').getContext('2d');
  const c2grad = c2ctx.createLinearGradient(0, 0, 0, 280);
  c2grad.addColorStop(0, c2col + '2e');
  c2grad.addColorStop(1, c2col + '00');
  c2ds.backgroundColor = c2grad;

  applyThemeToChart(chart1);
  applyThemeToChart(chart2);
}
</script>
</body>
</html>"""


def build_html(records: list[dict]) -> None:
    payload = [
        {
            "year": r["year"], "month": r["month"], "label": r["label"],
            "ADMINISTRACIÓN": r.get("ADMINISTRACIÓN"),
            "MANTENCIÓN":     r.get("MANTENCIÓN"),
            "USO CONSUMO":    r.get("USO CONSUMO"),
            "REPARACIÓN":     r.get("REPARACIÓN"),
            "EQUIPAMIENTO":   r.get("EQUIPAMIENTO"),
            "TOTAL":          r.get("TOTAL"),
            "PERSONAL":       r.get("PERSONAL"),
            "TAP":            r.get("TAP"),
        }
        for r in records
    ]
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    out = Path("ggcc/ggcc_chart.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    webbrowser.open(out.resolve().as_uri())
    print(f"Chart guardado en {out.resolve()}")


if __name__ == "__main__":
    records = scan_all()
    build_html(records)
