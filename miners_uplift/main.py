"""
Miners Uplift Dashboard  main.py
===================================
Merges gold and silver ETF miner analysis into a single miners_uplift.html.
Updates prices from yfinance / investing.com, then regenerates the merged file.

Usage:
    python main.py              # Update all prices + generate merged HTML
    python main.py --gold       # Only update gold ETFs
    python main.py --silver     # Only update silver ETFs
    python main.py --na         # Only update N/A prices (both metals)
    python main.py --merge-only # Regenerate merged HTML without fetching prices
    python main.py TICKER       # Update a specific ticker
"""

import sys
import re
import os
import json
import concurrent.futures
import cloudscraper
from bs4 import BeautifulSoup
import yfinance as yf
from pathlib import Path
from datetime import datetime

BASE_DIR    = Path(__file__).parent
GOLD_HTML   = BASE_DIR / 'etf_gold_miners_uplift'  / 'gold_analysisETF.html'
SILVER_HTML = BASE_DIR / 'etf_silver_miners_uplift' / 'silver_analysisETF.html'
OUTPUT_HTML = BASE_DIR / 'miners_uplift.html'

#  Ticker maps 

GOLD_TICKER_MAP = {
    'DSV.V':   'DSVSF',
    'SCZM':    'SCZ.V',
    'NFGC':    'NFGC',
    'AUGO':    'AUGO',
    'ELE.V':   'ELE.V',
    'NEWP':    'NEWP',
    'ORLA':    'ORLA',
    'USAS':    'USAS',
    'PE&OLES.MX': 'PE&OLES.MX',
    'ARTG.V':  'ARTG.V',
    'PAF.L':   'PAF.L',
    'SXGC.V':  'SXGC.TO',
    'KOZAA.IS':'TRALT.IS',
    'CNMC.SI': '5TP.SI',
    'ASM':     'ASM',
    'ITRG':    'ITRG',
    'CMCL':    'CMCL',
    'IDR':     'IDR',
    'CTGO':    'CTGO',
    'VOXR':    'VOXR',
    'GLDG':    'GLDG',
    'USAU':    'USAU',
    'FDR.V':   'FDR.V',
    'LUCA.V':  'LUCA.V',
    'WRLG.V':  'WRLG.V',
    'SBM.AX':  'SBM.AX',
    'BC8.AX':  'BC8.AX',
    'AMI.AX':  'AMI.AX',
    'AZY.AX':  'AZY.AX',
    'MEK.AX':  'MEK.AX',
    'ASL.AX':  'ASL.AX',
    'FFX.AX':  'FFX.AX',
    'SGD.V':   'SGD.TO',
    'GTWO.V':  'GTWO.TO',
    'RIO.V':   'RIO.TO',
    'CNL.V':   'CNL.TO',
    'HSLV.V':  'HSLV.TO',
    'ORE.V':   'ORE.TO',
    'ODV.TO':  'ODV',
}

SILVER_TICKER_MAP = {
    'FRES':     'FRES.L',
    'ABRA':     'ABRA.TO',
    'PE&OLES*': 'PE&OLES.MX',
    'PE&OLES':  'PE&OLES.MX',
    'KGH':      'KGH.WA',
    'BOL':      'BOL.ST',
    'ARTG':     'ARTG.V',
    'HOC':      'HOC.L',
    'GGD':      'GGD.TO',
    'KCN':      'KCN.AX',
    'SVL':      'SVL.AX',
    'HSTR':     'HSTR.V',
    'GSVR':     'GSVR.V',
    'SVRS':     'SVRS.V',
    'TUD':      'TUD.V',
    'AAG':      'AAG.V',
    'AGMR':     'AGMR.TO',
    'CKG':      'CKG.V',
    'CUU':      'CUU.V',
    'FPC':      'FPC.V',
    'IPT':      'IPT.V',
    'WAM':      'WAM.V',
    'MFRISCOA': 'MFRISCOA-1.MX',
    'WVM':      'WVM.V',
    'AMM':      'AMM.V',
    'MKR':      'MKR.AX',
    'DSV':      'DSVSF',
    'FVI':      'FVI.TO',
    'SCZ':      'SCZ.V',
    'NUAG':     'NUAG.TO',
    'ITR':      'ITR.V',
    'SLVR':     'SLVR.V',
    'ASL':      'ASL.AX',
    'BRC':      'BRC.V',
    'USL':      'USL.AX',
    'SOSI':     'SOSI.ST',
    'GORO':     'GORO',
    'K':        'KGC',
}

