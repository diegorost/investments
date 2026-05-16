"""
tax_return.py
Reads Racional/DriveWealth and Fintual monthly PDF statements and prints
per-ticker transaction history with running avg cost.

Usage:
    python tax_return.py                          # serves HTML on :5050
    python tax_return.py ./Racional/
    python tax_return.py ./Racional/ --ticker AGQ
    python tax_return.py ./Racional/ --no-serve   # plain text output
"""

import re
import sys
import argparse
import webbrowser
import threading
from pathlib import Path
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    print("Instalando pdfplumber...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"])
    import pdfplumber

from flask import Flask, render_template_string


# ── regex para líneas de transacción — formato trade confirmation Racional/Fintual ──
TX_RE = re.compile(
    r"^([A-Z][A-Z0-9.]{0,5})\s+"                    # Ticker (first word)
    r".+?\b(Buy|Sell)\b\s+"                          # Description ... Action
    r"(\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))\s+"         # Execution time (captured)
    r"-?([\d.]+)\s+"                                 # Quantity (negative on sells)
    r"([\d.]+)\s+"                                   # Price
    r"(\d{1,2}/\d{1,2}/\d{4})",                     # Trade Date (M/D/YYYY or MM/DD/YYYY)
    re.I,
)

ACAT_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+\d{2}/\d{2}/\d{4}\s+USD\s+ACATS\s+([A-Z]{1,6})\s+-.+:\s+([\d.]+)\s+0\.00\s+0\.00",
)

# ── regex para líneas de transacción — formato Alpaca/Fintual monthly statement ──
# Format: MM/DD/YYYY  Trade Entry  buy|sell  SYMBOL  QUANTITY  $PRICE  -$AMOUNT  $ --
FINTUAL_TX_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4})\s+"     # Trade Date
    r"Trade\s+Entry\s+"                  # Entry Type (skip Memopost, etc.)
    r"(buy|sell)\s+"                     # Side
    r"([A-Z]{1,6})\s+"                  # Symbol
    r"([\d,]+\.?\d*)\s+"                # Quantity
    r"\$([\d,]+\.?\d+)\s+"             # Price
    r"-?\$([\d,]+\.?\d+)",              # Amount (sign ignored — recomputed from side)
    re.I,
)

