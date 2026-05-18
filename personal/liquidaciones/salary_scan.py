import re
from datetime import date
from pathlib import Path

import pdfplumber
import json
import webbrowser
import tempfile

LIQUIDACIONES_PATH = r"C:\Users\diego\OneDrive\Liquidaciones"

MONTH_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "abrl": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_NAMES = {**MONTH_ES, **MONTH_EN}

MONTH_NUM_TO_NAME = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

SKIP_YEARS = {2020, 2021}
YEAR_2019_MAX_MONTH = 9
YEAR_2022_MIN_MONTH = 8


def is_excluded(path: Path) -> bool:
    name = path.name
    parts = path.parts
    if any("Contracts Addendeum" in p for p in parts):
        return True
    if re.match(r"R010993", name, re.IGNORECASE):
        return True
    if re.match(r"Tax File", name, re.IGNORECASE):
        return True
    if re.search(r"-bono", name, re.IGNORECASE):
        return True
    if re.search(r"_IC", name, re.IGNORECASE):
        return True
    return False


def parse_month(filename_stem: str) -> int | None:
    stem = filename_stem.lower()
    m = re.match(r"\d{4}-(\d{2})-([a-z]+)", stem)
    if m:
        return int(m.group(1))
    m = re.match(r"\d{4}_([a-z]+)", stem)
    if m:
        return MONTH_NAMES.get(m.group(1))
    return None


def parse_clp(text: str) -> float | None:
    """Parse Chilean number format: 1.234.567,89 → 1234567.89"""
    clean = text.replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


