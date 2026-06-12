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

function round(n, d) {
  const f = Math.pow(10, d);
  return Math.round(n * f) / f;
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

async function fetchChart(ticker, params) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?${params}`;
  const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
  const data = await r.json();
  const result = data.chart && data.chart.result && data.chart.result[0];
  if (!result) return null;
  return result;
}

async function fetchName(ticker) {
  try {
    const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(ticker)}&quotesCount=1`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    const data = await r.json();
    const quote = data.quotes && data.quotes[0];
    return (quote && (quote.longname || quote.shortname)) || null;
  } catch {
    return null;
  }
}

function dayKey(ts) {
  const d = new Date(ts * 1000);
  return `${d.getUTCFullYear()}-${d.getUTCMonth()}-${d.getUTCDate()}`;
}

function extractRows(result) {
  if (!result) return [];
  const timestamps = result.timestamp || [];
  const quote = (result.indicators && result.indicators.quote && result.indicators.quote[0]) || {};

  const rows = [];
  for (let i = 0; i < timestamps.length; i++) {
    const close = quote.close && quote.close[i];
    const high = quote.high && quote.high[i];
    const low = quote.low && quote.low[i];
    const open = quote.open && quote.open[i];
    const volume = (quote.volume && quote.volume[i]) || 0;
    if (close == null || high == null || low == null || open == null) continue;
    rows.push({ ts: timestamps[i], close, high, low, open, volume });
  }
  return rows;
}

async function fetchDaily(ticker) {
  const [maxResult, recentResult, name] = await Promise.all([
    fetchChart(ticker, "range=max&interval=1d").catch(() => null),
    fetchChart(ticker, "range=2y&interval=1d").catch(() => null),
    fetchName(ticker),
  ]);
  const meta = (maxResult && maxResult.meta) || (recentResult && recentResult.meta) || {};

  // range=max returns coarse (monthly) candles for older history on Yahoo's
  // chart API, so merge in range=2y daily candles, which take precedence
  // for any overlapping dates.
  const merged = new Map();
  for (const r of extractRows(maxResult)) merged.set(dayKey(r.ts), r);
  for (const r of extractRows(recentResult)) merged.set(dayKey(r.ts), r);

  const sorted = [...merged.values()].sort((a, b) => a.ts - b.ts);

  const rows = sorted.map((r) => {
    const d = new Date(r.ts * 1000);
    return {
      date: `${pad2(d.getUTCMonth() + 1)}/${pad2(d.getUTCDate())}/${d.getUTCFullYear()}`,
      price: round(r.close, 4),
      high: round(r.high, 4),
      low: round(r.low, 4),
      open: round(r.open, 4),
      vol: r.volume.toLocaleString("en-US"),
      volRaw: Math.round(r.volume),
      change: "",
    };
  });

  if (rows.length === 0) return null;

  return { name: name || meta.longName || meta.shortName || ticker, rows };
}

async function fetchIntraday(ticker, interval) {
  const valid = new Set(["1m", "2m", "5m", "15m", "30m", "60m", "90m"]);
  if (!valid.has(interval)) interval = "5m";

  const result = await fetchChart(ticker, `range=1d&interval=${interval}`);
  if (!result) return null;

  const timestamps = result.timestamp || [];
  const quote = (result.indicators && result.indicators.quote && result.indicators.quote[0]) || {};

  const rows = [];
  for (let i = 0; i < timestamps.length; i++) {
    const close = quote.close && quote.close[i];
    const high = quote.high && quote.high[i];
    const low = quote.low && quote.low[i];
    const open = quote.open && quote.open[i];
    const volume = (quote.volume && quote.volume[i]) || 0;
    if (close == null || high == null || low == null || open == null) continue;

    rows.push({
      ts: timestamps[i] * 1000,
      price: round(close, 4),
      high: round(high, 4),
      low: round(low, 4),
      open: round(open, 4),
      vol: volume.toLocaleString("en-US"),
    });
  }

  if (rows.length === 0) return null;
  return rows;
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/api/ticker") {
      const ticker = (url.searchParams.get("ticker") || "").trim().toUpperCase();
      if (!ticker) return jsonResponse({ error: "no ticker" }, 400);
      const result = await fetchDaily(ticker);
      if (!result) return jsonResponse({ error: "not found" }, 404);
      return jsonResponse({ ticker, name: result.name, data: result.rows });
    }

    if (url.pathname === "/api/intraday") {
      const ticker = (url.searchParams.get("ticker") || "").trim().toUpperCase();
      const interval = url.searchParams.get("interval") || "5m";
      if (!ticker) return jsonResponse({ error: "no ticker" }, 400);
      const rows = await fetchIntraday(ticker, interval);
      if (!rows) return jsonResponse({ error: "no data" }, 404);
      return jsonResponse({ ticker, data: rows });
    }

    return jsonResponse({ error: "Not found" }, 404);
  },
};
