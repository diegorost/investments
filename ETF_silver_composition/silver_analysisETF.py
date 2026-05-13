import yfinance as yf
import re
import sys
from datetime import datetime

def extract_silj_tickers(html_content):
    """
    Extract tickers from the SILJ data in the HTML.
    """
    pattern = r'const siljData = (\[[\s\S]*?\]);'
    match = re.search(pattern, html_content)
    if not match:
        return []
    data_str = match.group(1)
    ticker_matches = re.findall(r"ticker:'([^']+)'", data_str)
    return ticker_matches

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
        hist = stock.history(period='max')
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
    html_file = 'silver_analysisETF.html'
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"File not found: {html_file}")
        sys.exit(1)
    
    tickers = extract_silj_tickers(html_content)
    
    if not tickers:
        print("No SILJ tickers found in the HTML file.")
        sys.exit(1)
    
    print(f"Found {len(tickers)} SILJ tickers. Fetching updated data from yfinance...")
    
    updates = {}
    for ticker in tickers:
        current, ath = get_stock_data(ticker)
        if current is not None and ath is not None:
            pct = ((ath - current) / ath) * 100
        else:
            pct = None
        updates[ticker] = (current, ath, pct)
        print(f"Updated {ticker}: Current={current}, ATH={ath}, %={pct}")
    
    # Update the HTML
    updated_html = update_known_data(html_content, updates)
    
    # Write back
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(updated_html)
    
    print(f"Updated {html_file} with new data.")

if __name__ == "__main__":
    main()