def extract_amounts(pdf_path: str) -> dict[str, float | None]:
    """Extract sueldo_base and neto from a liquidacion PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return {"sueldo_base": None, "neto": None}

    sueldo_base = None
    neto = None

    m = re.search(r"Sueldo\s+base\s+([\d.,]+)", text, re.IGNORECASE)
    if m:
        sueldo_base = parse_clp(m.group(1))

    # 2019+: "TOTAL A PAGAR 4.150.849"
    m = re.search(r"TOTAL\s+A\s+PAGAR\s+([\d.,]+)", text, re.IGNORECASE)
    if m:
        neto = parse_clp(m.group(1))

    # 2008-2018: "Monto líquido: 1.594.644"
    if neto is None:
        m = re.search(r"Monto\s+l[íi]quido\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        if m:
            neto = parse_clp(m.group(1))

    return {"sueldo_base": sueldo_base, "neto": neto}


def is_bono_ic(path: Path) -> bool:
    name = path.name
    if re.search(r"-bono", name, re.IGNORECASE):
        return True
    if re.search(r"_IC\.pdf$", name, re.IGNORECASE) and not re.search(r"_plus_IC", name, re.IGNORECASE):
        return True
    return False


def extract_bonus_amount(pdf_path: str) -> dict:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return {"bruto": None, "neto": None}

    bruto = None
    neto = None

    for pattern in [
        r"Incentivo\s+Anual\s+por\s+Desempe[ñn]o\s+([\d.,]+)",
        r"Bono\s+Desempe[ñn]o\s+\d{4}\s+([\d.,]+)",
        r"Bono\s+[Aa][ñn]o\s+\d{4}\s+([\d.,]+)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            bruto = parse_clp(m.group(1))
            break

    m = re.search(r"TOTAL\s+A\s+PAGAR\s+([\d.,]+)", text, re.IGNORECASE)
    if m:
        neto = parse_clp(m.group(1))
    if neto is None:
        m = re.search(r"Monto\s+l[íi]quido\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        if m:
            neto = parse_clp(m.group(1))
    if neto is None:
        m = re.search(r"L[íi]quido\s*:\s*([\d.,]+)", text, re.IGNORECASE)
        if m:
            neto = parse_clp(m.group(1))

    return {"bruto": bruto, "neto": neto}


def scan_bonos() -> list[dict]:
    results = []
    root = Path(LIQUIDACIONES_PATH)
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not re.match(r"^\d{4}$", year_dir.name):
            continue
        year = int(year_dir.name)
        if year in SKIP_YEARS:
            continue
        for file in sorted(year_dir.iterdir()):
            if file.suffix.lower() != ".pdf":
                continue
            if any("Contracts Addendeum" in p for p in file.parts):
                continue
            if re.match(r"R010993|Tax File", file.name, re.IGNORECASE):
                continue
            if not is_bono_ic(file):
                continue
            month = parse_month(file.stem)
            if month is None:
                continue
            if year == 2019 and month > YEAR_2019_MAX_MONTH:
                continue
            if year == 2022 and month < YEAR_2022_MIN_MONTH:
                continue
            kind = "IC" if re.search(r"_IC\.pdf$", file.name, re.IGNORECASE) else "bono"
            results.append({"year": year, "month": month, "kind": kind,
                            "filename": file.name, "path": str(file)})
    return results


def scan_liquidaciones() -> list[dict]:
    results = []
    root = Path(LIQUIDACIONES_PATH)

    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not re.match(r"^\d{4}$", year_dir.name):
            continue
        year = int(year_dir.name)
        if year in SKIP_YEARS:
            continue

        for file in sorted(year_dir.iterdir()):
            if file.suffix.lower() != ".pdf":
                continue
            if is_excluded(file):
                continue
            month = parse_month(file.stem)
            if month is None:
                continue
            if year == 2019 and month > YEAR_2019_MAX_MONTH:
                continue
            if year == 2022 and month < YEAR_2022_MIN_MONTH:
                continue

            results.append({
                "year": year,
                "month": month,
                "month_name": MONTH_NUM_TO_NAME[month],
                "filename": file.name,
                "path": str(file),
            })

    return results


def extract_all(rows: list[dict]) -> list[dict]:
    print(f"Extrayendo datos de {len(rows)} PDFs...")
    enriched = []
    for i, r in enumerate(rows, 1):
        amounts = extract_amounts(r["path"])
        enriched.append({**r, **amounts})
        if i % 20 == 0:
            print(f"  {i}/{len(rows)}")
    print("Listo.")
    return enriched


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Remuneraciones</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-filler@2.0.0/dist/chartjs-plugin-filler.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
    background: #f5f5f7;
    color: #1d1d1f;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 24px;
  }
  header { text-align: center; margin-bottom: 40px; }
  header h1 { font-size: 32px; font-weight: 700; letter-spacing: -0.5px; }
  header p  { font-size: 15px; color: #6e6e73; margin-top: 6px; }

  .cards {
    display: flex; gap: 16px; margin-bottom: 36px; flex-wrap: wrap; justify-content: center;
  }
  .card {
    background: #fff;
    border-radius: 18px;
    padding: 20px 28px;
    min-width: 160px;
    box-shadow: 0 2px 12px rgba(0,0,0,.06);
  }
  .card .label { font-size: 12px; color: #6e6e73; text-transform: uppercase; letter-spacing: .5px; }
  .card .value { font-size: 26px; font-weight: 600; margin-top: 4px; letter-spacing: -0.5px; }
  .card.blue  .value { color: #0071e3; }
  .card.green .value { color: #34c759; }

  .chart-wrap {
    background: #fff;
    border-radius: 22px;
    padding: 32px 32px 24px;
    box-shadow: 0 2px 20px rgba(0,0,0,.07);
    width: 100%;
    max-width: 1100px;
  }
  .chart-title {
    font-size: 17px; font-weight: 600; margin-bottom: 4px;
  }
  .chart-sub {
    font-size: 13px; color: #6e6e73; margin-bottom: 24px;
  }
  canvas { width: 100% !important; }
</style>
</head>
<body>

<header>
  <h1>Remuneraciones</h1>
  <p>Diego Rost &mdash; 2008 – 2026</p>
</header>

<div class="cards">
  <div class="card blue">
    <div class="label">Último neto</div>
    <div class="value" id="last-neto">—</div>
  </div>
  <div class="card">
    <div class="label">Último sueldo base</div>
    <div class="value" id="last-base">—</div>
  </div>
  <div class="card green">
    <div class="label">Crecimiento total</div>
    <div class="value" id="growth">—</div>
  </div>
  <div class="card">
    <div class="label">Liquidaciones</div>
    <div class="value" id="total">—</div>
  </div>
</div>

<div class="chart-wrap">
  <div class="chart-title">Evolución mensual</div>
  <div class="chart-sub">Sueldo base y neto a pagar en millones CLP</div>
  <canvas id="chart" height="320"></canvas>
</div>

<div style="height:48px"></div>

<div class="cards">
  <div class="card blue">
    <div class="label">Último bono neto</div>
    <div class="value" id="b-last-neto">—</div>
  </div>
  <div class="card">
    <div class="label">Último bono bruto</div>
    <div class="value" id="b-last-bruto">—</div>
  </div>
  <div class="card" style="color:#ff453a">
    <div class="label">Retención impuesto</div>
    <div class="value" id="b-retencion" style="color:#ff453a">—</div>
  </div>
  <div class="card">
    <div class="label">Bonos / IC</div>
    <div class="value" id="b-total">—</div>
  </div>
</div>

<div class="chart-wrap">
  <div class="chart-title">Bono Anual e Incentivo (IC)</div>
  <div class="chart-sub">Bruto y neto recibido por año, en millones CLP</div>
  <canvas id="bonus-chart" height="260"></canvas>
</div>

<script>
const RAW = __DATA__;

const fmt = v => {
  const m = v / 1e6;
  return m >= 1 ? `$${m.toFixed(2)}M` : `$${(v/1e3).toFixed(0)}K`;
};

const labels = RAW.map(r => `${r.year}-${String(r.month).padStart(2,'0')}`);
const neto   = RAW.map(r => r.neto ?? null);
const base   = RAW.map(r => r.sueldo_base ?? null);

// cards
const lastNeto = [...neto].reverse().find(v => v !== null);
const lastBase = [...base].reverse().find(v => v !== null);
const firstNeto = neto.find(v => v !== null);
document.getElementById('last-neto').textContent = fmt(lastNeto);
document.getElementById('last-base').textContent = fmt(lastBase);
document.getElementById('growth').textContent    = `+${((lastNeto/firstNeto - 1)*100).toFixed(0)}%`;
document.getElementById('total').textContent     = RAW.length;

const ctx = document.getElementById('chart').getContext('2d');

const blueGrad = ctx.createLinearGradient(0, 0, 0, 380);
blueGrad.addColorStop(0, 'rgba(0,113,227,0.18)');
blueGrad.addColorStop(1, 'rgba(0,113,227,0)');

new Chart(ctx, {
  type: 'line',
  data: {
    labels,
    datasets: [
      {
        label: 'Neto a pagar',
        data: neto,
        borderColor: '#0071e3',
        borderWidth: 2.5,
        backgroundColor: blueGrad,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#0071e3',
      },
      {
        label: 'Sueldo base',
        data: base,
        borderColor: '#ff9f0a',
        borderWidth: 2,
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#ff9f0a',
        borderDash: [5, 4],
      }
    ]
  },
  options: {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: {
          boxWidth: 12, boxHeight: 12, borderRadius: 6,
          usePointStyle: true, pointStyle: 'circle',
          font: { size: 13, family: '-apple-system, BlinkMacSystemFont, sans-serif' },
          color: '#1d1d1f',
          padding: 20,
        }
      },
      tooltip: {
        backgroundColor: 'rgba(255,255,255,0.95)',
        titleColor: '#1d1d1f',
        bodyColor: '#1d1d1f',
        borderColor: '#e0e0e5',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 12,
        titleFont: { weight: '600', size: 13 },
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y)}`,
          afterBody: items => {
            const n = items.find(i => i.datasetIndex === 0)?.parsed.y;
            const b = items.find(i => i.datasetIndex === 1)?.parsed.y;
            if (n == null || b == null) return [];
            const pct = ((n - b) / b * 100).toFixed(1);
            const sign = pct >= 0 ? '+' : '';
            return [` Descuento neto: ${sign}${pct}%`];
          }
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: '#6e6e73',
          font: { size: 11 },
          maxRotation: 0,
          callback: function(val, idx) {
            const lbl = labels[idx];
            return lbl && lbl.endsWith('-01') ? lbl.slice(0,4) : '';
          }
        },
        border: { display: false }
      },
      y: {
        grid: { color: '#f0f0f5', drawBorder: false },
        ticks: {
          color: '#6e6e73',
          font: { size: 11 },
          callback: v => fmt(v)
        },
        border: { display: false }
      }
    }
  }
});

// ── Bonus chart ───────────────────────────────────────────
const BONUS = __BONUS_DATA__;

const lastB = [...BONUS].reverse().find(b => b.neto != null);
const lastBruto = lastB?.bruto;
const lastBneto = lastB?.neto;
document.getElementById('b-last-neto').textContent  = lastBneto  ? fmt(lastBneto)  : '—';
document.getElementById('b-last-bruto').textContent = lastBruto  ? fmt(lastBruto)  : '—';
document.getElementById('b-total').textContent      = BONUS.length;
if (lastBruto && lastBneto) {
  const ret = ((lastBruto - lastBneto) / lastBruto * 100).toFixed(1);
  document.getElementById('b-retencion').textContent = `${ret}%`;
}

const bLabels = BONUS.map(b => `${b.year}`);
const bBruto  = BONUS.map(b => b.bruto ?? null);
const bNeto   = BONUS.map(b => b.neto  ?? null);

const ctx2 = document.getElementById('bonus-chart').getContext('2d');

const greenGrad = ctx2.createLinearGradient(0, 0, 0, 320);
greenGrad.addColorStop(0, 'rgba(52,199,89,0.18)');
greenGrad.addColorStop(1, 'rgba(52,199,89,0)');

new Chart(ctx2, {
  type: 'line',
  data: {
    labels: bLabels,
    datasets: [
      {
        label: 'Neto recibido',
        data: bNeto,
        borderColor: '#34c759',
        borderWidth: 2.5,
        backgroundColor: greenGrad,
        fill: true,
        tension: 0.35,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: '#34c759',
      },
      {
        label: 'Bruto',
        data: bBruto,
        borderColor: '#ff9f0a',
        borderWidth: 2,
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.35,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: '#ff9f0a',
        borderDash: [5, 4],
      }
    ]
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
          font: { size: 13, family: '-apple-system, BlinkMacSystemFont, sans-serif' },
          color: '#1d1d1f', padding: 20,
        }
      },
      tooltip: {
        backgroundColor: 'rgba(255,255,255,0.95)',
        titleColor: '#1d1d1f', bodyColor: '#1d1d1f',
        borderColor: '#e0e0e5', borderWidth: 1,
        padding: 12, cornerRadius: 12,
        titleFont: { weight: '600', size: 13 },
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y)}`,
          afterBody: items => {
            const ne = items.find(i => i.datasetIndex === 0)?.parsed.y;
            const br = items.find(i => i.datasetIndex === 1)?.parsed.y;
            if (br == null || ne == null) return [];
            const ret = ((br - ne) / br * 100).toFixed(1);
            return [` Retención: ${ret}%`];
          }
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#6e6e73', font: { size: 11 } },
        border: { display: false }
      },
      y: {
        grid: { color: '#f0f0f5' },
        ticks: { color: '#6e6e73', font: { size: 11 }, callback: v => fmt(v) },
        border: { display: false }
      }
    }
  }
});
</script>
</body>
</html>"""


