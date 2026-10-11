# Singles and Doubles Screener

A standalone screener for mid and large cap stocks (market cap over $2B) that looks for
"singles" (about +10%) and "doubles" (+20%) within 2 to 6 weeks. Inspired by the idea of
four 20% moves a year doubling a portfolio. It is separate from the home run (pre parabolic)
and Weinstein stage screeners and changes nothing in them.

## What is here

- `scripts/update_prices.py` adds new trading days from Nasdaq's public API (`--full` refetches ten years). It checks for splits and refetches any stock whose history changed.
- `scripts/store.py` reads and writes the price store, `data/prices/YYYY-MM.csv.gz`, one small file per month.
- `scripts/build_universe.py` builds `data/universe.json`, the stocks over $2B.
- `scripts/engine.py` builds the weekly panel: trend, momentum, Weinstein style stage, sector stage, market regime, trade outcomes.
- `scripts/screener.py` writes the candidates and odds tables to `output/`.
- `scripts/exits.py dashboard` writes the exit rule study.
- `scripts/attention.py` tracks the weekly plan and any positions in `data/positions.json`, and writes the daily flags. `--set-plan` freezes the top 25 per tier.
- `scripts/render_site.py` builds `site/index.html`, the standalone dashboard.
- `research/` holds the exploratory analysis, including the entry timing study.

## Schedule (GitHub Actions)

- Weekly plan, Mondays 15:00 UTC (after the open): refresh universe and full history, rebuild, freeze the plan.
- Daily check, weekdays 22:00 UTC (after the close): add new days, rebuild, flag anything needing attention.
- Both commit their results to this repo. Cloudflare Pages serves the `site/` folder.

## Your positions

List trades you actually took in `data/positions.json`, for example
`[{"symbol": "ABC", "tier": "Double", "date": "2026-10-12", "entry": 50.0, "stop": 46.0, "target": 60.0}]`.
The daily check then tracks them like plan names.

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

