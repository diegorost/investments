"""
Miners Uplift Dashboard - webapp (Flask)
=========================================
Serves miners_uplift.html and provides a background price refresh endpoint.

Local:
    python app.py

Railway:
    Start command: gunicorn app:app
"""

import os
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, Response, jsonify, redirect

# Import price-update logic from main.py
import sys
sys.path.insert(0, str(Path(__file__).parent))
from main import (
    GOLD_HTML, SILVER_HTML, OUTPUT_HTML,
    GOLD_TICKER_MAP, SILVER_TICKER_MAP,
    GOLD_STATIC, SILVER_INVESTING_COM,
    GOLD_ETF_CLASSES, SILVER_ETF_CLASSES,
    update_html_file, generate_merged_html,
)

app = Flask(__name__)

# ── Midnight auto-refresh ──────────────────────────────────────────────────────

def _seconds_until_midnight():
    now  = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - now).total_seconds()

def _midnight_scheduler():
    while True:
        secs = _seconds_until_midnight()
        print(f'Auto-refresh scheduled in {secs/3600:.1f}h (at midnight)')
        time.sleep(secs)
        print('Midnight auto-refresh triggered')
        t = threading.Thread(target=_do_update, args=('all',), daemon=True)
        t.start()

# ── Update state ───────────────────────────────────────────────────────────────

_update_lock   = threading.Lock()
_update_status = {
    'running':      False,
    'last_updated': None,
    'last_error':   None,
    'progress':     '',
}

