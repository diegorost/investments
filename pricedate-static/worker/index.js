const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

async function fetchSeries(ticker, period1, period2) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?period1=${period1}&period2=${period2}&interval=1d`;
  const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
  if (!r.ok) throw new Error(`Failed to fetch data for ${ticker}`);
  const data = await r.json();
  const result = data.chart && data.chart.result && data.chart.result[0];
  if (!result) return [];
  const timestamps = result.timestamp || [];
  const quote = result.indicators.quote[0];
  return timestamps.map((ts, i) => ({
    date: new Date(ts * 1000).toISOString().slice(0, 10),
    high: quote.high[i],
    low: quote.low[i],
  })).filter((r) => r.high != null && r.low != null);
}

async function getPrice(ticker, dateStr) {
  const d = new Date(dateStr + "T00:00:00Z");
  const end = new Date(d);
  end.setUTCDate(end.getUTCDate() + 7);
  const period1 = Math.floor(d.getTime() / 1000);
  const period2 = Math.floor(end.getTime() / 1000);

  const rows = await fetchSeries(ticker, period1, period2);
  const row = rows.find((r) => r.date >= dateStr);
  if (row) return { price: (row.high + row.low) / 2, date: row.date };
  throw new Error(`No data for ${ticker} on or after ${dateStr}`);
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/price") {
      return jsonResponse({ ok: false, error: "Not found" }, 404);
    }

    const raw = (url.searchParams.get("ticker") || "").trim().toUpperCase();
    const entry = (url.searchParams.get("entry") || "").trim();
    const exit_ = (url.searchParams.get("exit") || "").trim();
    const tickers = raw.split(",").map((t) => t.trim()).filter(Boolean);

    if (!tickers.length || !entry || !exit_) {
      return jsonResponse({ ok: false, error: "ticker, entry and exit are required" }, 400);
    }

    try {
      const results = [];
      for (const t of tickers) {
        const e = await getPrice(t, entry);
        const x = await getPrice(t, exit_);
        results.push({
          ticker: t,
          entry_price: e.price,
          entry_date: e.date,
          exit_price: x.price,
          exit_date: x.date,
          return_pct: (x.price / e.price - 1) * 100,
        });
      }
      return jsonResponse({ ok: true, results });
    } catch (err) {
      return jsonResponse({ ok: false, error: err.message }, 400);
    }
  },
};