GOLD_STATIC = {'FFX.AX'}

SILVER_INVESTING_COM = {
    'VOLCABC1': 'https://www.investing.com/equities/volcan-cmp-min?cid=102134',
    'APX.PS':   'https://www.investing.com/equities/apex-mining-a',
}

GOLD_ETF_CLASSES = {'ring': 'RING', 'auau': 'AUAU', 'gdx': 'GDX', 'gdxj': 'GDXJ'}
SILVER_ETF_CLASSES = {'slvp': 'SLVP', 'sil': 'SIL', 'silj': 'SILJ'}

_scraper = None

#  Price fetching 

def get_scraper():
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper()
    return _scraper

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        current = info.get('currentPrice') or info.get('regularMarketPrice')
        hist  = stock.history(period='1y')
        ath   = hist['High'].max() if not hist.empty else None
        return current, ath
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")
        return None, None

def get_etf_aum(ticker):
    try:
        info = yf.Ticker(ticker).info
        aum = info.get('totalAssets') or info.get('netAssets')
        return aum
    except Exception:
        return None

def _fmt_aum(aum):
    if aum is None:
        return 'N/A'
    if aum >= 1e9:
        return f'${aum/1e9:.1f}B'
    if aum >= 1e6:
        return f'${aum/1e6:.0f}M'
    return f'${aum:,.0f}'

def get_plzl_data():
    url = 'https://www.investing.com/equities/polyus-zoloto_rts'
    try:
        resp = get_scraper().get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        current = ath = None
        for tag in soup.find_all('script', type='application/ld+json'):
            data = json.loads(tag.string or '{}')
            if data.get('@type') != 'FAQPage':
                continue
            for item in data.get('mainEntity', []):
                answer = item.get('acceptedAnswer', {}).get('text', '')
                if 'trading at a price of' in answer:
                    m = re.search(r'trading at a price of ([\d,]+\.?\d*)', answer)
                    if m: current = float(m.group(1).replace(',', ''))
                    m = re.search(r'52-week range spans from [\d,.]+ RUB to ([\d,]+\.?\d*)', answer)
                    if m: ath = float(m.group(1).replace(',', ''))
                    break
        if current is None:
            print('  PLZL: could not parse price')
        return current, ath
    except Exception as e:
        print(f'  PLZL: error scraping investing.com: {e}')
        return None, None

def get_investing_com_data(url):
    try:
        resp = get_scraper().get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        current = None
        price_elem = soup.find(attrs={'data-test': 'instrument-price-last'})
        if not price_elem:
            price_elem = soup.select_one('[class*="text-5xl"]')
        if price_elem:
            try: current = float(price_elem.get_text(strip=True).replace(',', ''))
            except ValueError: pass
        ath = None
        for div in soup.find_all('div', class_='text-secondary'):
            if '52 wk Range' in div.get_text():
                spans = div.parent.find_all('span')
                if len(spans) >= 2:
                    try: ath = float(spans[-1].get_text(strip=True).replace(',', ''))
                    except ValueError: pass
                break
        return current, ath
    except Exception as e:
        print(f'  Error fetching {url}: {e}')
        return None, None

#  HTML updating 

def extract_tickers(html, patterns):
    seen, tickers = set(), []
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            for t in re.findall(r"ticker:'([^']+)'", m.group(1)):
                if t not in seen:
                    seen.add(t)
                    tickers.append(t)
    return tickers

def update_known_data(html, updates):
    for ticker, (current, ath, pct) in updates.items():
        current_str = current if isinstance(current, str) else (f'${current:.2f}' if current is not None else 'N/A')
        ath_str     = ath     if isinstance(ath,     str) else (f'${ath:.2f}'     if ath     is not None else 'N/A')
        pct_val     = round(pct, 1) if pct is not None else 'null'
        lines = html.split('\n')
        for i, line in enumerate(lines):
            if f"'{ticker}':" in line:
                m = re.match(
                    r"\s*'[^']+':\s*\{\s*current:\s*'([^']*)',\s*ath:\s*'([^']*)',\s*pct:\s*([^,]+),\s*tier:\s*'([^']*)'\s*\},?",
                    line)
                if m:
                    _, _, _, tier = m.groups()
                    lines[i] = f"  '{ticker}': {{ current: '{current_str}', ath: '{ath_str}', pct: {pct_val}, tier: '{tier}' }},"
                    break
        html = '\n'.join(lines)
    return html