def plot_salaries(rows: list[dict], bonus_rows: list[dict]) -> None:
    data = sorted(
        [r for r in rows if r.get("neto") is not None],
        key=lambda r: (r["year"], r["month"])
    )
    payload = [
        {"year": r["year"], "month": r["month"],
         "neto": r["neto"], "sueldo_base": r.get("sueldo_base")}
        for r in data
    ]

    bonus_data = sorted(
        [r for r in bonus_rows if r.get("neto") is not None],
        key=lambda r: (r["year"], r["month"])
    )
    bonus_payload = [
        {"year": r["year"], "month": r["month"], "kind": r["kind"],
         "bruto": r.get("bruto"), "neto": r["neto"]}
        for r in bonus_data
    ]

    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(payload))
            .replace("__BONUS_DATA__", json.dumps(bonus_payload)))
    out = Path("liquidaciones/salary_chart.html")
    out.write_text(html, encoding="utf-8")
    webbrowser.open(out.resolve().as_uri())
    print(f"Chart guardado en {out.resolve()}")


def check_gaps(rows: list[dict]) -> None:
    today = date.today()
    by_year: dict[int, set[int]] = {}
    for r in rows:
        by_year.setdefault(r["year"], set()).add(r["month"])

    gaps = []
    for year, months in sorted(by_year.items()):
        if year == 2019:
            expected = set(range(1, YEAR_2019_MAX_MONTH + 1))
        elif year == 2022:
            expected = set(range(YEAR_2022_MIN_MONTH, 13))
        elif year == 2008:
            expected = set(range(5, 13))
        else:
            expected = set(range(1, 13))

        expected = {m for m in expected if (year, m) <= (today.year, today.month)}
        missing = expected - months
        for m in sorted(missing):
            gaps.append(f"  {year}-{m:02d} ({MONTH_NUM_TO_NAME[m]})")

    if gaps:
        print("\nMissing months:")
        print("\n".join(gaps))
    else:
        print("\nNo missing months detected.")


if __name__ == "__main__":
    rows = scan_liquidaciones()
    enriched = extract_all(rows)
    check_gaps(enriched)

    bonus_rows = scan_bonos()
    print(f"\nExtrayendo datos de {len(bonus_rows)} PDFs de bono/IC...")
    bonus_enriched = []
    for r in bonus_rows:
        amounts = extract_bonus_amount(r["path"])
        bonus_enriched.append({**r, **amounts})
    print("Listo.")

    plot_salaries(enriched, bonus_enriched)
