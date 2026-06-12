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

function fmtDate(d) {
  return d.toISOString().slice(0, 10).replace(/-/g, "");
}

function parseStooqCsv(text) {
  const lines = text.trim().split("\n");
  if (lines.length < 2 || lines[0].startsWith("No data")) return [];
  const header = lines[0].split(",");
  const idx = {};
  header.forEach((h, i) => (idx[h.trim()] = i));
  return lines
    .slice(1)
    .map((line) => {
      const cols = line.split(",");
      return {
        date: cols[idx["Date"]],
        high: parseFloat(cols[idx["High"]]),
        low: parseFloat(cols[idx["Low"]]),
      };
    })
    .filter((r) => r.date && !isNaN(r.high) && !isNaN(r.low));
}

async function fetchSeries(symbol, start, end) {
  const url = `https://stooq.com/q/d/l/?s=${encodeURIComponent(symbol)}&d1=${start}&d2=${end}&i=d`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Failed to fetch data for ${symbol}`);
  const text = await r.text();
  return parseStooqCsv(text);
}

async function getPrice(ticker, dateStr) {
  const d = new Date(dateStr + "T00:00:00Z");
  const end = new Date(d);
  end.setUTCDate(end.getUTCDate() + 7);
  const start = fmtDate(d);
  const endStr = fmtDate(end);

  const candidates = [ticker.toLowerCase(), `${ticker.toLowerCase()}.us`];
  for (const sym of candidates) {
    const rows = await fetchSeries(sym, start, endStr);
    const row = rows.find((r) => r.date >= dateStr);
    if (row) return { price: (row.high + row.low) / 2, date: row.date };
  }
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