def update_etf_hero(html, etf_class, current, ath, pct, aum=None):
    current_str = f'${current:.2f}' if current is not None else 'N/A'
    ath_str     = f'${ath:.2f}'     if ath     is not None else 'N/A'
    pct_str     = f'-{abs(pct):.1f}%' if pct is not None else 'N/A'
    aum_str     = _fmt_aum(aum)
    tab_start = html.find(f'id="tab-{etf_class}"')
    if tab_start == -1: return html
    next_tab  = html.find('<div id="tab-', tab_start + 1)
    if next_tab == -1: next_tab = len(html)
    section = html[tab_start:next_tab]
    section = re.sub(r'(<div class="label">Current</div><div class="val">)[^<]*(</div>)',     rf'\g<1>{current_str}\2', section, count=1)
    section = re.sub(r'(<div class="label">52-Wk High</div><div class="val">)[^<]*(</div>)', rf'\g<1>{ath_str}\2',     section, count=1)
    section = re.sub(r'(<div class="label">% Below</div><div class="val down">)[^<]*(</div>)',rf'\g<1>{pct_str}\2',    section, count=1)
    section = re.sub(r'(<h3>ETF Price</h3><div class="value">)[^<]*(</div>)',                 rf'\g<1>{current_str}\2', section, count=1)
    section = re.sub(r'(<h3>52-Wk High</h3><div class="value">)[^<]*(</div>)',               rf'\g<1>{ath_str}\2',     section, count=1)
    section = re.sub(r'(% Below: )[^<]*(</p>)',                                               rf'\g<1>{pct_str}\2',    section, count=1)
    section = re.sub(r'(<h3>AUM</h3><div class="value">)[^<]*(</div>)',                       rf'\g<1>{aum_str}\2',    section, count=1)
    return html[:tab_start] + section + html[next_tab:]

#  Price update orchestration 

def update_html_file(html, metal, ticker_map, static_tickers, investing_com_tickers,
                     etf_classes, gold_patterns=None, silver_patterns=None,
                     only=None, na_only=False):
    patterns = gold_patterns or silver_patterns or []
    tickers = extract_tickers(html, patterns)
    if not tickers:
        print(f"No tickers found in {metal} HTML.")
        return html

    if only:
        tickers = [only] if only in tickers else []
    elif na_only:
        na_set  = set(re.findall(r"'([^']+)':\s*\{[^}]*current:\s*'N/A'", html))
        tickers = [t for t in tickers if t in na_set]
        print(f"  {metal}: {len(tickers)} N/A tickers")
    else:
        print(f"  {metal}: {len(tickers)} unique tickers")

    updates = {}

    if metal == 'GOLD' and 'PLZL' in tickers and (not only or only == 'PLZL'):
        print("  Fetching PLZL from investing.com...")
        cur, ath = get_plzl_data()
        if cur is not None:
            pct = ((ath - cur) / ath * 100) if ath else None
            updates['PLZL'] = (f'{cur:,.0f}', f'{ath:,.0f}' if ath else 'N/A', pct)
            print(f"  PLZL: {cur:,.0f} RUB / ATH {ath:,.0f} RUB / {pct:.1f}%")

    # Investing.com tickers (sequential — rate limit)
    for ticker in tickers:
        if ticker in (investing_com_tickers or {}):
            url = investing_com_tickers[ticker]
            cur, ath = get_investing_com_data(url)
            pct = ((ath - cur) / ath * 100) if cur and ath else None
            updates[ticker] = (cur, ath, pct)
            print(f"  {ticker} (investing.com): {cur} / {ath} / {pct}")

    # yfinance tickers — batch download (one request for all tickers)
    yf_map = {}  # orig_ticker -> yf_ticker
    for ticker in tickers:
        if metal == 'GOLD' and ticker == 'PLZL':
            continue
        if ticker in (static_tickers or set()):
            print(f"  Skipping {ticker} (not on yfinance)")
            continue
        if ticker in (investing_com_tickers or {}):
            continue
        yf_map[ticker] = ticker_map.get(ticker, ticker)

    if yf_map:
        yf_symbols = list(yf_map.values())
        try:
            batch = yf.download(yf_symbols, period='1y', auto_adjust=True,
                                progress=False, threads=True)
            close = batch['Close'] if 'Close' in batch else batch.get('close', batch)
            high  = batch['High']  if 'High'  in batch else batch.get('high',  batch)
            for orig, yf_t in yf_map.items():
                try:
                    col = yf_t if yf_t in close.columns else None
                    if col is None and len(yf_symbols) == 1:
                        col = close.columns[0] if not close.empty else None
                    if col is not None:
                        cur = float(close[col].dropna().iloc[-1])
                        ath = float(high[col].dropna().max())
                        pct = ((ath - cur) / ath * 100) if ath else None
                        updates[orig] = (cur, ath, pct)
                        label = f"{orig} ({yf_t})" if yf_t != orig else orig
                        print(f"  {label}: {cur:.2f} / {ath:.2f}")
                    else:
                        updates[orig] = (None, None, None)
                except Exception as e:
                    print(f"  {orig}: parse error {e}")
                    updates[orig] = (None, None, None)
        except Exception as e:
            print(f"  Batch download failed ({e}), falling back to individual fetches")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                def _fetch_one(args):
                    orig, yf_t = args
                    cur, ath = get_stock_data(yf_t)
                    pct = ((ath - cur) / ath * 100) if cur and ath else None
                    return orig, (cur, ath, pct)
                for orig, result in ex.map(_fetch_one, list(yf_map.items())):
                    updates[orig] = result

    html = update_known_data(html, updates)

    if not only or only in etf_classes.values():
        print(f"\n  Updating {metal} ETF hero sections...")
        for etf_cls, etf_ticker in etf_classes.items():
            if only and only != etf_ticker:
                continue
            cur, ath = get_stock_data(etf_ticker)
            aum = get_etf_aum(etf_ticker)
            if cur:
                pct = ((ath - cur) / ath * 100) if ath else None
                html = update_etf_hero(html, etf_cls, cur, ath, pct, aum)
                print(f"  {etf_ticker}: ${cur:.2f} / ${ath:.2f} / -{pct:.1f}% / AUM {_fmt_aum(aum)}")

    return html

