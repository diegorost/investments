const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const YAHOO_MARKETS = [
  // US indices & volatility
  { name: "S&P 500",            ticker: "^GSPC",     region: "US",      flag: "us" },
  { name: "NASDAQ",              ticker: "^IXIC",     region: "US",      flag: "us" },
  { name: "Dow Jones",           ticker: "^DJI",      region: "US",      flag: "us" },
  { name: "Russell 2000",        ticker: "^RUT",      region: "US",      flag: "us" },
  { name: "VIX",                 ticker: "^VIX",      region: "US",      flag: "us" },
  // Chile stocks
  { name: "LATAM Airlines",      ticker: "LTM.SN",        region: "CHILE", flag: "cl" },
  { name: "Itaú Chile",          ticker: "ITAUCL.SN",     region: "CHILE", flag: "cl" },
  { name: "CFMITNIPSA",          ticker: "CFMITNIPSA.SN", region: "CHILE", flag: "cl" },
  // Futures
  { name: "Gold",                ticker: "GC=F",      region: "FUTURES", icon: "🥇" },
  { name: "Silver",              ticker: "SI=F",      region: "FUTURES", icon: "🥈" },
  { name: "Copper",              ticker: "HG=F",      region: "FUTURES", icon: "🟤", dec: 4 },
  { name: "Oil (WTI)",           ticker: "CL=F",      region: "FUTURES", icon: "🛢️" },
  { name: "US Dollar Index",     ticker: "DX-Y.NYB",  region: "FUTURES", icon: "💵", dec: 3 },
  { name: "Bitcoin",             ticker: "BTC-USD",   region: "FUTURES", icon: "₿" },
  // Forex (1 USD = X) — flags: [base, quote]
  { name: "USD / CLP",           ticker: "USDCLP=X",  region: "FOREX", flags: ["us", "cl"] },
  { name: "USD / EUR",           ticker: "USDEUR=X",  region: "FOREX", flags: ["us", "eu"], dec: 4 },
  { name: "USD / JPY",           ticker: "USDJPY=X",  region: "FOREX", flags: ["us", "jp"] },
  { name: "USD / GBP",           ticker: "USDGBP=X",  region: "FOREX", flags: ["us", "gb"], dec: 4 },
  { name: "USD / BRL",           ticker: "USDBRL=X",  region: "FOREX", flags: ["us", "br"], dec: 4 },
  { name: "USD / ARS",           ticker: "USDARS=X",  region: "FOREX", flags: ["us", "ar"] },
  // Miners
  { name: "AEM",   ticker: "AEM",  region: "MINERS", icon: "🥇" },
  { name: "BTG",   ticker: "BTG",  region: "MINERS", icon: "🥇" },
  { name: "IAG",   ticker: "IAG",  region: "MINERS", icon: "🥇" },
  { name: "RGLD",  ticker: "RGLD", region: "MINERS", icon: "🥇" },
  { name: "AG",    ticker: "AG",   region: "MINERS", icon: "🥈" },
  { name: "SILJ",  ticker: "SILJ", region: "MINERS", icon: "🥈" },
  { name: "JNUG",  ticker: "JNUG", region: "MINERS", icon: "🥇" },
  { name: "NUGT",  ticker: "NUGT", region: "MINERS", icon: "🥇" },
  { name: "GDXU",  ticker: "GDXU", region: "MINERS", icon: "🥇" },
];


const HIDDEN_TICKERS = new Set(["CHILE", "CHILE.SN", "BSANTANDER", "BSANTANDER.SN"]);
const HIDDEN_NAMES = new Set(["CHILE", "BANCO DE CHILE", "BSANTANDER", "SANTANDER CHILE"]);

function round(n, d) {
  if (n == null || !Number.isFinite(n)) return null;
  const f = Math.pow(10, d);
  return Math.round(n * f) / f;
}

function safePercentChange(change, base) {
  if (change == null || base == null || base === 0) return null;
  const pct = (change / base) * 100;
  return Number.isFinite(pct) ? pct : null;
}

async function fetchOne(market) {
  const d = market.dec || 2;
  const needsIntradayPreviousClose = market.ticker.endsWith(".SN");
  const base = {
    region: market.region,
    ticker: market.ticker,
    flag: market.flag,
    flags: market.flags,
    icon: market.icon,
    dec: d,
  };
  try {
    const range = needsIntradayPreviousClose ? "1d" : "5d";
    const interval = needsIntradayPreviousClose ? "1m" : "1d";
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(market.ticker)}?range=${range}&interval=${interval}`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    const data = await r.json();
    const result = data.chart && data.chart.result && data.chart.result[0];
    const meta = result && result.meta;
    const closes = result && result.indicators && result.indicators.quote[0].close;
    const current = meta && meta.regularMarketPrice != null
      ? meta.regularMarketPrice
      : closes && closes.length
        ? closes[closes.length - 1]
        : null;
    const prev = needsIntradayPreviousClose
      ? ((meta && meta.previousClose != null)
        ? meta.previousClose
        : (meta && meta.chartPreviousClose != null)
          ? meta.chartPreviousClose
          : (closes && closes.length > 1 && closes[closes.length - 2] != null)
            ? closes[closes.length - 2]
            : null)
      : ((closes && closes.length > 1 && closes[closes.length - 2] != null)
        ? closes[closes.length - 2]
        : (meta && meta.previousClose != null)
          ? meta.previousClose
          : (meta && meta.chartPreviousClose != null)
            ? meta.chartPreviousClose
            : null);
    if (current == null) {
      return { name: market.name, value: null, prev: null, change: null, pct: null, error: "No data", ...base };
    }
    const change = prev != null ? current - prev : null;
    const pct = safePercentChange(change, prev);
    return {
      name: market.name,
      value: round(current, d),
      prev: prev != null ? round(prev, d) : null,
      change: change != null ? round(change, d) : null,
      pct: pct != null ? round(pct, 2) : null,
      error: null,
      ...base,
    };
  } catch {
    return { name: market.name, value: null, prev: null, change: null, pct: null, error: "Error fetching data", ...base };
  }
}

async function fetchYahoo() {
  const markets = await Promise.all(YAHOO_MARKETS.map(fetchOne));
  const visibleMarkets = markets.filter((m) => {
    const ticker = (m.ticker || "").toUpperCase();
    const name = (m.name || "").toUpperCase();
    return !HIDDEN_TICKERS.has(ticker) && !HIDDEN_NAMES.has(name);
  });

  const gold = visibleMarkets.find((m) => m.name === "Gold");
  const silver = visibleMarkets.find((m) => m.name === "Silver");
  if (gold && silver && gold.value && silver.value) {
    const gsrVal = gold.value / silver.value;
    const gsrPrev = gold.prev && silver.prev ? gold.prev / silver.prev : null;
    const gsrChange = gsrPrev != null ? gsrVal - gsrPrev : null;
    const gsrPct = safePercentChange(gsrChange, gsrPrev);
    const gsrEntry = {
      name: "Gold/Silver Ratio (GSR)",
      icon: "📊",
      value: round(gsrVal, 2),
      change: gsrChange != null ? round(gsrChange, 2) : null,
      pct: gsrPct != null ? round(gsrPct, 2) : null,
      error: null,
      region: "FUTURES",
      dec: 2,
    };
    const silverIdx = visibleMarkets.findIndex((m) => m.name === "Silver");
    visibleMarkets.splice(silverIdx + 1, 0, gsrEntry);
  }

  return {
    markets: visibleMarkets,
    updated: new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC",
  };
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/api/yahoo") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    const data = await fetchYahoo();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
