"""
vector_boletas.py
Reads Vector Capital PDF boletas from ./vector/ and displays purchases with
their USD and CLP amounts.

Usage:
    python vector_boletas.py                         # serves HTML on :5051
    python vector_boletas.py ./vector/ --no-serve    # plain text output
    python vector_boletas.py --dump-text             # print extracted PDF text
"""

import argparse
import unicodedata
import re
import sys
import threading
import webbrowser
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Instalando pdfplumber...")
    import subprocess

    subprocess.run([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"], check=False)
    import pdfplumber

try:
    from flask import Flask, render_template_string
except ImportError:
    Flask = None
    render_template_string = None


MONEY_RE = re.compile(r"(?:USD|US\$|\$)?\s*-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?")
DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
DOC_RE = re.compile(r"(?:N[ro.\s]*|Numero\s+)(?:boleta|factura|documento)?\s*:?\s*(\d+)", re.I)

FIELD_PATTERNS = {
    "side": [
        r"\b(Compra|Venta)\b",
        r"Tipo\s+Operacion\s*:?\s*(Compra|Venta)",
        r"Operacion\s*:?\s*(Compra|Venta)",
    ],
    "ticker": [
        r"Nemo(?:tecnico)?\s*:?\s*([A-Z0-9.\-]+)",
        r"Instrumento\s*:?\s*([A-Z0-9.\-]+)",
        r"Codigo\s*:?\s*([A-Z0-9.\-]+)",
        r"Ticker\s*:?\s*([A-Z0-9.\-]+)",
    ],
    "quantity": [
        r"Unidades\s*:?\s*([0-9.,]+)",
        r"Acciones\s*:?\s*([0-9.,]+)",
    ],
    "price_usd": [
        r"Precio\s*/\s*U\s*:?\s*(?:USD|US\$|\$)?\s*([0-9.,]+)",
        r"Precio\s*(?:Unitario|/U)?\s*(?:USD|US\$|Dolares?)?\s*:?\s*(?:USD|US\$|\$)?\s*([0-9.,]+)",
        r"(?:USD|US\$)\s*/?\s*(?:Accion|Unidad)\s*:?\s*([0-9.,]+)",
    ],
    "amount_usd": [
        r"Cantidad\s*:?\s*(?:USD|US\$|\$)?\s*([0-9.,]+)",
        r"(?:Monto|Total|Neto|Valor\s+Transado)\s*(?:USD|US\$|Dolares?)\s*:?\s*(?:USD|US\$|\$)?\s*([0-9.,]+)",
        r"(?:USD|US\$)\s*(?:Monto|Total|Neto|Valor\s+Transado)\s*:?\s*(?:USD|US\$|\$)?\s*([0-9.,]+)",
    ],
    "amount_clp": [
        r"(?:Monto|Total|Neto|Valor\s+Transado|Total\s+a\s+Pagar)\s*(?:CLP|Pesos?)\s*:?\s*\$?\s*([0-9.,]+)",
        r"(?:CLP|Pesos?)\s*(?:Monto|Total|Neto|Valor\s+Transado|Total\s+a\s+Pagar)\s*:?\s*\$?\s*([0-9.,]+)",
        r"Total\s+(?:Factura|Boleta)\s*:?\s*\$?\s*([0-9.,]+)",
    ],
    "fx_rate": [
        r"Tipo\s+de\s+Cambio\s*:?\s*\$?\s*([0-9.,]+)",
        r"Dolar\s*(?:Observado|Referencia)?\s*:?\s*\$?\s*([0-9.,]+)",
        r"TC\s*:?\s*\$?\s*([0-9.,]+)",
    ],
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Vector Boletas</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: #101418; color: #e7edf3; }
  main { padding: 28px; max-width: 1280px; margin: 0 auto; }
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
  h1 { margin: 0 0 6px; font-size: 24px; font-weight: 650; }
  .subtitle { color: #8fa1b2; }
  button { border: 1px solid #3b4b5c; background: #223040; color: #e7edf3; border-radius: 8px; padding: 9px 14px; cursor: pointer; font-weight: 600; }
  button:hover { background: #2b3b4d; }
  .stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 22px; }
  .stat { background: #182029; border: 1px solid #293542; border-radius: 8px; padding: 12px 16px; min-width: 150px; }
  .label { color: #8fa1b2; font-size: 12px; text-transform: uppercase; }
  .value { margin-top: 4px; font-size: 18px; font-weight: 650; }
  table { width: 100%; border-collapse: collapse; background: #182029; border: 1px solid #293542; border-radius: 8px; overflow: hidden; }
  th, td { padding: 10px 12px; border-bottom: 1px solid #293542; white-space: nowrap; text-align: right; }
  th { color: #8fa1b2; font-size: 12px; font-weight: 600; text-transform: uppercase; }
  td:first-child, td:nth-child(2), th:first-child, th:nth-child(2) { text-align: left; }
  tr:last-child td { border-bottom: 0; }
  .warn { color: #f6c177; }
  .muted { color: #8fa1b2; }
</style>
</head>
<body>
<main>
  <div class="topbar">
    <div>
      <h1>Vector Boletas</h1>
      <div class="subtitle">{{ pdf_count }} PDFs desde {{ folder }}</div>
    </div>
    <form method="get" action="/">
      <button type="submit">Rescan</button>
    </form>
  </div>
  <div class="stats">
    <div class="stat"><div class="label">Compras</div><div class="value">{{ purchase_count }}</div></div>
    <div class="stat"><div class="label">Total USD</div><div class="value">{{ fmt_usd(total_usd) }}</div></div>
    <div class="stat"><div class="label">Total CLP</div><div class="value">{{ fmt_clp(total_clp) }}</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>PDF</th><th>Fecha</th><th>Tipo</th>
        <th>Precio /U</th><th>Cantidad USD</th><th>TC</th><th>Monto CLP</th>
      </tr>
    </thead>
    <tbody>
    {% for row in rows %}
      <tr>
        <td>{{ row.source }}</td>
        <td>{{ row.date or "" }}</td>
        <td class="{{ '' if row.side == 'Compra' else 'muted' }}">{{ row.side or "" }}</td>
        <td>{{ fmt_usd(row.price_usd) }}</td>
        <td>{{ fmt_usd(row.amount_usd) }}</td>
        <td>{{ fmt_fx(row.fx_rate) }}</td>
        <td>{{ fmt_clp(row.amount_clp) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</main>
</body>
</html>
"""


def strip_accents(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def parse_number(value):
    if value is None:
        return None
    value = str(value).strip().replace(" ", "").replace("$", "").replace("USD", "").replace("US", "")
    value = value.replace("\u00a0", "")
    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts[-1]) in (1, 2):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 or len(parts[-1]) == 3:
            value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def money_after_label(text, label_words, currency_words):
    labels = "|".join(re.escape(word) for word in label_words)
    currencies = "|".join(re.escape(word) for word in currency_words)
    pattern = re.compile(
        rf"(?:{labels}).{{0,45}}(?:{currencies}).{{0,20}}({MONEY_RE.pattern})",
        re.I | re.S,
    )
    match = pattern.search(text)
    return parse_number(match.group(1)) if match else None


def first_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip()
    return None


def extract_text(pdf_path):
    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return "\n".join(chunks)


def extract_tables(pdf_path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    clean = [str(cell or "").strip() for cell in row]
                    if any(clean):
                        rows.append(clean)
    return rows


def normalize_cell(value):
    value = strip_accents(str(value or "")).upper()
    return re.sub(r"[^A-Z0-9/$]+", " ", value).strip()


def table_field_for_label(label):
    label = normalize_cell(label)
    if not label:
        return None
    if "PRECIO" in label and "/U" in label:
        return "price_usd"
    if label == "CANTIDAD" or " CANTIDAD " in f" {label} ":
        return "amount_usd"
    if "MONTO" in label and ("PESO" in label or "CLP" in label or "$" in label):
        return "amount_clp"
    if "TOTAL" in label and ("PAGAR" in label or "CLP" in label or "PESO" in label):
        return "amount_clp"
    if "TIPO CAMBIO" in label or label == "TC":
        return "fx_rate"
    if "UNIDADES" in label or "ACCIONES" in label:
        return "quantity"
    if "NEMO" in label or "INSTRUMENTO" in label:
        return "ticker"
    return None


def first_number_in_cell(value):
    match = MONEY_RE.search(str(value or ""))
    return parse_number(match.group(0)) if match else None


def cell_value_to_field(field, value):
    if field in {"ticker", "side"}:
        value = str(value or "").strip()
        return value or None
    return first_number_in_cell(value)


def apply_table_field(parsed, field, value):
    parsed_value = cell_value_to_field(field, value)
    if parsed_value is not None:
        parsed.setdefault(field, parsed_value)


def fields_in_header_line(line):
    checks = [
        (r"\bCANTIDAD\b", "amount_usd"),
        (r"\bPRECIO\s*/\s*U\b", "price_usd"),
        (r"\b(?:MONTO|TOTAL).*(?:CLP|PESOS?)\b", "amount_clp"),
        (r"\b(?:TIPO\s+CAMBIO|TC)\b", "fx_rate"),
        (r"\b(?:UNIDADES|ACCIONES)\b", "quantity"),
    ]
    found = []
    normalized = strip_accents(line)
    for pattern, field in checks:
        match = re.search(pattern, normalized, re.I)
        if match:
            found.append((match.start(), field))
    return [field for _, field in sorted(found)]


def parse_from_tables(table_rows):
    parsed = {}
    for row_index, row in enumerate(table_rows):
        joined = " ".join(row)
        normalized = strip_accents(joined)
        if not parsed.get("side") and re.search(r"\bCompra\b", normalized, re.I):
            parsed["side"] = "Compra"
        if not parsed.get("side") and re.search(r"\bVenta\b", normalized, re.I):
            parsed["side"] = "Venta"
        if not parsed.get("ticker"):
            match = re.search(r"\b[A-Z]{2,6}(?:\.[A-Z])?\b", joined)
            if match and match.group(0) not in {"USD", "CLP", "IVA"}:
                parsed["ticker"] = match.group(0)
        for col_index, cell in enumerate(row):
            field = table_field_for_label(cell)
            if not field:
                continue

            right_cells = row[col_index + 1 :]
            for candidate in right_cells:
                apply_table_field(parsed, field, candidate)
                if field in parsed:
                    break

            if field not in parsed and row_index + 1 < len(table_rows):
                below_row = table_rows[row_index + 1]
                if col_index < len(below_row):
                    apply_table_field(parsed, field, below_row[col_index])

        header_fields = [table_field_for_label(cell) for cell in row]
        if any(header_fields) and row_index + 1 < len(table_rows):
            value_row = table_rows[row_index + 1]
            for col_index, field in enumerate(header_fields):
                if field and col_index < len(value_row):
                    apply_table_field(parsed, field, value_row[col_index])

        numbers = [parse_number(item) for item in row]
        numbers = [number for number in numbers if number is not None]
        if "USD" in normalized.upper() and numbers:
            parsed.setdefault("amount_usd", numbers[-1])
            if len(numbers) >= 2:
                parsed.setdefault("price_usd", numbers[-2])
        if ("CLP" in normalized.upper() or "PESO" in normalized.upper()) and numbers:
            parsed.setdefault("amount_clp", numbers[-1])
    return parsed


def parse_from_lines(text):
    parsed = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        header_fields = fields_in_header_line(line)
        if len(header_fields) >= 2:
            values = []
            for candidate in lines[index + 1 : index + 4]:
                values.extend(match.group(0) for match in MONEY_RE.finditer(candidate))
                if len(values) >= len(header_fields):
                    break
            for field, value in zip(header_fields, values):
                apply_table_field(parsed, field, value)

        field = table_field_for_label(line)
        if not field:
            continue

        inline_value = re.sub(re.escape(line), "", line, count=1).strip()
        candidates = [line]
        if inline_value:
            candidates.append(inline_value)
        candidates.extend(lines[index + 1 : index + 3])
        for candidate in candidates:
            apply_table_field(parsed, field, candidate)
            if field in parsed:
                break
    return parsed


def parse_boleta(pdf_path):
    raw_text = extract_text(pdf_path)
    text = strip_accents(raw_text)
    compact = re.sub(r"[ \t]+", " ", text)
    table_guess = parse_from_tables(extract_tables(pdf_path))
    line_guess = parse_from_lines(text)

    date = first_match(compact, [r"Fecha\s*(?:Operacion|Transaccion|Emision)?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"])
    if not date:
        match = DATE_RE.search(compact)
        date = match.group(1) if match else None

    row = {
        "source": pdf_path.name,
        "date": date,
        "document": first_match(compact, [DOC_RE.pattern]),
        "side": first_match(compact, FIELD_PATTERNS["side"]) or table_guess.get("side") or line_guess.get("side"),
        "ticker": first_match(compact, FIELD_PATTERNS["ticker"]) or table_guess.get("ticker") or line_guess.get("ticker"),
        "quantity": parse_number(first_match(compact, FIELD_PATTERNS["quantity"])),
        "price_usd": parse_number(first_match(compact, FIELD_PATTERNS["price_usd"])),
        "amount_usd": parse_number(first_match(compact, FIELD_PATTERNS["amount_usd"])),
        "fx_rate": parse_number(first_match(compact, FIELD_PATTERNS["fx_rate"])),
        "amount_clp": parse_number(first_match(compact, FIELD_PATTERNS["amount_clp"])),
        "raw_text": raw_text,
    }

    for key in ("quantity", "price_usd", "amount_usd", "fx_rate", "amount_clp"):
        if row[key] is None and table_guess.get(key) is not None:
            row[key] = table_guess[key]
        if row[key] is None and line_guess.get(key) is not None:
            row[key] = line_guess[key]

    if row["amount_usd"] is None:
        row["amount_usd"] = money_after_label(
            compact,
            ["Monto", "Total", "Neto", "Valor Transado", "Valor Operacion"],
            ["USD", "US$", "Dolares"],
        )
    if row["amount_clp"] is None:
        row["amount_clp"] = money_after_label(
            compact,
            ["Monto", "Total", "Neto", "Valor Transado", "Total a Pagar"],
            ["CLP", "Pesos"],
        )
    if row["fx_rate"] is None and row["amount_usd"] and row["amount_clp"]:
        row["fx_rate"] = row["amount_clp"] / row["amount_usd"]
    return row


def load_boletas(folder):
    pdfs = sorted(folder.glob("*.pdf"))
    rows = [parse_boleta(pdf) for pdf in pdfs]
    rows.sort(key=lambda row: (date_key(row["date"]), row["source"]))
    return pdfs, rows


def date_key(value):
    if not value:
        return "99999999"
    parts = re.split(r"[/-]", value)
    if len(parts) != 3:
        return value
    day, month, year = parts
    if len(year) == 2:
        year = "20" + year
    return f"{year.zfill(4)}{month.zfill(2)}{day.zfill(2)}"


def fmt_qty(value):
    return "" if value is None else f"{value:,.6f}".rstrip("0").rstrip(".")


def fmt_usd(value):
    return "" if value is None else f"US$ {value:,.2f}"


def fmt_clp(value):
    return "" if value is None else f"$ {value:,.0f}"


def fmt_fx(value):
    return "" if value is None else f"{value:,.10f}".rstrip("0").rstrip(".")


def print_rows(rows, pdf_count, folder):
    purchases = [row for row in rows if (row["side"] or "").lower() == "compra"]
    total_usd = sum(row["amount_usd"] or 0 for row in purchases)
    total_clp = sum(row["amount_clp"] or 0 for row in purchases)
    print(f"\nLeyendo {pdf_count} PDFs desde {folder}")
    print(f"Compras: {len(purchases)}  |  Total USD: {fmt_usd(total_usd)}  |  Total CLP: {fmt_clp(total_clp)}\n")
    print(
        f"{'PDF':<30} {'Fecha':<10} {'Tipo':<8} "
        f"{'Precio /U':>14} {'Cantidad USD':>14} {'TC':>16} {'Monto CLP':>14}"
    )
    print("-" * 142)
    for row in rows:
        print(
            f"{row['source']:<30} {(row['date'] or ''):<10} "
            f"{(row['side'] or ''):<8} "
            f"{fmt_usd(row['price_usd']):>14} {fmt_usd(row['amount_usd']):>14} "
            f"{fmt_fx(row['fx_rate']):>16} {fmt_clp(row['amount_clp']):>14}"
        )


def main():
    default_folder = Path(__file__).parent / "vector"
    parser = argparse.ArgumentParser(description="Parser de boletas Vector Capital")
    parser.add_argument("folder", nargs="?", default=str(default_folder), help="Carpeta con PDFs (default: ./vector/)")
    parser.add_argument("--no-serve", action="store_true", help="Imprimir en consola en vez de servir HTML")
    parser.add_argument("--dump-text", action="store_true", help="Imprimir el texto extraido de cada PDF")
    parser.add_argument("--port", type=int, default=5051, help="Puerto para el servidor HTML (default: 5051)")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[!] No existe la carpeta: {folder}")
        sys.exit(1)

    if args.dump_text:
        pdfs, rows = load_boletas(folder)
        if not pdfs:
            print(f"[!] No se encontraron PDFs en {folder}")
            sys.exit(1)
        for row in rows:
            print(f"\n{'=' * 90}\n{row['source']}\n{'=' * 90}")
            print(row["raw_text"])
        return

    if args.no_serve or Flask is None:
        pdfs, rows = load_boletas(folder)
        if not pdfs:
            print(f"[!] No se encontraron PDFs en {folder}")
            sys.exit(1)
        if Flask is None and not args.no_serve:
            print("[!] Flask no esta instalado. Mostrando salida de consola.")
        print_rows(rows, len(pdfs), folder)
        return

    app = Flask(__name__)

    @app.route("/")
    def index():
        pdfs, rows = load_boletas(folder)
        purchases = [row for row in rows if (row["side"] or "").lower() == "compra"]
        return render_template_string(
            HTML_TEMPLATE,
            rows=rows,
            folder=folder,
            pdf_count=len(pdfs),
            purchase_count=len(purchases),
            total_usd=sum(row["amount_usd"] or 0 for row in purchases),
            total_clp=sum(row["amount_clp"] or 0 for row in purchases),
            fmt_qty=fmt_qty,
            fmt_usd=fmt_usd,
            fmt_clp=fmt_clp,
            fmt_fx=fmt_fx,
        )

    url = f"http://localhost:{args.port}"
    print(f"\nServidor iniciado en {url}  (Ctrl+C para detener)\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
