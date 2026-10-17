/* Strategy Trackers API: replaces refresh.py. Fetches Yahoo chart data for every
   underlying (full daily history) and every leveraged ETF (latest close), and
   computes exactly what the pages' localStorage trackers need: last close, ATH
   (intraday, split-adjusted, not dividend-adjusted), the ATH from before the
   latest session, the previous completed month's intraday high, and the ETF's
   latest close. Shape matches the old data/prices.js's window.TRACKER_PRICES. */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// ETF -> underlying. TQQQ / UPRO belong to Strategy A; they ride along in
// Strategy B as disabled reference rows, exactly as in the workbooks.
const PAIRS = [
  ["TQQQ", "QQQ"], ["UPRO", "SPY"],
  ["MUU", "MU"], ["SNXX", "SNDK"], ["LITX", "LITE"], ["NVDL", "NVDA"],
  ["AMDL", "AMD"], ["GGLL", "GOOGL"], ["AMZU", "AMZN"], ["MSFU", "MSFT"],
  ["GDXU", "GDX"], ["NBIG", "NBIS"], ["CRWL", "CRWD"], ["METU", "META"],
  ["AAPX", "AAPL"], ["PLTU", "PLTR"], ["NOWL", "NOW"],
  ["BEX", "BE"], ["GEVX", "GEV"],
];

function round4(n) {
  if (n == null || !Number.isFinite(n)) return null;
  return Math.round(n * 10000) / 10000;
}

// Daily bars from Yahoo are timestamped at the exchange's local session; shift
// by gmtoffset so the date component matches the trading day (same convention
// yfinance/pandas give refresh.py).
function dateStr(ts, gmtoffset) {
  const d = new Date((ts + (gmtoffset || 0)) * 1000);
  return d.toISOString().slice(0, 10);
}

async function fetchChart(ticker, range) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?range=${range}&interval=1d`;
  const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
  const data = await r.json();
  const result = data.chart && data.chart.result && data.chart.result[0];
  if (!result) return null;
  const ts = result.timestamp || [];
  const q = result.indicators.quote[0] || {};
  const gmtoffset = result.meta && result.meta.gmtoffset;
  const bars = [];
  for (let i = 0; i < ts.length; i++) {
    if (q.close[i] == null) continue;
    bars.push({ date: dateStr(ts[i], gmtoffset), close: q.close[i], high: q.high[i] != null ? q.high[i] : q.close[i] });
  }
  return bars.length ? bars : null;
}

// Highest intraday High of the calendar month before the one `asofDate` is in.
function monthHigh(bars, asofDate) {
  const y = +asofDate.slice(0, 4), m = +asofDate.slice(5, 7);
  const prevY = m === 1 ? y - 1 : y, prevM = m === 1 ? 12 : m - 1;
  const label = `${prevY}-${String(prevM).padStart(2, "0")}`;
  const inMonth = bars.filter((b) => b.date.slice(0, 7) === label);
  if (!inMonth.length) return [null, null];
  return [Math.max(...inMonth.map((b) => b.high)), label];
}

async function buildRow(etf, und) {
  const row = { etf, underlying: und };
  const problems = [];
  const [undBars, etfBars] = await Promise.all([
    fetchChart(und, "max").catch(() => null),
    fetchChart(etf, "1mo").catch(() => null),
  ]);
  if (!undBars) {
    problems.push(`no ${und} history`);
  } else {
    const last = undBars[undBars.length - 1];
    const before = undBars.slice(0, -1);
    const athBar = undBars.reduce((a, b) => (b.high > a.high ? b : a));
    row.und_close = round4(last.close);
    row.und_date = last.date;
    row.und_high_today = round4(last.high);
    row.ath = round4(athBar.high);
    row.ath_date = athBar.date;
    row.ath_prior = before.length ? round4(Math.max(...before.map((b) => b.high))) : null;
    row.history_start = undBars[0].date;
    row.sessions = undBars.length;
    const [mh, mlabel] = monthHigh(undBars, last.date);
    row.prev_month_high = round4(mh);
    row.prev_month = mlabel;
    if (mh == null) problems.push("no bars in the previous month");
  }
  if (!etfBars) {
    problems.push(`no ${etf} quote`);
  } else {
    const last = etfBars[etfBars.length - 1];
    row.etf_close = round4(last.close);
    row.etf_date = last.date;
    if (undBars && row.etf_date !== row.und_date) {
      problems.push(`ETF quote ${row.etf_date} vs underlying ${row.und_date}`);
    }
  }
  row.status = problems.length ? "ERROR" : "OK";
  row.note = problems.join("; ");
  return row;
}

async function buildAll() {
  const rows = await Promise.all(PAIRS.map(([etf, und]) => buildRow(etf, und)));
  return {
    generated_at: new Date().toISOString(),
    source: "Yahoo Finance chart API (daily bars, split-adjusted, dividends not adjusted)",
    rows,
  };
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }
    const url = new URL(request.url);
    if (url.pathname !== "/api/prices") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }
    const data = await buildAll();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
