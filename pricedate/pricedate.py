import json
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import yfinance as yf

PORT = 5050

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Price Lookup</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e0e0e0; display: flex; justify-content: center; align-items: flex-start; padding: 60px 20px; min-height: 100vh; }
  .card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 12px; padding: 36px 40px; width: 580px; }
  h1 { font-size: 1.3rem; font-weight: 600; margin-bottom: 28px; color: #fff; }
  label { display: block; font-size: 0.78rem; color: #888; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }
  input { width: 100%; background: #0f1117; border: 1px solid #2a2d3a; border-radius: 7px; color: #e0e0e0; font-size: 1rem; padding: 10px 14px; outline: none; transition: border-color .2s; }
  input:focus { border-color: #4f8ef7; }
  .row { margin-bottom: 18px; }
  .dates { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  button { width: 100%; margin-top: 8px; padding: 12px; background: #4f8ef7; border: none; border-radius: 7px; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background .2s; }
  button:hover { background: #3a7de8; }
  button:disabled { background: #2a3a5a; cursor: default; }
  #result { margin-top: 24px; display: none; }
  table { width: 100%; border-collapse: collapse; }
  thead th { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: .06em; padding: 0 0 10px; text-align: left; border-bottom: 1px solid #2a2d3a; }
  thead th:not(:first-child) { text-align: right; }
  tbody td { padding: 11px 0; border-bottom: 1px solid #1e2130; font-size: 0.95rem; }
  tbody tr:last-child td { border-bottom: none; }
  tbody td:not(:first-child) { text-align: right; }
  .ticker-cell { font-weight: 700; color: #fff; }
  .pos { color: #4ade80; font-weight: 700; }
  .neg { color: #f87171; font-weight: 700; }
  #error { margin-top: 18px; color: #f87171; font-size: 0.88rem; display: none; background: #2a1a1a; border-radius: 7px; padding: 10px 14px; }
  #spinner { margin-top: 14px; color: #888; font-size: 0.85rem; display: none; text-align: center; }
  .hint { font-size: 0.75rem; color: #555; margin-top: 5px; }
</style>
</head>
<body>
<div class="card">
  <h1>Price Lookup</h1>
  <div class="row">
    <label for="ticker">Ticker(s)</label>
    <input id="ticker" type="text" placeholder="AAPL, MSFT, TSLA" autocomplete="off">
    <p class="hint">Separate multiple tickers with commas</p>
  </div>
  <div class="dates">
    <div class="row">
      <label for="entry">Entry</label>
      <input id="entry" type="date">
    </div>
    <div class="row">
      <label for="exit">Exit</label>
      <input id="exit" type="date">
    </div>
  </div>
  <button id="btn" onclick="lookup()">Look up</button>
  <div id="spinner">Fetching prices...</div>
  <div id="error"></div>
  <div id="result">
    <table>
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Entry</th>
          <th>Exit</th>
          <th>Return</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>
<script>
  async function lookup() {
    const raw    = document.getElementById('ticker').value.trim().toUpperCase();
    const entry  = document.getElementById('entry').value;
    const exit_  = document.getElementById('exit').value;
    const btn    = document.getElementById('btn');
    const errEl  = document.getElementById('error');
    const resEl  = document.getElementById('result');
    const spin   = document.getElementById('spinner');
    const tbody  = document.getElementById('tbody');

    errEl.style.display = 'none';
    resEl.style.display = 'none';
    tbody.innerHTML = '';

    if (!raw || !entry || !exit_) {
      errEl.textContent = 'Fill in all fields.';
      errEl.style.display = 'block';
      return;
    }
    if (entry > exit_) {
      errEl.textContent = 'Entry date must be before exit date.';
      errEl.style.display = 'block';
      return;
    }

    btn.disabled = true;
    spin.style.display = 'block';

    try {
      const r = await fetch(`/price?ticker=${encodeURIComponent(raw)}&entry=${entry}&exit=${exit_}`);
      const d = await r.json();
      if (!d.ok) throw new Error(d.error);

      for (const row of d.results) {
        const tr  = document.createElement('tr');
        const pct = row.return_pct;
        const cls = pct >= 0 ? 'pos' : 'neg';
        tr.innerHTML = `
          <td class="ticker-cell">${row.ticker}</td>
          <td>$${row.entry_price.toFixed(2)}<br><small style="color:#555">${row.entry_date}</small></td>
          <td>$${row.exit_price.toFixed(2)}<br><small style="color:#555">${row.exit_date}</small></td>
          <td class="${cls}">${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%</td>`;
        tbody.appendChild(tr);
      }
      resEl.style.display = 'block';
    } catch (e) {
      errEl.textContent   = e.message;
      errEl.style.display = 'block';
    } finally {
      btn.disabled       = false;
      spin.style.display = 'none';
    }
  }

  document.addEventListener('keydown', e => { if (e.key === 'Enter') lookup(); });
</script>
</body>
</html>"""


def get_price(ticker, date_str):
    d   = datetime.strptime(date_str, "%Y-%m-%d")
    end = (d + timedelta(days=7)).strftime("%Y-%m-%d")
    df  = yf.download(ticker, start=date_str, end=end, progress=False)
    if df.empty:
        raise ValueError(f"No data for {ticker} on or after {date_str}")
    high = float(df["High"].iloc[0].item())
    low  = float(df["Low"].iloc[0].item())
    return (high + low) / 2, df.index[0].strftime("%Y-%m-%d")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/price":
            qs      = parse_qs(parsed.query)
            raw     = qs.get("ticker", [""])[0].strip().upper()
            entry   = qs.get("entry",  [""])[0].strip()
            exit_   = qs.get("exit",   [""])[0].strip()
            tickers = [t.strip() for t in raw.split(",") if t.strip()]
            try:
                if not tickers or not entry or not exit_:
                    raise ValueError("ticker, entry and exit are required")
                results = []
                for t in tickers:
                    ep, ed = get_price(t, entry)
                    xp, xd = get_price(t, exit_)
                    results.append({
                        "ticker":      t,
                        "entry_price": ep, "entry_date": ed,
                        "exit_price":  xp, "exit_date":  xd,
                        "return_pct":  (xp / ep - 1) * 100,
                    })
                payload = json.dumps({"ok": True, "results": results})
                self.send_response(200)
            except Exception as e:
                payload = json.dumps({"ok": False, "error": str(e)})
                self.send_response(400)
            body = payload.encode("utf-8")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url    = f"http://127.0.0.1:{PORT}"
    print(f"Price Lookup running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
