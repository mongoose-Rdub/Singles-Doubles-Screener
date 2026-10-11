# Singles and Doubles Screener

A standalone screener for mid and large cap stocks (market cap over $2B) that looks for
"singles" (about +10%) and "doubles" (+20%) within 2 to 6 weeks. Inspired by the idea of
four 20% moves a year doubling a portfolio. It is separate from the home run (pre parabolic)
and Weinstein stage screeners and changes nothing in them.

## What is here

- `scripts/build_universe.py` builds `data/universe.json` from the Nasdaq screener.
- `scripts/fetch_data.py` pulls ten years of daily bars from the Nasdaq historical API.
- `scripts/engine.py` builds the weekly panel: trend, momentum, Weinstein style stage, sector stage, market regime, and trade outcomes.
- `scripts/screener.py` produces the candidate list and the odds tables in `output/`.
- `scripts/exits.py` is the exit rule study.
- `research/` holds the exploratory analysis scripts behind the findings.
- `data/prices/` holds ten years of daily prices as monthly compressed files.
- `dashboard/` holds the dashboard page.

## Method in brief

- Entry at the weekly close, hold up to 30 trading days.
- Stop is the lower of 10 day low (less 0.5%) or 2 ATR below the close, never tighter than 3%.
- Double tier: ATR% of 4.0% or more, target +20%. Single tier: ATR% from 2.8% to under 4.0%, target +10%.
- Filters: price $10 or more, 20 day dollar volume $20M or more, market cap over $2B.
- Priority score is an ordering aid only: 60 times relative strength percentile plus 40 times range rank inside the tier.

## Findings

- Win rate rises with volatility (ATR%). Ranking inside a tier raises win rate mostly by using wider stops, not by adding profit.
- Stock stage, sector stage, SPY regime, trend filters, past move record, setups and volume showed no signal that held in both 2017 to 2021 and 2022 to 2026.
- Exit rules did not beat buy and hold per day held.

## Caveats

- Survivorship bias: the universe is stocks over $2B today, which inflates absolute profit. Trust comparisons, not absolute returns.
- Costs, taxes and earnings dates are not modeled.
- Stocks with fewer than about 260 trading days of history are skipped.

## Status

Scripts currently read and write local pickle files. Incremental daily updates, a standalone
dashboard page and any scheduling are not built yet. Nothing runs automatically.
