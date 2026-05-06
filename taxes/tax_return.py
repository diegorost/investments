"""
tax_return.py
Reads Racional/DriveWealth monthly PDF statements from a folder and prints
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


# ── regex para líneas de transacción DriveWealth/Racional ────────────────────
TX_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+"              # Trade Date
    r"\d{2}/\d{2}/\d{4}\s+"                # Settle Date
    r"USD\s+"                               # Currency
    r"(BUY|SELL)\s+"                        # Activity Type
    r"([A-Z]+(?:\.[A-Z]+)?)\s+-\s+"        # Ticker symbol
    r".+?(?:Principal|Agency)\.\s+"         # Description (lazy) + exec type
    r"-?([\d,]+(?:\.[\d]+)?)\s+"           # Quantity
    r"([\d,]+(?:\.[\d]+)?)\s+"             # Price
    r"\(?([\d,]+(?:\.[\d]+)?)\)?"         # Amount
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Tax Return - Racional</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; padding: 2rem; }
  h1 { font-size: 1.4rem; font-weight: 600; color: #f8fafc; margin-bottom: 0.25rem; }
  .subtitle { color: #64748b; font-size: 0.85rem; margin-bottom: 2rem; }
  .summary { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
  .stat { background: #1e2130; border: 1px solid #2d3348; border-radius: 8px; padding: 0.75rem 1.25rem; }
  .stat-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-value { font-size: 1.1rem; font-weight: 600; color: #f8fafc; margin-top: 0.2rem; }
  .ticker-section { margin-bottom: 2rem; }
  .ticker-header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 0.5rem; }
  .ticker-name { font-size: 1.1rem; font-weight: 700; color: #818cf8; }
  .ticker-summary { font-size: 0.82rem; color: #94a3b8; }
  .position-open  { color: #34d399; }
  .position-closed { color: #64748b; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  th { text-align: right; padding: 0.4rem 0.75rem; color: #64748b; font-weight: 500;
       border-bottom: 1px solid #2d3348; white-space: nowrap; }
  th:first-child, th:nth-child(2) { text-align: left; }
  td { text-align: right; padding: 0.35rem 0.75rem; border-bottom: 1px solid #1e2130; white-space: nowrap; }
  td:first-child, td:nth-child(2) { text-align: left; }
  tr:last-child td { border-bottom: none; }
  .buy  { color: #34d399; }
  .sell { color: #f87171; }
  .ticker-card { background: #1e2130; border: 1px solid #2d3348; border-radius: 10px;
                 padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
</style>
</head>
<body>
<h1>Tax Return &mdash; Racional / DriveWealth</h1>
<p class="subtitle">{{ pdf_count }} statements &bull; {{ total_txs }} transactions &bull; {{ ticker_count }} tickers</p>

<div class="summary">
  <div class="stat"><div class="stat-label">Open positions</div><div class="stat-value">{{ open_count }}</div></div>
  <div class="stat"><div class="stat-label">Closed positions</div><div class="stat-value">{{ closed_count }}</div></div>
</div>

{% for ticker, rows in tickers %}
<div class="ticker-card">
  <div class="ticker-header">
    <span class="ticker-name">{{ ticker }}</span>
    {% set last = rows[-1] %}
    {% set buy_shares = rows | selectattr("side", "equalto", "buy") | sum(attribute="qty") %}
    {% if last.shares_after > 0.000001 %}
      <span class="ticker-summary position-open">
        {{ "%.8f"|format(last.shares_after) }} shares &bull; suma {{ "%.8f"|format(buy_shares) }} &bull; capital invertido ${{ "%.2f"|format(last.capital_after) }} &bull; avg ${{ "%.4f"|format(last.avg_after) }}
      </span>
    {% else %}
      <span class="ticker-summary position-closed">closed &bull; suma {{ "%.8f"|format(buy_shares) }} &bull; capital invertido ${{ "%.2f"|format(last.capital_after) }}</span>
    {% endif %}
  </div>
  <table>
    <thead>
      <tr>
        <th>Date</th><th>Side</th>
        <th>Shares</th><th>Price</th><th>Capital invertido</th>
        <th>Acc. Shares</th><th>Avg Cost</th>
      </tr>
    </thead>
    <tbody>
    {% for r in rows %}
      <tr>
        <td>{{ r.date }}</td>
        <td class="{{ r.side }}">{{ r.side }}</td>
        <td class="{{ r.side }}">{{ '+' if r.side == 'buy' else '-' }}{{ "%.8f"|format(r.qty) }}</td>
        <td>${{ "%.4f"|format(r.price) }}</td>
        <td>${{ "%.2f"|format(r.capital_after) }}</td>
        <td>{{ "%.8f"|format(r.shares_after) }}</td>
        <td>${{ "%.4f"|format(r.avg_after) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endfor %}
</body>
</html>
"""


