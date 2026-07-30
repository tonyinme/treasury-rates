# Treasury Income Table

A deliberately simple local comparison table showing the latest official
TreasuryDirect auction for every standard term from 4 weeks through 30 years.
It displays auction date, coupon, auction price, current yield, and the
published auction yield.

Each auction row is paired with a **Market estimate** row. The app retrieves the
latest official Daily Treasury Bill Rates and Daily Treasury Par Yield Curve
Rates, then prices the auction security from that benchmark yield, coupon, and
maturity. These are modeled prior-business-day reference values—not live,
executable secondary-market quotes.

> Auction prices are issuance results, not live secondary-market ask quotes.
> This is an analytical tool, not investment advice.

## Run on macOS

Prerequisites: Python 3.12 or newer.

```bash
chmod +x run.sh
./run.sh
```

The script creates `.venv` when needed, installs pinned dependencies, and starts
the server. Open <http://127.0.0.1:8000>. Stop it with `Control-C`.

The equivalent manual setup is:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run tests with:

```bash
source .venv/bin/activate
pytest
```

## GitHub Pages

Run `python scripts/build_static.py` to generate the public static edition.
The included GitHub Actions workflow refreshes official data on weekday
evenings, builds the page, and deploys it to GitHub Pages. It can also be
refreshed immediately from the repository's Actions tab with **Run workflow**.

## Data and API

At startup the app retrieves the latest Bill, Note, and Bond auction records
from TreasuryDirect's public `TA_WS` JSON service. It selects the newest auction
for each standard term and saves it to `data/treasury_auction_cache.json`. If
TreasuryDirect is temporarily unavailable, the last successful official results
are used and clearly labeled as cached. The bundled hypothetical CSV is only an
initial emergency fallback when no official cache exists.

The app also retrieves the official daily-rate XML feeds and caches the latest
observations in `data/treasury_daily_rates_cache.json`. Bill estimates use the
published coupon-equivalent rate for their exact term. Notes and bonds use their
matching constant-maturity par-yield-curve point.

The interface intentionally stays focused on the table. The underlying API
still supports CSV import and export for future use.

## Fields

`CUSIP`, `security_type`, `issue_date`, `maturity_date`, `coupon_rate`,
`clean_bid`, `clean_ask`, `last_price`, `quote_timestamp`, `source`, and
`data_status` are required. Coupon is stored as a decimal (`0.0475` means 4.75%).
Prices are dollars per $100 face. Dates and timestamps use ISO 8601. Bid, ask,
and last inputs are clean prices.

## Formulas and conventions

- Annual coupon per $100 = coupon rate × $100.
- Face purchased = investment ÷ dirty price × $100. The MVP shows fractional
  face value for analytical comparison; it does not round to tradable increments.
- Current yield = annual coupon per $100 ÷ selected clean price.
- Cash yield = annual coupon per $100 ÷ dirty settlement price.
- Dirty price = selected clean price + accrued interest per $100.
- Gain/loss to par = face value − clean or dirty purchase cost.
- Compound pull to par = `(100 / clean price)^(1 / years) − 1`. This is a price
  return measure, not YTM, and is not simply added to current yield.
- YTM discounts every remaining semiannual coupon and principal cash flow to the
  dirty price, solving numerically. It is annualized on a semiannual
  bond-equivalent basis.
- Macaulay duration is the PV-weighted cash-flow time. Modified duration divides
  it by `(1 + YTM/2)`. The 1 percentage-point rate shock uses
  `−modified duration × 0.01` and is only a first-order approximation.

Coupon dates are derived backward in six-month increments from maturity.
Accrued interest uses Actual/Actual within the current coupon period:
semiannual coupon × actual days accrued ÷ actual days in the coupon period.
Calculations use the user-selected settlement date and default to ask price.

### Simplifications and limitations

This MVP does not model ex-coupon trading, business-day settlement adjustments,
holidays, odd first/last coupons, taxes, commissions, reinvestment rates,
convexity, minimum denominations, or transaction-specific rounding. It assumes
standard fixed-rate Treasury notes/bonds, two regular coupons per year, promised
payments, and maturity dates that anchor coupon dates. Monthly cash is an
equivalent only; actual coupons are semiannual. Duration shock results can be
inaccurate for large moves. Failed calculations return `N/A` rather than a
fabricated value.

## API

- `GET /api/securities`
- `GET /api/securities/{cusip}`
- `GET /api/summary`
- `POST /api/import`
- `GET /api/export`

Calculation endpoints accept `settlement`, `investment`, and `price_basis`
(`ask`, `bid`, `midpoint`, or `last`) query parameters.

## Adding a real data provider

Implement `TreasuryDataProvider.fetch_securities()` in `app/data_loader.py` and
return validated `TreasurySecurity` records. Then select that provider in
`app/main.py`; the calculation and UI layers do not need to change. Plausible
future adapters include TreasuryDirect security metadata, Treasury Fiscal Data,
licensed IBKR quotes, and normalized broker-download CSVs. Metadata sources and
market-quote sources should remain distinct, with timestamps and status labels
preserved. Web scraping is intentionally out of scope.
