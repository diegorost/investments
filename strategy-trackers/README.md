# Strategy Trackers

Interactive replacements for the two Excel workbooks described in the
17 Oct 2026 handover (`Strategy_A_Simplified.xlsx`, `Strategy_B_Individual_ETFs_Flexible_MUU.xlsx`).
Deployed as a static Cloudflare Pages site plus a tiny Cloudflare Worker that
fetches live Yahoo Finance data — runs at $0/month, same pattern as
`miners-uplift` / `stock-exchanges` / `ticker-analysis`. The original local,
Python-refreshed version lives in `../strategy-trackers-py`.

| File | What it is |
|---|---|
| `index.html` | Landing page linking the two trackers |
| `strategy_a.html` | Strategy A: TQQQ / QQQ (from 10%), UPRO / SPY (from 5%); SELL ALL when the underlying's close is back at the pre-drawdown ATH |
| `strategy_b.html` | Strategy B: 15 ETFs (TQQQ / UPRO present as disabled reference rows); SELL ALL when the underlying's close reaches the previous completed month's intraday high |
| `shared/tracker.js`, `shared/tracker.css` | The one script and stylesheet both pages use |
| `worker/index.js`, `worker/wrangler.toml` | Cloudflare Worker: fetches Yahoo chart data for every underlying (full daily history) and ETF (latest close), computes ATH / prior ATH / previous-month high, serves it as JSON at `/api/prices` |

## Daily use

1. Open either tracker page. Prices load automatically from the Worker on page load.
2. Click **Refresh prices** in the header any time to re-fetch live (e.g. right after the US close).
3. START HERE: check the quote dates and DROP FROM ATH, then WHAT TO DO
   (CONSIDER BUYING / SELL ALL / WAIT; CHECK DATA is a data warning, not a signal).
4. Trade with the broker yourself, then record the confirmed fill on TRADES.

Tabs mirror the workbooks: START HERE, DASHBOARD (tiles + drawdown ladders), TRADES,
BUY LEVELS (rung status BUY / USED / WAIT / PAUSED / DISABLED / NO DATA / OVER CAP),
SETTINGS (starting cash, reference lot, optional allocation cap, enable / pause / first tier
per pair, cash flows), FEED CHECK (what the data holds, manual overrides per field),
RULES (the logic in words).

## Where the data lives

* Market data: fetched live from the Worker's `/api/prices` endpoint (Yahoo Finance chart
  API, no caching — every page load and every "Refresh prices" click re-fetches). Nothing is
  written to disk.
* Your entries (trades, settings, cash flows, manual price overrides): the browser's
  localStorage, one key per strategy (`strategy_tracker:A`, `strategy_tracker:B`).
  **Export backup** on the header downloads it as JSON; **Import backup** restores it.
  Opening the page in another browser or profile starts from the handover
  state (Strategy A blank; Strategy B with the two 16 Oct 2026 LITX buys, 14 shares,
  tracked cash -$380.12 until starting cash is entered).

## Deploying

* **Worker**: `cd worker && npx wrangler deploy` (deploys `strategy-trackers-api`, no KV/secrets needed).
* **Pages**: deploy this folder (minus `worker/`) to Cloudflare Pages, same as the other
  trackers in this repo.
* Update `API_BASE` in `shared/tracker.js` if the Worker's deployed URL differs from
  `https://strategy-trackers-api.<your-subdomain>.workers.dev`.

## Rules implemented

* Drawdown = underlying daily close / underlying intraday ATH (split-adjusted, not
  dividend-adjusted) - 1. Buying zone active from the first tier; rungs every 5 points,
  up to 16, below 100%. Reached / used rungs are information; repeat buys at the same rung
  in any size are allowed, and there is no duplicate-level check.
* Sell reference A = max intraday high before the latest session. B = max intraday high of
  the previous calendar month (advances automatically with the quote date).
* SELL ALL = close >= sell reference and tracked shares > 0; outranks CONSIDER BUYING.
* Cycle key = ticker + cycle number, advancing when a SELL takes tracked shares to zero.
* Tracked cash = starting cash + cash flows + sells (gross - fees) - buys (gross + fees).
* Stale flag: quote date older than the last completed weekday session (holidays unknown).

Decision support only; not financial advice.