def _do_update(mode='all'):
    """Run price update in background thread."""
    with _update_lock:
        if _update_status['running']:
            return
        _update_status['running']    = True
        _update_status['last_error'] = None
        _update_status['progress']   = 'Starting...'

    try:
        gold_html   = GOLD_HTML.read_text(encoding='utf-8')
        silver_html = SILVER_HTML.read_text(encoding='utf-8')

        gold_patterns = [
            r'const ringData = (\[[\s\S]*?\]);',
            r'const auauData = (\[[\s\S]*?\]);',
            r'const gdxData  = (\[[\s\S]*?\]);',
            r'const gdxjData = (\[[\s\S]*?\]);',
        ]
        silver_patterns = [
            r'const slvpData = (\[[\s\S]*?\]);',
            r'const silData  = (\[[\s\S]*?\]);',
            r'const siljData = (\[[\s\S]*?\]);',
        ]

        if mode == 'etf':
            # Fast update: only the 7 ETF hero sections, skip all holdings
            _update_status['progress'] = 'Updating ETF prices only...'
            for etf_cls, etf_ticker in {**GOLD_ETF_CLASSES, **SILVER_ETF_CLASSES}.items():
                from main import get_stock_data, update_etf_hero
                cur, ath = get_stock_data(etf_ticker)
                if cur and ath:
                    pct = (ath - cur) / ath * 100
                    gold_html   = update_etf_hero(gold_html,   etf_cls, cur, ath, pct)
                    silver_html = update_etf_hero(silver_html, etf_cls, cur, ath, pct)
                    print(f'  {etf_ticker}: ${cur:.2f}')
            GOLD_HTML.write_text(gold_html, encoding='utf-8')
            SILVER_HTML.write_text(silver_html, encoding='utf-8')

        if mode in ('all', 'gold'):
            _update_status['progress'] = 'Updating GOLD prices...'
            gold_html = update_html_file(
                gold_html, 'GOLD',
                ticker_map=GOLD_TICKER_MAP,
                static_tickers=GOLD_STATIC,
                investing_com_tickers=None,
                etf_classes=GOLD_ETF_CLASSES,
                gold_patterns=gold_patterns,
            )
            GOLD_HTML.write_text(gold_html, encoding='utf-8')

        if mode in ('all', 'silver'):
            _update_status['progress'] = 'Updating SILVER prices...'
            silver_html = update_html_file(
                silver_html, 'SILVER',
                ticker_map=SILVER_TICKER_MAP,
                static_tickers=set(),
                investing_com_tickers=SILVER_INVESTING_COM,
                etf_classes=SILVER_ETF_CLASSES,
                silver_patterns=silver_patterns,
            )
            SILVER_HTML.write_text(silver_html, encoding='utf-8')

        _update_status['progress'] = 'Generating merged HTML...'
        merged = generate_merged_html(gold_html, silver_html)
        OUTPUT_HTML.write_text(merged, encoding='utf-8')

        _update_status['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        _update_status['progress']     = 'Done'

    except Exception as e:
        _update_status['last_error'] = str(e)
        _update_status['progress']   = f'Error: {e}'
        print(f'Update error: {e}')
    finally:
        _update_status['running'] = False

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/dashboard')
def dashboard():
    if not OUTPUT_HTML.exists():
        # Generate merged HTML on first visit if it doesn't exist
        try:
            gold_html   = GOLD_HTML.read_text(encoding='utf-8')
            silver_html = SILVER_HTML.read_text(encoding='utf-8')
            merged = generate_merged_html(gold_html, silver_html)
            OUTPUT_HTML.write_text(merged, encoding='utf-8')
        except Exception as e:
            return Response(f'<pre>Error generating dashboard: {e}</pre>', status=500)

    html = OUTPUT_HTML.read_text(encoding='utf-8')

    # Inject status bar before </body>
    status = _update_status
    if status['last_updated']:
        updated_text = f'Last updated: {status["last_updated"]}'
    else:
        updated_text = 'Prices not yet refreshed this session'

    status_bar = f"""
<div id="status-bar" style="
  position:fixed; bottom:0; left:0; right:0;
  background:#1a1a2e; color:#e0e0e0;
  padding:10px 20px; font-family:monospace; font-size:0.82em;
  display:flex; align-items:center; gap:16px; z-index:9999;
  border-top:2px solid #d97706; box-shadow:0 -2px 10px rgba(0,0,0,0.3);">
  <span id="status-text" style="flex:1">{updated_text}</span>
  <span id="progress-text" style="color:#f59e0b;"></span>
  <button onclick="refreshPrices('all')"
    style="padding:6px 14px;background:#d97706;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
    Refresh All
  </button>
  <button onclick="refreshPrices('etf')"
    style="padding:6px 14px;background:#059669;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
    ETF Only
  </button>
  <button onclick="refreshPrices('gold')"
    style="padding:6px 14px;background:#92400e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
    Gold Only
  </button>
  <button onclick="refreshPrices('silver')"
    style="padding:6px 14px;background:#1e40af;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
    Silver Only
  </button>
  <button onclick="openETFModal()"
    style="padding:6px 14px;background:#4338ca;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
    ETF Lookup
  </button>
</div>
<div style="height:44px;"></div>
<script>
function refreshPrices(mode) {{
  fetch('/api/refresh', {{method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{mode: mode}}) }})
    .then(r => r.json())
    .then(d => {{
      if (d.ok) pollStatus();
      else document.getElementById('progress-text').textContent = d.error;
    }});
}}
function pollStatus() {{
  const poll = setInterval(() => {{
    fetch('/api/status').then(r => r.json()).then(d => {{
      document.getElementById('progress-text').textContent = d.running ? d.progress : '';
      if (d.last_updated) document.getElementById('status-text').textContent = 'Last updated: ' + d.last_updated;
      if (d.last_error)   document.getElementById('progress-text').textContent = 'Error: ' + d.last_error;
      if (!d.running) {{
        clearInterval(poll);
        if (!d.last_error) location.reload();
      }}
    }});
  }}, 2000);
}}
// Auto-poll if update is already running
fetch('/api/status').then(r => r.json()).then(d => {{ if (d.running) pollStatus(); }});
</script>

<div id="etf-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.78);z-index:10000;align-items:center;justify-content:center;">
  <div style="background:#1a1a2e;border:1px solid #d97706;border-radius:12px;padding:24px;width:min(780px,94vw);max-height:82vh;overflow-y:auto;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <span style="font-family:monospace;font-size:0.78rem;letter-spacing:2px;text-transform:uppercase;color:#d97706;">ETF &amp; Fund Holders</span>
      <button onclick="closeETFModal()" style="margin-left:auto;background:transparent;border:1px solid #444;color:#9ca3af;border-radius:4px;padding:4px 12px;cursor:pointer;font-family:monospace;font-size:0.75rem;">&#x2715; Close</button>
    </div>
    <form onsubmit="event.preventDefault();searchETFHolders()" style="display:flex;gap:8px;margin-bottom:16px;">
      <input type="text" id="etf-ticker-input" placeholder="e.g. NVDA, GDX, SILJ"
        autocomplete="off" autocapitalize="characters" spellcheck="false"
        style="flex:1;font-family:monospace;font-size:0.9rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:8px 14px;background:#0f1629;border:1px solid #555;color:#facc15;border-radius:4px;outline:none;transition:border-color 0.15s;"
        onfocus="this.style.borderColor='#d97706'" onblur="this.style.borderColor='#555'">
      <button type="submit" style="padding:8px 18px;background:#d97706;color:#000;border:none;border-radius:4px;cursor:pointer;font-family:monospace;font-size:0.8rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;">Search</button>
    </form>
    <div id="etf-results"></div>
  </div>
</div>
<script>
function openETFModal() {{
  const m = document.getElementById('etf-modal');
  m.style.display = 'flex';
  setTimeout(() => document.getElementById('etf-ticker-input').focus(), 50);
}}
function closeETFModal() {{
  document.getElementById('etf-modal').style.display = 'none';
  document.getElementById('etf-results').innerHTML = '';
}}
document.getElementById('etf-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeETFModal();
}});
async function searchETFHolders() {{
  const ticker = (document.getElementById('etf-ticker-input').value || '').trim().toUpperCase();
  if (!ticker) return;
  const res = document.getElementById('etf-results');
  res.innerHTML = '<div style="font-family:monospace;font-size:0.8rem;color:#9ca3af;padding:12px 0">Loading holders for ' + ticker + '…</div>';
  try {{
    const resp = await fetch('/api/etf-holders?ticker=' + encodeURIComponent(ticker));
    const data = await resp.json();
    if (data.error) {{
      res.innerHTML = '<div style="font-family:monospace;font-size:0.8rem;color:#f87171;padding:12px 0">Error: ' + data.error + '</div>';
      return;
    }}
    const fmtN   = (n) => n != null ? Number(n).toLocaleString() : '—';
    const fmtPct = (n) => n != null ? (parseFloat(n) * 100).toFixed(2) + '%' : '—';
    const fmtUSD = (n) => n != null ? '$' + Number(n).toLocaleString() : '—';
    const fmtDt  = (s) => s ? new Date(s).toLocaleDateString('en-US', {{month:'short',day:'numeric',year:'numeric'}}) : '—';
    const thS = 'text-align:left;padding:7px 10px;font-size:0.58rem;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;border-bottom:1px solid #2d3748;';
    const tdS = 'padding:7px 10px;border-bottom:1px solid rgba(255,255,255,0.06);color:#e2e8f0;font-family:monospace;font-size:0.7rem;';
    const mkTbl = (rows) => {{
      if (!rows || !rows.length) return '<div style="font-family:monospace;font-size:0.75rem;color:#6b7280;padding:8px 0">No data available.</div>';
      return '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:0.7rem;"><thead><tr>' +
        ['#','Holder','Shares','% Out','Value','Date'].map(h => '<th style="' + thS + '">' + h + '</th>').join('') +
        '</tr></thead><tbody>' +
        rows.map((r, i) =>
          '<tr>' +
          '<td style="' + tdS + 'color:#6b7280">' + (i + 1) + '</td>' +
          '<td style="' + tdS + '">' + (r['Holder'] || '—') + '</td>' +
          '<td style="' + tdS + '">' + fmtN(r['Shares']) + '</td>' +
          '<td style="' + tdS + '">' + fmtPct(r['% Out']) + '</td>' +
          '<td style="' + tdS + '">' + fmtUSD(r['Value']) + '</td>' +
          '<td style="' + tdS + '">' + fmtDt(r['Date Reported']) + '</td>' +
          '</tr>'
        ).join('') +
        '</tbody></table></div>';
    }};
    res.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">' +
        '<div><div style="font-family:monospace;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;color:#5ab4e0;margin-bottom:8px">Mutual Fund / ETF Holders</div>' + mkTbl(data.mutualFunds) + '</div>' +
        '<div><div style="font-family:monospace;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;color:#d97706;margin-bottom:8px">Institutional Holders</div>' + mkTbl(data.institutional) + '</div>' +
      '</div>';
  }} catch(e) {{
    res.innerHTML = '<div style="font-family:monospace;font-size:0.8rem;color:#f87171;padding:12px 0">Request failed.</div>';
  }}
}}
</script>
"""
    html = html.replace('</body>', status_bar + '\n</body>')
    return Response(html, mimetype='text/html')

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    from flask import request
    if _update_status['running']:
        return jsonify({'ok': False, 'error': 'Update already in progress'})
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'all')
    if mode not in ('all', 'gold', 'silver', 'etf'):
        mode = 'all'
    t = threading.Thread(target=_do_update, args=(mode,), daemon=True)
    t.start()
    return jsonify({'ok': True, 'mode': mode})

