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
<script>

</script>
"""

    miner_lookup = """
<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:14px 18px;margin-bottom:20px;">
  <form onsubmit="event.preventDefault();searchMiner()" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
    <span style="font-weight:700;font-size:0.9em;color:#92400e;white-space:nowrap;">&#128269; Miner Lookup</span>
    <input type="text" id="miner-input" placeholder="Ticker or name..."
      autocomplete="off" autocapitalize="characters" spellcheck="false"
      style="font-family:monospace;font-size:0.9em;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:7px 12px;border:1px solid #fcd34d;border-radius:6px;outline:none;width:160px;background:#fff;color:#92400e;">
    <button type="submit"
      style="padding:7px 18px;background:#d97706;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.85em;">
      Search
    </button>
    <span style="font-size:0.75em;color:#b45309;">Searches RING &middot; AUAU &middot; GDX &middot; GDXJ &middot; SLVP &middot; SIL &middot; SILJ</span>
  </form>
  <div id="miner-results" style="margin-top:12px;display:none;"></div>
</div>
<script>
async function searchMiner() {
  const q = (document.getElementById('miner-input').value || '').trim().toUpperCase();
  if (!q) return;
  const res = document.getElementById('miner-results');
  res.style.display = 'block';
  res.innerHTML = '<span style="font-family:monospace;font-size:0.8em;color:#6b7280">Searching...</span>';
  try {
    const resp = await fetch('/api/miner-search?q=' + encodeURIComponent(q));
    const data = await resp.json();
    if (data.error) { res.innerHTML = '<span style="color:#dc2626;font-family:monospace;font-size:0.8em">' + data.error + '</span>'; return; }
    if (!data.results.length) {
      res.innerHTML = '<span style="font-family:monospace;font-size:0.82em;color:#6b7280">Not found in any of the 7 dashboard ETFs.</span>';
      return;
    }
    const colors = {RING:'#d97706',AUAU:'#f59e0b',GDX:'#b45309',GDXJ:'#92400e',SLVP:'#1d4ed8',SIL:'#7c3aed',SILJ:'#059669'};
    const rows = data.results;
    let html = '<div style="font-size:0.82em;color:#374151;margin-bottom:8px;font-weight:600">Found <strong>'
      + rows[0].name + '</strong> (' + rows[0].ticker + ') in <strong>' + rows.length + '</strong> ETF' + (rows.length > 1 ? 's' : '') + ':</div>';
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.82em;">'
      + '<thead><tr style="border-bottom:2px solid #e5e7eb">'
      + ['ETF','Rank','Weight','Current','52wk High','% Below ATH','Tier'].map(function(h) {
          return '<th style="text-align:left;padding:6px 10px;font-size:0.72em;letter-spacing:1px;text-transform:uppercase;color:#6b7280;white-space:nowrap">' + h + '</th>';
        }).join('')
      + '</tr></thead><tbody>'
      + rows.map(function(r) {
          return '<tr style="border-bottom:1px solid #f3f4f6">'
            + '<td style="padding:7px 10px"><span style="background:' + (colors[r.etf]||'#374151') + ';color:#fff;padding:2px 8px;border-radius:4px;font-weight:700;font-size:0.85em">' + r.etf + '</span></td>'
            + '<td style="padding:7px 10px;color:#6b7280">#' + r.rank + '</td>'
            + '<td style="padding:7px 10px;font-weight:700">' + r.weight + '</td>'
            + '<td style="padding:7px 10px;font-weight:700;color:#059669">' + r.current + '</td>'
            + '<td style="padding:7px 10px">' + r.ath + '</td>'
            + '<td style="padding:7px 10px;font-weight:700;color:#dc2626">' + (r.pct != null ? '-' + r.pct + '%' : 'N/A') + '</td>'
            + '<td style="padding:7px 10px;color:#6b7280">' + (r.tier||'') + '</td>'
            + '</tr>';
        }).join('')
      + '</tbody></table></div>';
    res.innerHTML = html;
  } catch(e) {
    res.innerHTML = '<span style="color:#dc2626;font-family:monospace;font-size:0.8em">Request failed.</span>';
  }
}
</script>
"""

    html = html.replace('<div class="metal-tab-bar">', miner_lookup + '<div class="metal-tab-bar">')
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

@app.route('/api/miner-search')
def miner_search():
    import re
    from flask import request as freq
    q = freq.args.get('q', '').strip().upper()
    if not q:
        return jsonify({'error': 'query required'}), 400
    try:
        gold_html   = GOLD_HTML.read_text(encoding='utf-8')
        silver_html = SILVER_HTML.read_text(encoding='utf-8')

        etf_defs = [
            ('RING', gold_html,   r'const ringData\s*=\s*(\[[\s\S]*?\]);'),
            ('AUAU', gold_html,   r'const auauData\s*=\s*(\[[\s\S]*?\]);'),
            ('GDX',  gold_html,   r'const gdxData\s*=\s*(\[[\s\S]*?\]);'),
            ('GDXJ', gold_html,   r'const gdxjData\s*=\s*(\[[\s\S]*?\]);'),
            ('SLVP', silver_html, r'const slvpData\s*=\s*(\[[\s\S]*?\]);'),
            ('SIL',  silver_html, r'const silData\s*=\s*(\[[\s\S]*?\]);'),
            ('SILJ', silver_html, r'const siljData\s*=\s*(\[[\s\S]*?\]);'),
        ]

        known = {}
        for html in (gold_html, silver_html):
            for m in re.finditer(
                r"'([^']+)':\s*\{\s*current:\s*'([^']*)',\s*ath:\s*'([^']*)',\s*pct:\s*([^,\n]+),\s*tier:\s*'([^']*)'",
                html
            ):
                ticker, current, ath, pct_raw, tier = m.groups()
                try:
                    pct = round(float(pct_raw.strip()), 1)
                except ValueError:
                    pct = None
                known[ticker] = {'current': current, 'ath': ath, 'pct': pct, 'tier': tier}

        results = []
        for etf_name, html, pattern in etf_defs:
            m = re.search(pattern, html)
            if not m:
                continue
            entries = re.findall(r"\{ticker:'([^']+)',\s*name:'([^']+)',\s*weight:'([^']+)'\}", m.group(1))
            for i, (ticker, name, weight) in enumerate(entries):
                if ticker.upper() == q or q in name.upper():
                    info = known.get(ticker, {})
                    results.append({
                        'etf':     etf_name,
                        'ticker':  ticker,
                        'name':    name,
                        'weight':  weight,
                        'rank':    i + 1,
                        'current': info.get('current', 'N/A'),
                        'ath':     info.get('ath', 'N/A'),
                        'pct':     info.get('pct'),
                        'tier':    info.get('tier', ''),
                    })

        return jsonify({'query': q, 'results': results})
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
