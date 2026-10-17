"""Refresh the local Strategy A / Strategy B trackers' market data.

Pulls the full daily history of every underlying and the latest closes of every
leveraged ETF from Yahoo (yfinance), then writes data/prices.js, which the HTML
pages load with a plain <script src> tag (a page opened from disk cannot fetch
Yahoo directly: the chart API sends no CORS headers, and browsers block fetch()
of local files too, so a .js file is the one thing that works from file://).

Per pair the file carries, for the UNDERLYING: last close, its date, the
all-time intraday high including today (drawdown reference), the all-time high
BEFORE today's session (Strategy A sell reference: "the ATH from before the
drawdown"), the previous completed calendar month's intraday high (Strategy B
sell reference), and for the ETF: last close and its date.  Plus a FeedStatus per
row (OK / ERROR with the reason) so the pages' FEED CHECK tab can show what came
back.  Nothing here decides anything: the pages compute drawdowns, ladders and
actions from these numbers and the trades the user records in the browser.

    python refresh.py            # all 17 pairs
    python refresh.py --pairs TQQQ/QQQ MUU/MU
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "prices.js"

# ETF -> underlying.  TQQQ / UPRO belong to Strategy A; they ride along in
# Strategy B as disabled reference rows, exactly as in the workbooks.
PAIRS: list[tuple[str, str]] = [
    ("TQQQ", "QQQ"), ("UPRO", "SPY"),
    ("MUU", "MU"), ("SNXX", "SNDK"), ("LITX", "LITE"), ("NVDL", "NVDA"),
    ("AMDL", "AMD"), ("GGLL", "GOOGL"), ("AMZU", "AMZN"), ("MSFU", "MSFT"),
    ("GDXU", "GDX"), ("NBIG", "NBIS"), ("CRWL", "CRWD"), ("METU", "META"),
    ("AAPX", "AAPL"), ("PLTU", "PLTR"), ("NOWL", "NOW"),
]


def _frame(raw: pd.DataFrame, sym: str) -> pd.DataFrame | None:
    """One ticker's OHLC out of a bulk download, rows with a close only."""
    try:
        df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
    except KeyError:
        return None
    df = df.dropna(subset=["Close"])
    return df if len(df) else None


def _month_high(df: pd.DataFrame, asof: pd.Timestamp) -> tuple[float | None, str | None]:
    """Highest intraday High of the calendar month before the one `asof` is in."""
    first_of_this = asof.replace(day=1)
    prev_end = first_of_this - pd.Timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
    m = df[(idx >= prev_start.normalize()) & (idx <= prev_end.normalize() + pd.Timedelta(hours=23))]
    if not len(m):
        return None, None
    return float(m["High"].max()), prev_start.strftime("%Y-%m")


def build(pairs: list[tuple[str, str]]) -> dict:
    unds = sorted({u for _, u in pairs})
    etfs = sorted({e for e, _ in pairs})
    # auto_adjust=False: split-adjusted but not dividend-adjusted, so highs and
    # closes are the prices that printed (the ATH convention the handover uses).
    und_raw = yf.download(unds, period="max", interval="1d", auto_adjust=False,
                          group_by="ticker", progress=False, threads=True)
    etf_raw = yf.download(etfs, period="1mo", interval="1d", auto_adjust=False,
                          group_by="ticker", progress=False, threads=True)
    rows = []
    for etf, und in pairs:
        row: dict = {"etf": etf, "underlying": und}
        u = _frame(und_raw, und)
        e = _frame(etf_raw, etf)
        problems = []
        if u is None:
            problems.append(f"no {und} history")
        else:
            last = u.iloc[-1]
            asof = u.index[-1]
            before = u.iloc[:-1]
            row.update({
                "und_close": round(float(last["Close"]), 4),
                "und_date": asof.strftime("%Y-%m-%d"),
                "und_high_today": round(float(last["High"]), 4),
                "ath": round(float(u["High"].max()), 4),
                "ath_date": u["High"].idxmax().strftime("%Y-%m-%d"),
                "ath_prior": round(float(before["High"].max()), 4) if len(before) else None,
                "history_start": u.index[0].strftime("%Y-%m-%d"),
                "sessions": int(len(u)),
            })
            mh, mlabel = _month_high(u, asof)
            row["prev_month_high"] = round(mh, 4) if mh is not None else None
            row["prev_month"] = mlabel
            if mh is None:
                problems.append("no bars in the previous month")
        if e is None:
            problems.append(f"no {etf} quote")
        else:
            row["etf_close"] = round(float(e["Close"].iloc[-1]), 4)
            row["etf_date"] = e.index[-1].strftime("%Y-%m-%d")
            if u is not None and row["etf_date"] != row["und_date"]:
                problems.append(f"ETF quote {row['etf_date']} vs underlying {row['und_date']}")
        row["status"] = "OK" if not problems else "ERROR"
        row["note"] = "; ".join(problems)
        rows.append(row)
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": "Yahoo Finance via yfinance (daily bars, split-adjusted, dividends not adjusted)",
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pairs", nargs="*", help="ETF/UNDERLYING pairs to refresh (default: all)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    pairs = PAIRS
    if a.pairs:
        pairs = [tuple(p.upper().split("/")) for p in a.pairs]  # type: ignore[misc]
    data = build(pairs)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("// Generated by strategy_trackers/refresh.py; do not edit by hand.\n"
                     "window.TRACKER_PRICES = " + json.dumps(data, indent=1) + ";\n",
                     encoding="utf-8")
    bad = [r for r in data["rows"] if r["status"] != "OK"]
    print(f"wrote {a.out} ({len(data['rows'])} pairs, {len(bad)} with problems) at {data['generated_at']}")
    for r in data["rows"]:
        flag = "" if r["status"] == "OK" else f"  <-- {r['note']}"
        drop = ""
        if r.get("und_close") and r.get("ath"):
            drop = f"{(r['und_close'] / r['ath'] - 1) * 100:+.1f}% from ATH"
        print(f"  {r['etf']:<5} {r['underlying']:<5} close {r.get('und_close', '-'):>9} on {r.get('und_date', '-')}  "
              f"ATH {r.get('ath', '-'):>9}  prev-month high {r.get('prev_month_high', '-'):>9}  {drop}{flag}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
