import yfinance as yf
import re
import sys
import os
import json
import cloudscraper
from bs4 import BeautifulSoup

def extract_all_tickers(html_content):
    """Extract unique tickers from the RING and AUAU data arrays."""
    patterns = [
        r'const ringData = (\[[\s\S]*?\]);',
        r'const auauData = (\[[\s\S]*?\]);',
        r'const gdxData = (\[[\s\S]*?\]);',
        r'const gdxjData = (\[[\s\S]*?\]);',
    ]
    seen = set()
    tickers = []
    for pattern in patterns:
        m = re.search(pattern, html_content)
        if m:
            for ticker in re.findall(r"ticker:'([^']+)'", m.group(1)):
                if ticker not in seen:
                    seen.add(ticker)
                    tickers.append(ticker)
    return tickers

def get_plzl_data():
    """Scrape PLZL current price and 52-week high from investing.com (price in RUB).
    Uses the JSON-LD FAQ block which contains both values in plain text."""
    url = 'https://www.investing.com/equities/polyus-zoloto_rts'
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        current, ath = None, None
        for tag in soup.find_all('script', type='application/ld+json'):
            data = json.loads(tag.string or '{}')
            if data.get('@type') != 'FAQPage':
                continue
            for item in data.get('mainEntity', []):
                answer = item.get('acceptedAnswer', {}).get('text', '')
                # "trading at a price of 2,136.4 RUB ... 52-week range spans from 1,617.0 RUB to 2,776.8 RUB"
                if 'trading at a price of' in answer:
                    m = re.search(r'trading at a price of ([\d,]+\.?\d*)', answer)
                    if m:
                        current = float(m.group(1).replace(',', ''))
                    m = re.search(r'52-week range spans from [\d,.]+ RUB to ([\d,]+\.?\d*)', answer)
                    if m:
                        ath = float(m.group(1).replace(',', ''))
                    break  # found the summary question, done

        if current is None:
            print('PLZL: could not parse price from investing.com')
        return current, ath
    except Exception as e:
        print(f'PLZL: error scraping investing.com: {e}')
        return None, None

