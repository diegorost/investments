# Strategy Trackers (local HTML)

Interactive, browser-only replacements for the two Excel workbooks described in the
17 Oct 2026 handover (`Strategy_A_Simplified.xlsx`, `Strategy_B_Individual_ETFs_Flexible_MUU.xlsx`).
Open the pages straight from disk; no server, no account, nothing leaves the computer.

| File | What it is |
|---|---|
| `index.html` | Landing page linking the two trackers |
| `strategy_a.html` | Strategy A: TQQQ / QQQ (from 10%), UPRO / SPY (from 5%); SELL ALL when the underlying's close is back at the pre-drawdown ATH |
| `strategy_b.html` | Strategy B: 15 ETFs (TQQQ / UPRO present as disabled reference rows); SELL ALL when the underlying's close reaches the previous completed month's intraday high |
| `shared/tracker.js`, `shared/tracker.css` | The one script and stylesheet both pages use |
| `refresh.py` | Yahoo (yfinance) -> `data/prices.js` |
| `data/prices.js` | The market data the pages read (generated; rerun the refresh after each close) |

## Daily use

1. After the US close: `python refresh.py` in this folder (about 10 s), then reload the page.
2. START HERE: check the quote dates and DROP FROM ATH, then WHAT TO DO
   (CONSIDER BUYING / SELL ALL / WAIT; CHECK DATA is a data warning, not a signal).
3. Trade with the broker yourself, then record the confirmed fill on TRADES.

Tabs mirror the workbooks: START HERE, DASHBOARD (tiles + drawdown ladders), TRADES,
BUY LEVELS (rung status BUY / USED / WAIT / PAUSED / DISABLED / NO DATA / OVER CAP),
SETTINGS (starting cash, reference lot, optional allocation cap, enable / pause / first tier
per pair, cash flows), FEED CHECK (what the data file holds, manual overrides per field),
RULES (the logic in words).

## Where the data lives

* Market data: `data/prices.js`, rewritten by `refresh.py`. A page opened from `file://`
  cannot call Yahoo itself (no CORS headers) and cannot `fetch()` a local JSON file either,
  so the data ships as a `.js` file loaded by a `<script>` tag.
* Your entries (trades, settings, cash flows, manual price overrides): the browser's
  localStorage, one key per strategy (`strategy_tracker:A`, `strategy_tracker:B`).
  **Export backup** on the header downloads it as JSON; **Import backup** restores it.
  Moving the folder, or opening it in another browser or profile, starts from the handover
  state (Strategy A blank; Strategy B with the two 16 Oct 2026 LITX buys, 14 shares,
  tracked cash -$380.12 until starting cash is entered).

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