@app.route('/api/status')
def api_status():
    return jsonify({
        'running':      _update_status['running'],
        'last_updated': _update_status['last_updated'],
        'last_error':   _update_status['last_error'],
        'progress':     _update_status['progress'],
    })

@app.route('/api/etf-holders')
def etf_holders():
    from flask import request as freq
    import yfinance as yf
    ticker = freq.args.get('ticker', '').upper().strip()
    if not ticker:
        return jsonify({'error': 'ticker required'}), 400
    try:
        t = yf.Ticker(ticker)
        def df_to_records(df):
            if df is None or df.empty:
                return []
            return json.loads(df.to_json(orient='records', date_format='iso'))
        return jsonify({
            'ticker':        ticker,
            'mutualFunds':   df_to_records(t.mutualfund_holders),
            'institutional': df_to_records(t.institutional_holders),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Entry point ────────────────────────────────────────────────────────────────

# Start midnight scheduler (runs regardless of local vs Railway)
threading.Thread(target=_midnight_scheduler, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f'\nMiners Uplift Dashboard running at http://127.0.0.1:{port}')
    # Generate merged HTML on startup if not present
    if not OUTPUT_HTML.exists():
        print('Generating initial merged HTML...')
        try:
            gold_html   = GOLD_HTML.read_text(encoding='utf-8')
            silver_html = SILVER_HTML.read_text(encoding='utf-8')
            OUTPUT_HTML.write_text(generate_merged_html(gold_html, silver_html), encoding='utf-8')
            print('Done.')
        except Exception as e:
            print(f'Warning: {e}')
    app.run(host='0.0.0.0', port=port, debug=False)