RACIONAL_DAILY_FOLDER   = Path(r"C:\Users\diego\OneDrive\Inversiones\Racional\Detalle Acciones Diario")
RACIONAL_MONTHLY_FOLDER = Path(r"C:\Users\diego\OneDrive\Inversiones\Racional\Detalle Acciones Mensual")
FINTUAL_MONTHLY_FOLDER  = Path(r"C:\Users\diego\OneDrive\Inversiones\Fintual\Detalle Acciones Mensual")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Tax Return - Racional / Fintual</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; padding: 2rem; }
  h1 { font-size: 1.4rem; font-weight: 600; color: #f8fafc; margin-bottom: 0.25rem; }
  .subtitle { color: #64748b; font-size: 0.85rem; margin-bottom: 1.5rem; }
  .summary { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat { background: #1e2130; border: 1px solid #2d3348; border-radius: 8px; padding: 0.75rem 1.25rem; }
  .stat-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-value { font-size: 1.1rem; font-weight: 600; color: #f8fafc; margin-top: 0.2rem; }
  .tabs { display: flex; gap: 0; margin-bottom: 1.5rem; border-bottom: 1px solid #2d3348; }
  .tab-btn { background: none; border: none; border-bottom: 2px solid transparent; color: #64748b;
             font-size: 0.9rem; font-weight: 600; padding: 0.6rem 1.25rem; cursor: pointer;
             margin-bottom: -1px; transition: color 0.15s; }
  .tab-btn:hover { color: #e2e8f0; }
  .tab-btn.active { color: #818cf8; border-bottom-color: #818cf8; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .ticker-header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 0.5rem; }
  .ticker-name { font-size: 1.1rem; font-weight: 700; color: #818cf8; }
  .ticker-summary { font-size: 0.82rem; color: #94a3b8; }
  .position-open  { color: #34d399; }
  .position-closed { color: #64748b; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  th { text-align: right; padding: 0.4rem 0.75rem; color: #64748b; font-weight: 500;
       border-bottom: 1px solid #2d3348; white-space: nowrap; }
  th:first-child, th:nth-child(2), th:nth-child(3), th:nth-child(4) { text-align: left; }
  td { text-align: right; padding: 0.35rem 0.75rem; border-bottom: 1px solid #1e2130; white-space: nowrap; }
  td:first-child, td:nth-child(2), td:nth-child(3), td:nth-child(4) { text-align: left; }
  tr:last-child td { border-bottom: none; }
  .buy  { color: #f87171; }
  .sell { color: #34d399; }
  .source-racional { color: #818cf8; font-weight: 600; }
  .source-fintual  { color: #f59e0b; font-weight: 600; }
  .ticker-card { background: #1e2130; border: 1px solid #2d3348; border-radius: 10px;
                 padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
  .closed-total { background: #1e2130; border: 1px solid #2d3348; border-radius: 10px;
                  padding: 1rem 1.25rem; display: flex; align-items: center; gap: 2rem; }
  .closed-total-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .closed-total-value { font-size: 1.1rem; font-weight: 600; color: #f8fafc; margin-top: 0.2rem; }
</style>
</head>
<body>
<h1>Tax Return &mdash; Racional / Fintual</h1>
<p class="subtitle">{{ pdf_count }} statements &bull; {{ total_txs }} transactions &bull; {{ ticker_count }} tickers</p>

<div class="summary">
  <div class="stat"><div class="stat-label">Open Positions</div><div class="stat-value">{{ open_count }}</div></div>
  <div class="stat"><div class="stat-label">Closed Positions</div><div class="stat-value">{{ closed_count }}</div></div>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="showTab('open', this)">Open Positions ({{ open_count }})</button>
  <button class="tab-btn" onclick="showTab('closed', this)">Closed Positions ({{ closed_count }})</button>
  <button class="tab-btn" onclick="showTab('acat', this)">ACAT ({{ acat_count }})</button>
</div>

<div id="tab-open" class="tab-panel active">
{% for ticker, rows in open_tickers %}
  {% set last = rows[-1] %}
  {% set total_amount = rows | sum(attribute="amount") %}
  <div class="ticker-card">
    <div class="ticker-header">
      <span class="ticker-name">{{ ticker }}</span>
      <span class="ticker-summary position-open">
        {{ "%.8f"|format(last.shares_after) }} shares &bull; avg ${{ "%.4f"|format(last.avg_after) }}
      </span>
    </div>
    <table>
      <thead><tr>
        <th>Source</th><th>Date</th><th>Time</th><th>Side</th>
        <th>Shares</th><th>Price</th><th>Amount</th>
        <th>Acc. Shares</th><th>Avg Cost</th>
      </tr></thead>
      <tbody>
      {% for r in rows %}
        <tr>
          <td class="source-{{ r.broker|lower }}">{{ r.broker }}</td>
          <td>{{ r.date }}</td>
          <td>{{ r.time }}</td>
          <td class="{{ r.side }}">{{ r.side }}</td>
          <td class="{{ r.side }}">{{ '+' if r.side == 'buy' else '-' }}{{ "%.8f"|format(r.qty) }}</td>
          <td>${{ "%.4f"|format(r.price) }}</td>
          <td class="{{ r.side }}">{{ "-" if r.amount < 0 else "+" }}${{ "%.2f"|format(r.amount|abs) }}</td>
          <td>{{ "%.8f"|format(r.shares_after) }}</td>
          <td>${{ "%.4f"|format(r.avg_after) }}</td>
        </tr>
      {% endfor %}
      </tbody>
      <tfoot>
        <tr style="border-top:1px solid #2d3348; font-weight:600;">
          <td colspan="6" style="text-align:right; padding: 0.4rem 0.75rem; color:#94a3b8;">Total</td>
          <td style="color:{{ '#34d399' if total_amount > 0 else '#f87171' }}">{{ "-" if total_amount < 0 else "" }}${{ "%.2f"|format(total_amount|abs) }}</td>
          <td colspan="2"></td>
        </tr>
      </tfoot>
    </table>
  </div>
{% endfor %}
</div>

<div id="tab-closed" class="tab-panel">
{% for ticker, rows in closed_tickers %}
  {% set total_amount = rows | sum(attribute="amount") %}
  <div class="ticker-card">
    <div class="ticker-header">
      <span class="ticker-name">{{ ticker }}</span>
    </div>
    <table>
      <thead><tr>
        <th>Source</th><th>Date</th><th>Time</th><th>Side</th>
        <th>Shares</th><th>Price</th><th>Amount</th>
        <th>Acc. Shares</th><th>Avg Cost</th>
      </tr></thead>
      <tbody>
      {% for r in rows %}
        <tr>
          <td class="source-{{ r.broker|lower }}">{{ r.broker }}</td>
          <td>{{ r.date }}</td>
          <td>{{ r.time }}</td>
          <td class="{{ r.side }}">{{ r.side }}</td>
          <td class="{{ r.side }}">{{ '+' if r.side == 'buy' else '-' }}{{ "%.8f"|format(r.qty) }}</td>
          <td>${{ "%.4f"|format(r.price) }}</td>
          <td class="{{ r.side }}">{{ "-" if r.amount < 0 else "+" }}${{ "%.2f"|format(r.amount|abs) }}</td>
          <td>{{ "%.8f"|format(r.shares_after) }}</td>
          <td>${{ "%.4f"|format(r.avg_after) }}</td>
        </tr>
      {% endfor %}
      </tbody>
      <tfoot>
        <tr style="border-top:1px solid #2d3348; font-weight:600;">
          <td colspan="6" style="text-align:right; padding: 0.4rem 0.75rem; color:#94a3b8;">Total</td>
          <td style="color:{{ '#34d399' if total_amount > 0 else '#f87171' }}">{{ "-" if total_amount < 0 else "" }}${{ "%.2f"|format(total_amount|abs) }}</td>
          <td colspan="2"></td>
        </tr>
      </tfoot>
    </table>
  </div>
{% endfor %}
<div class="closed-total">
  <div><div class="closed-total-label">Closed Positions</div><div class="closed-total-value">{{ closed_count }}</div></div>
  <div><div class="closed-total-label">Net</div><div class="closed-total-value" style="color:{{ '#34d399' if closed_total > 0 else '#f87171' }}">{{ "-" if closed_total < 0 else "+" }}${{ "%.2f"|format(closed_total|abs) }}</div></div>
</div>
</div>

<div id="tab-acat" class="tab-panel">
{% for ticker, rows in acat_tickers %}
  {% set total_amount = rows | sum(attribute="amount") %}
  <div class="ticker-card">
    <div class="ticker-header">
      <span class="ticker-name">{{ ticker }}</span>
        <span class="ticker-summary" style="color:#f59e0b;">ACAT transfer</span>
    </div>
    <table>
      <thead><tr>
        <th>Source</th><th>Date</th><th>Time</th><th>Side</th>
        <th>Shares</th><th>Price</th><th>Amount</th>
        <th>Acc. Shares</th><th>Avg Cost</th>
      </tr></thead>
      <tbody>
      {% for r in rows %}
        <tr>
          <td class="source-{{ r.broker|lower }}">{{ r.broker }}</td>
          <td>{{ r.date }}</td>
          <td>{{ r.time }}</td>
          <td style="color:#f59e0b;">{{ r.side }}</td>
          <td style="color:#f59e0b;">{{ '+' if r.side in ('buy','acat') else '-' }}{{ "%.8f"|format(r.qty) }}</td>
          <td>{{ "$%.4f"|format(r.price) if r.price else "—" }}</td>
          <td>{{ ("-" if r.amount < 0 else "+") + "$%.2f"|format(r.amount|abs) if r.amount else "—" }}</td>
          <td>{{ "%.8f"|format(r.shares_after) }}</td>
          <td>{{ "$%.4f"|format(r.avg_after) if r.avg_after else "—" }}</td>
        </tr>
      {% endfor %}
      </tbody>
      {% if total_amount %}
      <tfoot>
        <tr style="border-top:1px solid #2d3348; font-weight:600;">
          <td colspan="6" style="text-align:right; padding: 0.4rem 0.75rem; color:#94a3b8;">Total</td>
          <td style="color:{{ '#34d399' if total_amount > 0 else '#f87171' }}">{{ "-" if total_amount < 0 else "" }}${{ "%.2f"|format(total_amount|abs) }}</td>
          <td colspan="2"></td>
        </tr>
      </tfoot>
      {% endif %}
    </table>
  </div>
{% endfor %}
<div class="closed-total">
  <div><div class="closed-total-label">ACAT Tickers</div><div class="closed-total-value">{{ acat_count }}</div></div>
  <div><div class="closed-total-label">Net</div><div class="closed-total-value" style="color:{{ '#34d399' if acat_total > 0 else '#f87171' }}">{{ "-" if acat_total < 0 else "+" }}${{ "%.2f"|format(acat_total|abs) }}</div></div>
</div>
</div>

<script>
function showTab(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}
</script>
</body>
</html>
"""


def parse_number(s):
    return float(s.replace(",", "").replace("$", ""))


def extract_transactions(pdf_path, broker="Racional"):
    txs = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        for line in full_text.splitlines():
            line = line.strip()
            m = TX_RE.match(line)
            if not m:
                continue
            ticker, action, time_s, qty_s, price_s, date_s = m.groups()
            month, day, year = date_s.split("/")
            date = f"{int(month):02d}/{int(day):02d}/{year}"
            qty   = float(qty_s)
            price = float(price_s)
            txs.append({
                "date":   date,
                "time":   time_s.strip(),
                "side":   action.lower(),
                "ticker": ticker.upper(),
                "qty":    qty,
                "price":  price,
                "amount": round(qty * price * (-1 if action.lower() == "buy" else 1), 2),
                "broker": broker,
                "source": pdf_path.name,
            })
    except Exception as e:
        print(f"  [!] Error leyendo {pdf_path.name}: {e}")
    return txs


def extract_fintual_transactions(pdf_path, broker="Fintual"):
    txs = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        for line in full_text.splitlines():
            line = line.strip()
            m = FINTUAL_TX_RE.match(line)
            if not m:
                continue
            date_s, action, ticker, qty_s, price_s, _ = m.groups()
            month, day, year = date_s.split("/")
            date  = f"{int(month):02d}/{int(day):02d}/{year}"
            qty   = float(qty_s.replace(",", ""))
            price = float(price_s.replace(",", ""))
            txs.append({
                "date":   date,
                "time":   "—",
                "side":   action.lower(),
                "ticker": ticker.upper(),
                "qty":    qty,
                "price":  price,
                "amount": round(qty * price * (-1 if action.lower() == "buy" else 1), 2),
                "broker": broker,
                "source": pdf_path.name,
            })
    except Exception as e:
        print(f"  [!] Error leyendo {pdf_path.name}: {e}")
    return txs


def extract_acat_tickers(monthly_sources=None):
    """
    monthly_sources: list of (folder_path, broker_name) tuples.
    Falls back to Racional monthly folder if None.
    """
    if monthly_sources is None:
        monthly_sources = [(RACIONAL_MONTHLY_FOLDER, "Racional")]

    tickers = set()
    transfers = defaultdict(list)
    for monthly_folder, broker in monthly_sources:
        if not Path(monthly_folder).is_dir():
            continue
        for pdf_path in sorted(Path(monthly_folder).glob("*.pdf")):
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                for line in text.splitlines():
                    m = ACAT_RE.match(line.strip())
                    if m:
                        date, ticker, qty_s = m.group(1), m.group(2), m.group(3)
                        tickers.add(ticker)
                        transfers[ticker].append({"date": date, "qty": float(qty_s), "broker": broker})
            except Exception as e:
                print(f"  [!] Error leyendo {pdf_path.name}: {e}")
    return tickers, transfers


def compute_avg(transactions):
    total_shares = 0.0
    total_cost   = 0.0
    result = []
    for tx in transactions:
        if tx["side"] == "buy":
            total_shares += tx["qty"]
            total_cost   += tx["qty"] * tx["price"]
        else:
            avg_before = total_cost / total_shares if total_shares > 0 else 0.0
            total_shares -= tx["qty"]
            if total_shares < 0:
                total_shares = 0.0
                total_cost   = 0.0
            else:
                total_cost = total_shares * avg_before
        avg_after = total_cost / total_shares if total_shares > 0 else 0.0
        result.append({**tx, "shares_after": total_shares, "avg_after": avg_after, "capital_after": total_cost})
    return result


def print_ticker(ticker, rows):
    print(f"\n{'='*70}")
    print(f"  {ticker}")
    print(f"{'='*70}")
    print(f"  {'Fecha':<12} {'Lado':<5} {'Shares':>12} {'Precio':>10} {'Cap. Inv.':>12} {'Shares Acc':>12} {'Avg Cost':>10}")
    print(f"  {'-'*76}")
    for r in rows:
        sign = "+" if r["side"] == "buy" else "-"
        print(
            f"  {r['date']:<12} {r['side']:<5} "
            f"{sign}{r['qty']:>11.8f} "
            f"${r['price']:>9.4f} "
            f"${r['capital_after']:>11.2f} "
            f"{r['shares_after']:>12.8f} "
            f"${r['avg_after']:>9.4f}"
        )
    last = rows[-1]
    buy_shares = sum(r["qty"] for r in rows if r["side"] == "buy")
    print(
        f"\n  -> Posicion actual: {last['shares_after']:.8f} shares"
        f"  |  Suma shares: {buy_shares:.8f}"
        f"  |  Capital invertido: ${last['capital_after']:.2f}"
        f"  |  Avg: ${last['avg_after']:.4f}"
    )


def load_data(sources, filter_tickers=None):
    """
    sources: list of (folder_path, broker_name) tuples.
    """
    all_txs = []
    all_pdfs = []
    pdf_counts = {}
    for folder, broker in sources:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            parser = extract_fintual_transactions if broker == "Fintual" else extract_transactions
            txs = parser(pdf, broker)
            pdf_counts[pdf.name] = len(txs)
            all_txs.extend(txs)
            all_pdfs.append(pdf)

    by_ticker = defaultdict(list)
    for tx in all_txs:
        by_ticker[tx["ticker"]].append(tx)

    for ticker in by_ticker:
        by_ticker[ticker].sort(key=lambda x: (x["date"][6:], x["date"][0:2], x["date"][3:5]))

    tickers_to_show = sorted(by_ticker.keys())
    if filter_tickers:
        tickers_to_show = [t.upper() for t in filter_tickers if t.upper() in by_ticker]

    return all_pdfs, all_txs, by_ticker, tickers_to_show, pdf_counts


def main():
    parser = argparse.ArgumentParser(description="Parser de estados de cuenta Racional/Fintual")
    parser.add_argument("folder", nargs="?", default=str(RACIONAL_DAILY_FOLDER), help="Carpeta principal con los PDFs")
    parser.add_argument("--ticker", nargs="*", help="Filtrar por ticker(s)")
    parser.add_argument("--no-serve", action="store_true", help="Imprimir en consola en vez de servir HTML")
    parser.add_argument("--port", type=int, default=5050, help="Puerto para el servidor HTML (default: 5050)")
    args = parser.parse_args()

    primary_folder = Path(args.folder).expanduser()
    if not primary_folder.is_dir():
        print(f"[!] No existe la carpeta: {primary_folder}")
        sys.exit(1)

    sources = [(primary_folder, "Racional")]
    if FINTUAL_MONTHLY_FOLDER.is_dir():
        sources.append((FINTUAL_MONTHLY_FOLDER, "Fintual"))

    acat_monthly_sources = [(RACIONAL_MONTHLY_FOLDER, "Racional")]
    if FINTUAL_MONTHLY_FOLDER.is_dir():
        acat_monthly_sources.append((FINTUAL_MONTHLY_FOLDER, "Fintual"))

    pdfs, all_txs, by_ticker, tickers_to_show, pdf_counts = load_data(sources, args.ticker)
    acat_set, acat_transfers = extract_acat_tickers(acat_monthly_sources)

    if not pdfs:
        print(f"[!] No se encontraron PDFs en {primary_folder}")
        sys.exit(1)

    if args.no_serve:
        print(f"\nLeyendo {len(pdfs)} PDFs...\n")
        for name, count in pdf_counts.items():
            print(f"  {name:50s}  ->  {count} transacciones")
        for ticker in tickers_to_show:
            rows = compute_avg(by_ticker[ticker])
            print_ticker(ticker, rows)
        print(f"\n{'-'*70}")
        print(f"  Total tickers: {len(by_ticker)}")
        if not args.ticker:
            print(f"  Tickers: {', '.join(sorted(by_ticker.keys()))}")
        return

    # ── Flask server ──────────────────────────────────────────────────────────
    app = Flask(__name__)

    @app.route("/")
    def index():
        ticker_rows = [(t, compute_avg(by_ticker[t])) for t in tickers_to_show]
        all_acat       = sorted(acat_set)
        acat_tickers   = [
            (t, compute_avg(by_ticker[t]) if t in by_ticker else [
                {"date": tr["date"], "time": "—", "side": "acat",
                 "qty": tr["qty"], "price": 0.0, "amount": 0.0,
                 "shares_after": tr["qty"], "avg_after": 0.0, "capital_after": 0.0,
                 "broker": tr.get("broker", "Racional")}
                for tr in acat_transfers.get(t, [])
            ])
            for t in all_acat
        ]
        open_tickers   = [(t, rows) for t, rows in ticker_rows if t not in acat_set and rows[-1]["shares_after"] > 0.000001]
        closed_tickers = [(t, rows) for t, rows in ticker_rows if t not in acat_set and rows[-1]["shares_after"] <= 0.000001]
        closed_total   = sum(sum(r["amount"] for r in rows) for _, rows in closed_tickers)
        acat_total     = sum(sum(r["amount"] for r in rows) for _, rows in acat_tickers)
        return render_template_string(
            HTML_TEMPLATE,
            open_tickers=open_tickers,
            closed_tickers=closed_tickers,
            acat_tickers=acat_tickers,
            closed_total=closed_total,
            acat_total=acat_total,
            pdf_count=len(pdfs),
            total_txs=len(all_txs),
            ticker_count=len(tickers_to_show),
            open_count=len(open_tickers),
            closed_count=len(closed_tickers),
            acat_count=len(acat_tickers),
        )

    url = f"http://localhost:{args.port}"
    print(f"\nServidor iniciado en {url}  (Ctrl+C para detener)\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