#  Merged HTML generation 

def _between(html, start, end):
    s = html.find(start)
    if s == -1: return ''
    s += len(start)
    e = html.find(end, s)
    return html[s:e] if e != -1 else html[s:]

def generate_merged_html(gold_html, silver_html):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    #  Extract CSS 
    gold_css   = _between(gold_html,   '<style>', '</style>')
    silver_css = _between(silver_html, '<style>', '</style>')

    # Silver-specific styles not in gold CSS
    silver_color_overrides = """
/* Silver ETF hero gradients */
.etf-hero.slvp { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
.etf-hero.sil  { background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%); }
.etf-hero.silj { background: linear-gradient(135deg, #059669 0%, #10b981 100%); }

/* Silver tab active colors */
.tab-btn.slvp.active { border-top: 3px solid #2563eb; }
.tab-btn.sil.active  { border-top: 3px solid #7c3aed; }
.tab-btn.silj.active { border-top: 3px solid #059669; }

/* Silver theme overrides (scoped to .metal-silver) */
.metal-silver .page-header { border-bottom-color: #2563eb; }
.metal-silver .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.metal-silver .tab-btn.active { color: #1e40af; border-bottom: 3px solid white; margin-bottom: -3px; box-shadow: 0 -2px 8px rgba(0,0,0,0.06); }
.metal-silver .ticker { color: #1e40af; }
.metal-silver .ath-val { color: #7c3aed; }
.metal-silver tbody tr:hover { background: #f9fafb; }
.metal-silver .legend { background: #f9fafb; }
"""

    metal_tab_css = """
/* Metal top-level tabs */
.metal-tab-bar { display: flex; gap: 8px; margin-bottom: 28px; border-bottom: 3px solid #e5e7eb; }
.metal-tab { padding: 14px 32px; font-size: 1.05em; font-weight: 700; cursor: pointer;
             border: none; background: #f3f4f6; color: #6b7280; border-radius: 10px 10px 0 0;
             transition: all 0.2s; letter-spacing: 0.5px; }
.metal-tab:hover { background: #e5e7eb; color: #374151; }
.metal-tab.gold-tab.active   { background: white; color: #92400e; border-bottom: 3px solid white;
                                margin-bottom: -3px; border-top: 4px solid #d97706;
                                box-shadow: 0 -2px 10px rgba(0,0,0,0.08); }
.metal-tab.silver-tab.active { background: white; color: #1e40af; border-bottom: 3px solid white;
                                margin-bottom: -3px; border-top: 4px solid #2563eb;
                                box-shadow: 0 -2px 10px rgba(0,0,0,0.08); }
.metal-section { display: none; }
.metal-section.active { display: block; }
"""

    #  Extract body content (tab-nav + tab-panels) — stop before footer to avoid stray </div>
    gold_body_start   = gold_html.find('<div class="tab-nav">')
    gold_body_end     = gold_html.find('<div class="footer">')
    if gold_body_end == -1: gold_body_end = gold_html.find('<script>')

    silver_body_start = silver_html.find('<div class="tab-nav">')
    silver_body_end   = silver_html.find('<div class="footer">')
    if silver_body_end == -1: silver_body_end = silver_html.find('<script>')

    gold_body   = gold_html[gold_body_start:gold_body_end].strip() if gold_body_start != -1 else ''
    silver_body = silver_html[silver_body_start:silver_body_end].strip() if silver_body_start != -1 else ''

    # Fix showTab references in HTML to use metal-scoped functions
    gold_body   = gold_body.replace("showTab('",   "showGoldTab('")
    silver_body = silver_body.replace("showTab('", "showSilverTab('")

    #  Extract and process JavaScript 
    gold_js   = _between(gold_html,   '<script>', '</script>').strip()
    silver_js = _between(silver_html, '<script>', '</script>').strip()

    # Rename knownData in gold  goldKnownData
    gold_js = gold_js.replace('const knownData = {', 'const goldKnownData = {', 1)
    gold_js = re.sub(r'\bknownData\[', 'knownData[', gold_js)  # keep renderTable references unchanged for now

    # Rename showTab in gold  showGoldTab
    gold_js = gold_js.replace('function showTab(', 'function showGoldTab(', 1)

    # From silver JS, extract only: knownData block + loadETFData content
    silver_known_start = silver_js.find('const knownData = {')
    silver_known_end   = silver_js.find('\n};', silver_known_start) + 3
    silver_known_block = silver_js[silver_known_start:silver_known_end]
    silver_known_block = silver_known_block.replace('const knownData = {', 'const silverKnownData = {', 1)

    silver_load_start = silver_js.find('function loadETFData()')
    silver_load_end   = silver_js.find('\nfunction showTab(', silver_load_start)
    if silver_load_end == -1:
        silver_load_end = silver_js.find('\nwindow.onload', silver_load_start)
    if silver_load_end == -1:
        silver_load_end = len(silver_js)
    silver_load_block = silver_js[silver_load_start:silver_load_end].strip()
    silver_load_block = silver_load_block.replace('function loadETFData()', 'function loadSilverETFData()', 1)

    # Add filter-row guard to both gold and silver load blocks so filter rows never duplicate
    filter_guard = "    if (!table.querySelector('.filter-row')) table.querySelector('thead').appendChild(filterRow);"
    gold_js   = gold_js.replace("    table.querySelector('thead').appendChild(filterRow);", filter_guard)
    silver_load_block = silver_load_block.replace("    table.querySelector('thead').appendChild(filterRow);", filter_guard)

    # Strip window.onload and stale showTab from gold_js — we control initialization ourselves
    gold_js = re.sub(r'\nwindow\.onload\s*=\s*loadETFData\s*;', '', gold_js)
    gold_js = re.sub(r'\nfunction showTab\([\s\S]*?\n\}', '', gold_js)

    # Build the combined JS
    combined_js = f"""
{gold_js}

{silver_known_block}

// Merged knownData - silver values override gold for shared tickers
const knownData = Object.assign({{}}, goldKnownData, silverKnownData);

{silver_load_block}

function showGoldTab(name) {{
  document.querySelectorAll('#gold-section .tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#gold-section .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('#gold-section .tab-btn.' + name).classList.add('active');
}}

function showSilverTab(name) {{
  document.querySelectorAll('#silver-section .tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#silver-section .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('#silver-section .tab-btn.' + name).classList.add('active');
}}

function setMetal(metal) {{
  document.querySelectorAll('.metal-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.metal-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(metal + '-section').classList.add('active');
  document.querySelector('.metal-tab.' + metal + '-tab').classList.add('active');
}}

// Initialize both metals on load - script is at end of body so DOM is ready
loadETFData();
loadSilverETFData();
"""

    # Remove duplicate showGoldTab definition from gold_js (it was defined inline before)
    # The gold_js already has showGoldTab  we already renamed it above, no dupe issue

    #  Build final HTML 
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Precious Metals Miners ETF Dashboard</title>
<style>
{gold_css}
{silver_color_overrides}
{metal_tab_css}
</style>
</head>
<body>
<div class="container">

  <div class="page-header">
    <h1> Miners ETF Dashboard</h1>
    <span class="page-date">Updated {now}</span>
  </div>

  <div class="metal-tab-bar">
    <button class="metal-tab gold-tab active"   onclick="setMetal('gold')"> GOLD MINERS</button>
    <button class="metal-tab silver-tab"         onclick="setMetal('silver')"> SILVER MINERS</button>
  </div>

  <!-- GOLD SECTION -->
  <div id="gold-section" class="metal-section active">
    {gold_body}
  </div>

  <!-- SILVER SECTION -->
  <div id="silver-section" class="metal-section metal-silver">
    {silver_body}
  </div>

  <div class="footer">
    <p><strong>Tier Classification:</strong> Mega Cap (&gt;$20B) &middot; Senior ($5B-$20B) &middot; Mid-Tier ($1B-$5B) &middot; Junior-Mid ($500M-$1B) &middot; Junior ($100M-$500M) &middot; Micro (&lt;$100M)</p>
    <p style="margin-top:6px;"><strong>Data:</strong> Yahoo Finance &middot; investing.com &middot; Updated {now}</p>
  </div>

