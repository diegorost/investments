import yfinance as yf
import re
import sys
import os
from datetime import datetime

def extract_all_tickers(html_content):
    """Extract unique tickers from all three ETF data arrays."""
    patterns = [
        r'const slvpData = (\[[\s\S]*?\]);',
        r'const silData = (\[[\s\S]*?\]);',
        r'const siljData = (\[[\s\S]*?\]);',
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

def get_stock_data(ticker):
    """
    Get current price and all-time high for a ticker using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Current price
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        
        # All-time high
        hist = stock.history(period='1y')
        if not hist.empty:
            ath = hist['High'].max()
        else:
            ath = None
        
        return current_price, ath
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None, None

def update_known_data(html_content, updates):
    """
    Update the knownData in the HTML with new values.
    """
    for ticker, (current, ath, pct) in updates.items():
        # Format the values
        if current is not None:
            current_str = f'${current:.2f}'
        else:
            current_str = 'N/A'
        
        if ath is not None:
            ath_str = f'${ath:.2f}'
        else:
            ath_str = 'N/A'
        
        if pct is not None:
            pct_val = round(pct, 1)
        else:
            pct_val = 'null'
        
        # Find and replace the line for this ticker
        pattern = rf"('{ticker}': \{{\s*current: '[^']*',\s*ath: '[^']*',\s*pct: [^,]+,\s*tier: '[^']*'\s*\}},?)"
        replacement = f"'{ticker}': {{ current: '{current_str}', ath: '{ath_str}', pct: {pct_val}, tier: '\\1' }},"
        
        # But tier is kept the same, so need to preserve it.
        # Actually, better to match the exact line and replace current, ath, pct.
        
        # Find the line
        lines = html_content.split('\n')
        for i, line in enumerate(lines):
            if f"'{ticker}':" in line:
                # Parse the line
                # 'HL': { current: '$20.45', ath: '$34.17', pct: -40.2, tier: 'Mid-Tier Producer' },
                match = re.match(r"\s*'[^']+':\s*\{\s*current:\s*'([^']*)',\s*ath:\s*'([^']*)',\s*pct:\s*([^,]+),\s*tier:\s*'([^']*)'\s*\},?", line)
                if match:
                    _, _, _, tier = match.groups()
                    new_line = f"  '{ticker}': {{ current: '{current_str}', ath: '{ath_str}', pct: {pct_val}, tier: '{tier}' }},"
                    lines[i] = new_line
                    break
        
        html_content = '\n'.join(lines)
    
    return html_content

def main():
    html_file = os.path.join(os.path.dirname(__file__), 'silver_analysisETF.html')
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"File not found: {html_file}")
        sys.exit(1)
    
    arg = sys.argv[1] if len(sys.argv) > 1 else None
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
        na_set = set(re.findall(r"'([^']+)':\s*\{[^}]*current:\s*'N/A'", html_content))
        tickers = [t for t in tickers if t in na_set]
        print(f"Found {len(tickers)} tickers with N/A prices. Fetching 52-week data from yfinance...")
    else:
        print(f"Found {len(tickers)} unique tickers across all ETFs. Fetching 52-week data from yfinance...")
    
    ticker_map = {
        'FRES':      'FRES.L',
        'ABRA':      'ABRA.TO',
        'PE&OLES*':  'PE&OLES.MX',
        'PE&OLES':   'PE&OLES.MX',
        'KGH':       'KGH.WA',
        'BOL':       'BOL.ST',
        'ARTG':      'ARTG.V',
        'HOC':       'HOC.L',
        'GGD':       'GGD.TO',
        'KCN':       'KCN.AX',
        'SVL':       'SVL.AX',
        'HSTR':      'HSTR.V',
        'GSVR':      'GSVR.V',
        'SVRS':      'SVRS.V',
        'TUD':       'TUD.V',
        'AAG':       'AAG.V',
        'AGMR':      'AGMR.TO',
        'CKG':       'CKG.V',
        'CUU':       'CUU.V',
        'FPC':       'FPC.V',
        'IPT':       'IPT.V',
        'WAM':       'WAM.V',
        'MFRISCOA':  'MFRISCOA-1.MX',
        'WVM':       'WVM.V',
        'AMM':       'AMM.V',
        'MKR':       'MKR.AX',
        'DSV':       'DSVSF',
        'FVI':       'FVI.TO',
        'SCZ':       'SCZ.V',
        'NUAG':      'NUAG.TO',
        'ITR':       'ITR.V',
        'SLVR':      'SLVR.V',
        'ASL':       'ASL.AX',
        'BRC':       'BRC.V',
        'USL':       'USL.AX',
        'SOSI':      'SOSI.ST',
        'GORO':      'GORO',
        'AAG':       'AAG.V',
        'K':         'KGC',
    }

    static_tickers = {'VOLCABC1', 'APX.PS'}

    updates = {}
    for ticker in tickers:
        if ticker in static_tickers:
            print(f"Skipping {ticker} (static data, not fetching from yfinance)")
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
    
    # Update the HTML
    updated_html = update_known_data(html_content, updates)
    
    # Write back
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(updated_html)
    
    print(f"Updated {html_file} with new data.")

if __name__ == "__main__":
    main()