def parse_number(s):
    return float(s.replace(",", "").replace("$", ""))


def extract_transactions(pdf_path):
    txs = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

        lines = full_text.splitlines()
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Trade Date") or line.startswith("Transaction"):
                continue
            clean_lines.append(line)

        merged = []
        for line in clean_lines:
            if re.match(r"\d{2}/\d{2}/\d{4}", line):
                merged.append(line)
            elif merged:
                merged[-1] += " " + line

        for line in merged:
            if " BUY " not in line and " SELL " not in line:
                continue
            m = TX_RE.search(line)
            if m:
                date, side, ticker, qty_s, price_s, amount_s = m.groups()
                txs.append({
                    "date":   date,
                    "side":   side.lower(),
                    "ticker": ticker,
                    "qty":    parse_number(qty_s),
                    "price":  parse_number(price_s),
                    "amount": parse_number(amount_s),
                    "source": pdf_path.name,
                })
    except Exception as e:
        print(f"  [!] Error leyendo {pdf_path.name}: {e}")
    return txs


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


def load_data(folder, filter_tickers=None):
    pdfs = sorted(folder.glob("*.pdf"))
    all_txs = []
    pdf_counts = {}
    for pdf in pdfs:
        txs = extract_transactions(pdf)
        pdf_counts[pdf.name] = len(txs)
        all_txs.extend(txs)

    by_ticker = defaultdict(list)
    for tx in all_txs:
        by_ticker[tx["ticker"]].append(tx)

    for ticker in by_ticker:
        by_ticker[ticker].sort(key=lambda x: (x["date"][6:], x["date"][0:2], x["date"][3:5]))

    tickers_to_show = sorted(by_ticker.keys())
    if filter_tickers:
        tickers_to_show = [t.upper() for t in filter_tickers if t.upper() in by_ticker]

    return pdfs, all_txs, by_ticker, tickers_to_show, pdf_counts


def main():
    default_folder = Path(__file__).parent / "Racional"
    parser = argparse.ArgumentParser(description="Parser de estados de cuenta Racional/DriveWealth")
    parser.add_argument("folder", nargs="?", default=str(default_folder), help="Carpeta con los PDFs (default: ./Racional/)")
    parser.add_argument("--ticker", nargs="*", help="Filtrar por ticker(s)")
    parser.add_argument("--no-serve", action="store_true", help="Imprimir en consola en vez de servir HTML")
    parser.add_argument("--port", type=int, default=5050, help="Puerto para el servidor HTML (default: 5050)")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[!] No existe la carpeta: {folder}")
        sys.exit(1)

    pdfs, all_txs, by_ticker, tickers_to_show, pdf_counts = load_data(folder, args.ticker)

    if not pdfs:
        print(f"[!] No se encontraron PDFs en {folder}")
        sys.exit(1)

    if args.no_serve:
        print(f"\nLeyendo {len(pdfs)} PDFs desde {folder}...\n")
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
        last_rows = [rows[-1] for _, rows in ticker_rows]
        open_count  = sum(1 for r in last_rows if r["shares_after"] > 0.000001)
        closed_count = len(last_rows) - open_count
        return render_template_string(
            HTML_TEMPLATE,
            tickers=ticker_rows,
            pdf_count=len(pdfs),
            total_txs=len(all_txs),
            ticker_count=len(tickers_to_show),
            open_count=open_count,
            closed_count=closed_count,
        )

    url = f"http://localhost:{args.port}"
    print(f"\nServidor iniciado en {url}  (Ctrl+C para detener)\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