</div>
<script>
{combined_js}
</script>
</body>
</html>"""

    return html

#  Main 

def main():
    args      = sys.argv[1:]
    merge_only = '--merge-only' in args
    gold_only  = '--gold'   in args
    silver_only= '--silver' in args
    na_only    = '--na'     in args
    only       = None
    if args and not any(a.startswith('--') for a in args):
        only = args[0].upper()

    # Read both HTML files
    try:
        gold_html   = GOLD_HTML.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"Gold HTML not found: {GOLD_HTML}")
        sys.exit(1)
    try:
        silver_html = SILVER_HTML.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"Silver HTML not found: {SILVER_HTML}")
        sys.exit(1)

    if not merge_only:
        # Update gold
        if not silver_only:
            print("\n-- Updating GOLD --")
            gold_html = update_html_file(
                gold_html, 'GOLD',
                ticker_map=GOLD_TICKER_MAP,
                static_tickers=GOLD_STATIC,
                investing_com_tickers=None,
                etf_classes=GOLD_ETF_CLASSES,
                gold_patterns=[
                    r'const ringData = (\[[\s\S]*?\]);',
                    r'const auauData = (\[[\s\S]*?\]);',
                    r'const gdxData  = (\[[\s\S]*?\]);',
                    r'const gdxjData = (\[[\s\S]*?\]);',
                ],
                only=only, na_only=na_only
            )
            GOLD_HTML.write_text(gold_html, encoding='utf-8')
            print(f"  Saved {GOLD_HTML.name}")

        # Update silver
        if not gold_only:
            print("\n-- Updating SILVER --")
            silver_html = update_html_file(
                silver_html, 'SILVER',
                ticker_map=SILVER_TICKER_MAP,
                static_tickers=set(),
                investing_com_tickers=SILVER_INVESTING_COM,
                etf_classes=SILVER_ETF_CLASSES,
                silver_patterns=[
                    r'const slvpData = (\[[\s\S]*?\]);',
                    r'const silData  = (\[[\s\S]*?\]);',
                    r'const siljData = (\[[\s\S]*?\]);',
                ],
                only=only, na_only=na_only
            )
            SILVER_HTML.write_text(silver_html, encoding='utf-8')
            print(f"  Saved {SILVER_HTML.name}")

    # Generate merged HTML
    print("\n-- Generating merged HTML --")
    merged = generate_merged_html(gold_html, silver_html)
    OUTPUT_HTML.write_text(merged, encoding='utf-8')
    print(f"  Saved {OUTPUT_HTML}")
    print(f"\nDone. Open: {OUTPUT_HTML}")

if __name__ == '__main__':
    main()
