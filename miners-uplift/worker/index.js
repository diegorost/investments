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
  return Math.round(n * 100) / 100;
}

async function fetchEtf(ticker) {
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
    const pct = ((ath - current) / ath) * 100;
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
    if (url.pathname !== "/api/etf-prices") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    const entries = await Promise.all(
      Object.entries(ETFS).map(async ([cls, ticker]) => [cls, await fetchEtf(ticker)])
    );

    return new Response(JSON.stringify({ etfs: Object.fromEntries(entries) }), {
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
