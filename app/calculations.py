"""Treasury note/bond analytics. Rates are decimal values; prices are per $100 face."""
from calendar import monthrange
from datetime import date
from math import isfinite

def add_months(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 + months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(d.day, monthrange(year, month + 1)[1]))

def coupon_dates(maturity: date, settlement: date):
    d, dates = maturity, []
    while d > settlement:
        dates.append(d)
        d = add_months(d, -6)
    return sorted(dates)

def coupon_period(maturity: date, settlement: date):
    nxt = maturity
    while add_months(nxt, -6) > settlement:
        nxt = add_months(nxt, -6)
    return add_months(nxt, -6), nxt

def accrued_interest(coupon_rate: float, maturity: date, settlement: date) -> float:
    if settlement >= maturity:
        return 0.0
    prev, nxt = coupon_period(maturity, settlement)
    fraction = (settlement - prev).days / (nxt - prev).days  # Actual/Actual in coupon period
    return coupon_rate * 100 / 2 * fraction

def annual_coupon_per_100(coupon_rate): return coupon_rate * 100
def current_yield(coupon_rate, clean_price): return annual_coupon_per_100(coupon_rate) / clean_price
def cash_yield_dirty(coupon_rate, dirty_price): return annual_coupon_per_100(coupon_rate) / dirty_price
def face_value_purchased(investment, price): return investment / price * 100
def annual_coupon_income(face, coupon_rate): return face * coupon_rate
def gain_loss_to_par(face, price): return face - face * price / 100

def years_remaining(settlement, maturity): return max(0.0, (maturity - settlement).days / 365.2425)

def _cashflows(coupon_rate, maturity, settlement):
    dates = coupon_dates(maturity, settlement)
    coupon = coupon_rate * 100 / 2
    return [(d, coupon + (100 if d == maturity else 0)) for d in dates]

def _pv(ytm, coupon_rate, maturity, settlement):
    base = 1 + ytm / 2
    if base <= 0: return float("inf")
    return sum(cf / base ** (2 * (d - settlement).days / 365.2425)
               for d, cf in _cashflows(coupon_rate, maturity, settlement))

def price_from_yield(ytm, coupon_rate, maturity, settlement):
    """Estimated clean price per $100 from a benchmark yield."""
    dirty=_pv(ytm,coupon_rate,maturity,settlement)
    return dirty-accrued_interest(coupon_rate,maturity,settlement)

def yield_to_maturity(dirty_price, coupon_rate, maturity, settlement):
    if settlement >= maturity or dirty_price <= 0: return None
    lo, hi = -1.9, 2.0
    flo, fhi = _pv(lo, coupon_rate, maturity, settlement)-dirty_price, _pv(hi, coupon_rate, maturity, settlement)-dirty_price
    if flo * fhi > 0: return None
    for _ in range(160):
        mid = (lo + hi) / 2
        fm = _pv(mid, coupon_rate, maturity, settlement)-dirty_price
        if abs(fm) < 1e-11: return mid
        if flo * fm <= 0: hi = mid
        else: lo, flo = mid, fm
    return (lo + hi) / 2

def duration(ytm, dirty_price, coupon_rate, maturity, settlement):
    if ytm is None or dirty_price <= 0: return (None, None)
    flows = _cashflows(coupon_rate, maturity, settlement)
    pv_times = []
    for d, cf in flows:
        t = (d-settlement).days / 365.2425
        pv_times.append((t, cf / (1 + ytm/2) ** (2*t)))
    mac = sum(t*pv for t,pv in pv_times) / sum(pv for _,pv in pv_times)
    return mac, mac / (1 + ytm/2)

def analyze(sec, settlement, investment, price_basis="ask"):
    price_map = {"bid":sec.clean_bid, "ask":sec.clean_ask, "midpoint":(sec.clean_bid+sec.clean_ask)/2, "last":sec.last_price}
    price = price_map.get(price_basis, sec.clean_ask)
    ai = accrued_interest(sec.coupon_rate, sec.maturity_date, settlement)
    dirty = price + ai
    face = face_value_purchased(investment, dirty)
    annual = annual_coupon_income(face, sec.coupon_rate)
    ytm = yield_to_maturity(dirty, sec.coupon_rate, sec.maturity_date, settlement)
    mac, mod = duration(ytm, dirty, sec.coupon_rate, sec.maturity_date, settlement)
    yrs = years_remaining(settlement, sec.maturity_date)
    clean_gl, dirty_gl = gain_loss_to_par(face, price), gain_loss_to_par(face, dirty)
    compound = ((100/price)**(1/yrs)-1) if yrs > 0 and price > 0 else None
    return {
      "CUSIP":sec.CUSIP, "security_type":sec.security_type, "maturity_date":sec.maturity_date.isoformat(),
      "years_remaining":yrs, "coupon_rate":sec.coupon_rate, "clean_bid":sec.clean_bid,
      "clean_ask":sec.clean_ask, "selected_clean_price":price, "bid_ask_spread":sec.clean_ask-sec.clean_bid,
      "accrued_interest":ai, "dirty_ask":dirty, "current_yield_clean":current_yield(sec.coupon_rate,price),
      "cash_yield_dirty":cash_yield_dirty(sec.coupon_rate,dirty), "ytm":ytm,
      "annual_coupon_cash":annual, "semiannual_coupon_cash":annual/2, "monthly_equivalent":annual/12,
      "face_value_purchased":face, "maturity_value":face, "principal_gain_loss_clean":clean_gl,
      "principal_gain_loss_dirty":dirty_gl, "simple_annual_pull_to_par":dirty_gl/yrs if yrs else None,
      "compound_pull_to_par":compound, "macaulay_duration":mac, "modified_duration":mod,
      "estimated_pct_change_up_1":-mod*0.01 if mod is not None else None,
      "estimated_loss_up_1":mod*0.01*investment if mod is not None else None,
      "initial_settlement_cost":investment, "quote_timestamp":sec.quote_timestamp.isoformat(),
      "source":sec.source, "data_status":sec.data_status,
      "auction_date":sec.auction_date.isoformat() if sec.auction_date else None,
      "auction_yield":sec.auction_yield,
    }
