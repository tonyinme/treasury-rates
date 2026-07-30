"""Build a static GitHub Pages edition from official Treasury data."""
from datetime import date
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.calculations import analyze, current_yield, price_from_yield
from app.data_loader import TreasuryDailyRateProvider, TreasuryDirectAuctionProvider

OUT = ROOT / "site"
TERMS = [
    "4-Week Bill", "6-Week Bill", "8-Week Bill", "13-Week Bill",
    "17-Week Bill", "26-Week Bill", "52-Week Bill", "2-Year Note",
    "3-Year Note", "5-Year Note", "7-Year Note", "10-Year Note",
    "20-Year Bond", "30-Year Bond",
]

def pct(value):
    return "—" if value is None else f"{value * 100:.3f}%"

def short_date(value):
    if not value:
        return "—"
    parsed = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"

def build():
    securities = TreasuryDirectAuctionProvider().fetch_securities()
    rates, rate_status = TreasuryDailyRateProvider().fetch_rates()
    securities.sort(key=lambda security: TERMS.index(security.security_type))
    rows, auction_dates = [], []
    for security in securities:
        auction = analyze(security, date.today(), 100000, "ask")
        auction_dates.append(security.auction_date)
        rate = rates[security.security_type]
        rate_date = date.fromisoformat(rate["date"])
        market_price = price_from_yield(
            rate["yield"], security.coupon_rate, security.maturity_date, rate_date
        )
        market_current = current_yield(security.coupon_rate, market_price) if security.coupon_rate else None
        rows.append(f"""
        <tr class="auction-row">
          <td rowspan="2" class="term"><strong>{escape(security.security_type)}</strong><span>{escape(security.CUSIP)}</span></td>
          <td class="text-col"><span class="marker auction">Auction</span></td>
          <td class="date-col">{short_date(security.auction_date)}</td>
          <td class="date-col">{short_date(security.maturity_date)}</td>
          <td>{pct(security.coupon_rate)}</td><td>{security.clean_ask:.3f}</td>
          <td>{pct(auction["current_yield_clean"]) if security.coupon_rate else "—"}</td>
          <td>{pct(security.auction_yield or auction["ytm"])}</td>
        </tr>
        <tr class="market-row">
          <td class="text-col"><span class="marker market">Market estimate</span></td>
          <td class="date-col">{short_date(rate_date)}</td>
          <td class="date-col">{short_date(security.maturity_date)}</td>
          <td>{pct(security.coupon_rate)}</td><td>{market_price:.3f}</td>
          <td>{pct(market_current)}</td><td>{pct(rate["yield"])}</td>
        </tr>""")

    css = (ROOT / "app" / "static" / "styles.css").read_text()
    latest_rate = max(date.fromisoformat(value["date"]) for value in rates.values())
    status = (
        f"{len(securities)} standard Treasury terms · auctions "
        f"{short_date(min(auction_dates))} through {short_date(max(auction_dates))} · "
        f"daily rates {short_date(latest_rate)}"
    )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Official U.S. Treasury auction results and daily market-rate estimates.">
<title>Treasury Auction &amp; Market Rates</title><style>{css}</style></head>
<body><main>
<header><div><p class="eyebrow">U.S. TREASURY COMPARISON</p>
<h1>Treasury auction &amp; market rates</h1>
<p class="intro">Official auction results paired with a daily market-derived price estimate.</p>
</div><span class="sample official">OFFICIAL TREASURY DATA</span></header>
<section class="table-card" aria-labelledby="table-title">
<div class="table-heading"><div><h2 id="table-title">Treasury terms</h2>
<p>Two rows per term: issuance and market estimate</p></div><p class="as-of">Official daily data</p></div>
<div class="table-wrap"><table><thead><tr>
<th class="text-col">Term</th><th class="text-col">Market</th>
<th class="date-col">Auction / rate date</th><th class="date-col">Maturity date</th>
<th>Coupon</th><th>Price</th><th>Current yield</th><th>YTM</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p id="status" role="status">{status}</p></section>
<section class="notes" aria-label="Data notes"><h2>What the markers mean</h2><div class="note-grid">
<p><span class="marker auction">Auction</span><strong>Official Treasury issuance result.</strong>
The date is the auction date and the price is the auction price.</p>
<p><span class="marker market">Market estimate</span><strong>Prior-business-day Treasury rate.</strong>
Price is modeled from the official daily yield, coupon, and maturity—not a live bid or ask.</p>
</div><p class="bill-note">Treasury bills have no coupon. Their estimates use Treasury’s daily
coupon-equivalent bill yields; note and bond estimates use the daily par yield curve.</p></section>
<footer>Current yield is not total return. Market-estimate prices are modeled reference values,
not executable quotes. This is not investment advice.</footer>
</main></body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    (OUT / ".nojekyll").write_text("")
    print(f"Built {OUT / 'index.html'} using {rate_status}")

if __name__ == "__main__":
    build()