def get_stock_data(ticker):
    """Get current price and 52-week high for a ticker using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        hist = stock.history(period='1y')
        ath = hist['High'].max() if not hist.empty else None
        return current_price, ath
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None, None

ETF_CLASSES = {
    'ring': 'RING',
    'auau': 'AUAU',
    'gdx':  'GDX',
    'gdxj': 'GDXJ',
}

def update_etf_hero(html_content, etf_class, current, ath, pct):
    """Update the hero-stats and summary stat-cards for one ETF tab."""
    current_str = f'${current:.2f}' if current is not None else 'N/A'
    ath_str     = f'${ath:.2f}'     if ath     is not None else 'N/A'
    pct_str     = f'-{abs(pct):.1f}%' if pct is not None else 'N/A'

    # Scope all replacements to within this tab's div
    tab_start = html_content.find(f'id="tab-{etf_class}"')
    if tab_start == -1:
        return html_content
    next_tab = html_content.find('<div id="tab-', tab_start + 1)
    if next_tab == -1:
        next_tab = len(html_content)

    section = html_content[tab_start:next_tab]

    # Hero-stat values (Current / 52-Wk High / % Below)
    section = re.sub(
        r'(<div class="label">Current</div><div class="val">)[^<]*(</div>)',
        rf'\g<1>{current_str}\2', section, count=1)
    section = re.sub(
        r'(<div class="label">52-Wk High</div><div class="val">)[^<]*(</div>)',
        rf'\g<1>{ath_str}\2', section, count=1)
    section = re.sub(
        r'(<div class="label">% Below</div><div class="val down">)[^<]*(</div>)',
        rf'\g<1>{pct_str}\2', section, count=1)

    # Stat-card ETF Price / 52-Wk High / % Below line
    section = re.sub(
        r'(<h3>ETF Price</h3><div class="value">)[^<]*(</div>)',
        rf'\g<1>{current_str}\2', section, count=1)
    section = re.sub(
        r'(<h3>52-Wk High</h3><div class="value">)[^<]*(</div>)',
        rf'\g<1>{ath_str}\2', section, count=1)
    section = re.sub(
        r'(% Below: )[^<]*(</p>)',
        rf'\g<1>{pct_str}\2', section, count=1)

    return html_content[:tab_start] + section + html_content[next_tab:]

def update_known_data(html_content, updates):
    """Update knownData in the HTML with new values, preserving tier."""
    for ticker, (current, ath, pct) in updates.items():
        # Accept pre-formatted strings (e.g. RUB values) or raw floats
        current_str = current if isinstance(current, str) else (f'${current:.2f}' if current is not None else 'N/A')
        ath_str     = ath     if isinstance(ath,     str) else (f'${ath:.2f}'     if ath     is not None else 'N/A')
        pct_val     = round(pct, 1)     if pct     is not None else 'null'

        lines = html_content.split('\n')
        for i, line in enumerate(lines):
            if f"'{ticker}':" in line:
                match = re.match(
                    r"\s*'[^']+':\s*\{\s*current:\s*'([^']*)',\s*ath:\s*'([^']*)',\s*pct:\s*([^,]+),\s*tier:\s*'([^']*)'\s*\},?",
                    line
                )
                if match:
                    _, _, _, tier = match.groups()
                    lines[i] = f"  '{ticker}': {{ current: '{current_str}', ath: '{ath_str}', pct: {pct_val}, tier: '{tier}' }},"
                    break
        html_content = '\n'.join(lines)
    return html_content

def main():
    html_file = os.path.join(os.path.dirname(__file__), 'gold_analysisETF.html')

    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"File not found: {html_file}")
        sys.exit(1)

    arg     = sys.argv[1] if len(sys.argv) > 1 else None
    only    = None
    na_only = arg and arg.lower() == '--na'
    if arg and not na_only:
        only = arg.upper()

    tickers = extract_all_tickers(html_content)

    if not tickers:
        print("No tickers found in the HTML file.")
        sys.exit(1)

    if only:
        if only not in tickers:
            print(f"Ticker '{only}' not found in HTML. Available: {', '.join(tickers)}")
            sys.exit(1)
        tickers = [only]
        print(f"Updating single ticker: {only}")
    elif na_only:
        na_set  = set(re.findall(r"'([^']+)':\s*\{[^}]*current:\s*'N/A'", html_content))
        tickers = [t for t in tickers if t in na_set]
        print(f"Found {len(tickers)} tickers with N/A prices. Fetching from yfinance...")
    else:
        print(f"Found {len(tickers)} unique tickers across all ETFs. Fetching 52-week data from yfinance...")

    # Map HTML display tickers → yfinance symbols where they differ
    ticker_map = {
        # Barrick / AngloGold / Kinross / IAMGOLD / Harmony / B2Gold — NYSE tickers work directly
        'DSV.V':   'DSVSF',    # Discovery Silver: TSXV ticker rarely works; use OTC
        'SCZM':    'SCZ.V',    # Santacruz Silver Mining TSXV
        'NFGC':    'NFGC',     # New Found Gold NYSE American
        'AUGO':    'AUGO',     # Aura Minerals NYSE American
        'ELE.V':   'ELE.V',    # Elemental Altus TSXV
        'NEWP':    'NEWP',     # New Pacific Metals NYSE American
        'ORLA':       'ORLA',        # Orla Mining NYSE (also TSX)
        'USAS':       'USAS',        # Americas Gold & Silver NYSE American
        'PE&OLES.MX': 'PE&OLES.MX', # Industrias Penoles BMV
        'ARTG.V':     'ARTG.V',      # Artemis Gold TSXV
        # GDXJ-specific
        'PAF.L':      'PAF.L',       # Pan African Resources AIM/LSE
        'SXGC.V':     'SXGC.TO',    # Southern Cross Gold TSX
        'KOZAA.IS':   'TRALT.IS',   # Koza Anadolu → Tralti Istanbul
        'CNMC.SI':    '5TP.SI',     # CNMC Goldmine Singapore
        'ASM':        'ASM',         # Avino Silver & Gold NYSE American
        'ITRG':       'ITRG',        # Integra Resources NYSE American
        'CMCL':       'CMCL',        # Caledonia Mining NYSE American
        'IDR':        'IDR',         # Idaho Strategic Resources NYSE American
        'CTGO':       'CTGO',        # Contango Ore NYSE American
        'VOXR':       'VOXR',        # Vox Royalty NYSE American
        'GLDG':       'GLDG',        # GoldMining Inc NYSE American
        'USAU':       'USAU',        # US Gold Corp NYSE American
        'FDR.V':      'FDR.V',       # Founders Metals TSXV
        'LUCA.V':     'LUCA.V',      # Luca Mining TSXV
        'WRLG.V':     'WRLG.V',      # West Red Lake TSXV
        'SBM.AX':     'SBM.AX',      # St Barbara ASX
        'BC8.AX':     'BC8.AX',      # Black Cat Syndicate ASX
        'AMI.AX':     'AMI.AX',      # Aurelia Metals ASX
        'AZY.AX':     'AZY.AX',      # Antipa Minerals ASX
        'MEK.AX':     'MEK.AX',      # Meeka Metals ASX
        'ASL.AX':     'ASL.AX',      # Andean Silver ASX
        'FFX.AX':     'FFX.AX',      # Firefinch ASX
        'SGD.V':      'SGD.TO',
        'GTWO.V':     'GTWO.TO',
        'RIO.V':      'RIO.TO',
        'CNL.V':      'CNL.TO',
        'HSLV.V':     'HSLV.TO',
        'ORE.V':      'ORE.TO',
        'ODV.TO':     'ODV',
    }

    # Tickers yfinance cannot reliably fetch
    static_tickers = {
        # PLZL handled separately via investing.com scraper
        'FFX.AX',    # Firefinch/Birimian Gold ASX — not on yfinance
    }

    updates = {}

    # PLZL: scrape from investing.com (price in RUB, no yfinance support)
    if 'PLZL' in tickers and (only in (None, 'PLZL') or na_only):
        print("Fetching PLZL from investing.com...")
        plzl_cur, plzl_ath = get_plzl_data()
        if plzl_cur is not None:
            plzl_pct = ((plzl_ath - plzl_cur) / plzl_ath) * 100 if plzl_ath else None
            # Store as pre-formatted RUB strings (no $ prefix)
            updates['PLZL'] = (f'{plzl_cur:,.0f}', f'{plzl_ath:,.0f}' if plzl_ath else 'N/A', plzl_pct)
            print(f"Updated PLZL: Current={plzl_cur:,.0f} RUB, ATH={plzl_ath:,.0f} RUB, %={plzl_pct:.1f}%")
        else:
            print("PLZL: skipping (could not fetch)")

    for ticker in tickers:
        if ticker == 'PLZL':
            continue  # already handled above
        if ticker in static_tickers:
            print(f"Skipping {ticker} (not supported by yfinance)")
            continue
        yf_ticker = ticker_map.get(ticker, ticker)
        current, ath = get_stock_data(yf_ticker)
        if current is not None and ath is not None:
            pct = ((ath - current) / ath) * 100
        else:
            pct = None
        updates[ticker] = (current, ath, pct)
        label = f"{ticker} ({yf_ticker})" if yf_ticker != ticker else ticker
        print(f"Updated {label}: Current={current}, ATH={ath}, %={pct}")

    updated_html = update_known_data(html_content, updates)

    # Update ETF-level hero sections (skip if updating a single individual stock)
    if not only or only in ETF_CLASSES.values():
        print("\nFetching ETF prices for hero sections...")
        for etf_class, etf_ticker in ETF_CLASSES.items():
            if only and only != etf_ticker:
                continue
            cur, ath = get_stock_data(etf_ticker)
            if cur is not None:
                pct = ((ath - cur) / ath) * 100 if ath else None
                updated_html = update_etf_hero(updated_html, etf_class, cur, ath, pct)
                print(f"Updated {etf_ticker}: Current=${cur:.2f}, ATH=${ath:.2f}, %Below={pct:.1f}%")
            else:
                print(f"Could not fetch {etf_ticker} ETF price")

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(updated_html)

    print(f"\nSaved {html_file}")

if __name__ == "__main__":
    main()
