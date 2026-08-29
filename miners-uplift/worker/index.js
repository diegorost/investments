const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const ETFS = {
  ring: "RING",
  auau: "AUAU",
  gdx: "GDX",
  gdxj: "GDXJ",
  slvp: "SLVP",
  sil: "SIL",
  silj: "SILJ",
};

function round2(n) {
  if (n == null || !Number.isFinite(n)) return null;
  return Math.round(n * 100) / 100;
}

function safePercentChange(change, base) {
  if (change == null || base == null || base === 0) return null;
  const pct = (change / base) * 100;
  return Number.isFinite(pct) ? pct : null;
}

async function fetchQuote(ticker) {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?range=1y&interval=1d`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    const data = await r.json();
    const result = data.chart && data.chart.result && data.chart.result[0];
    const meta = result && result.meta;
    const current = meta && meta.regularMarketPrice;
    const highs = (result.indicators.quote[0].high || []).filter((h) => h != null);
    const ath = highs.length ? Math.max(...highs) : null;
    if (current == null || ath == null) return { current: null, ath: null, pct: null };
    const pct = safePercentChange(ath - current, ath);
    return { current: round2(current), ath: round2(ath), pct: round2(pct) };
  } catch {
    return { current: null, ath: null, pct: null };
  }
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/api/etf-prices") {
      const entries = await Promise.all(
        Object.entries(ETFS).map(async ([cls, ticker]) => [cls, await fetchQuote(ticker)])
      );
      return new Response(JSON.stringify({ etfs: Object.fromEntries(entries) }), {
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    // Batch quotes for individual ETF holdings: /api/stock-prices?tickers=NEM,AEM,B
    if (url.pathname === "/api/stock-prices") {
      const raw = url.searchParams.get("tickers") || "";
      const tickers = [...new Set(raw.split(",").map((t) => t.trim()).filter(Boolean))].slice(0, 50);
      const entries = await Promise.all(
        tickers.map(async (t) => [t, await fetchQuote(t)])
      );
      return new Response(JSON.stringify({ prices: Object.fromEntries(entries) }), {
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    return new Response(JSON.stringify({ error: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
