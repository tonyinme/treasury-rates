from io import StringIO
import pytest
from app.data_loader import load_csv, DataValidationError, SampleDataProvider, TreasuryAuctionHistoryProvider, TreasuryDirectAuctionProvider, TreasuryDailyRateProvider

def test_sample_schema_and_count(): assert len(SampleDataProvider().fetch_securities())==14
def test_missing_schema():
    with pytest.raises(DataValidationError,match="Missing columns"): load_csv(StringIO("CUSIP\nx\n"))
def test_invalid_values():
    bad="""CUSIP,security_type,issue_date,maturity_date,coupon_rate,clean_bid,clean_ask,last_price,quote_timestamp,source,data_status
x,Note,2020-01-01,2030-01-01,nope,99,100,100,2026-01-01T00:00:00,s,d"""
    with pytest.raises(DataValidationError,match="Invalid row"): load_csv(StringIO(bad))

def test_auction_provider_selects_latest_for_each_term():
    provider=TreasuryDirectAuctionProvider()
    rows=[]
    for term in provider.TERMS:
        kind="Bill" if "Week" in term else "Note" if term not in {"20-Year","30-Year"} else "Bond"
        base={"cusip":term,"securityType":kind,"securityTerm":term,"originalSecurityTerm":term,
              "auctionDate":"2026-01-01T00:00:00","issueDate":"2026-01-02T00:00:00",
              "maturityDate":"2030-01-01T00:00:00","highPrice":"99","interestRate":"",
              "highInvestmentRate":"4","highYield":""}
        rows.append(base)
    rows.append({**rows[0],"auctionDate":"2026-02-01T00:00:00","highPrice":"98"})
    selected=provider._select_latest(rows)
    assert len(selected)==14
    assert selected[0]["highPrice"]=="98"

def test_daily_rate_xml_parser():
    xml=b"""<feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
    xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
    <entry><content><m:properties><d:NEW_DATE>2026-07-28T00:00:00</d:NEW_DATE>
    <d:BC_10YEAR>4.69</d:BC_10YEAR></m:properties></content></entry></feed>"""
    assert TreasuryDailyRateProvider._entries(xml)==[{"NEW_DATE":"2026-07-28T00:00:00","BC_10YEAR":"4.69"}]

def test_auction_history_maps_rates_and_terms():
    provider=TreasuryAuctionHistoryProvider()
    records=[
      {"cusip":"bill","securityType":"Bill","securityTerm":"4-Week","originalSecurityTerm":"17-Week",
       "auctionDate":"2020-01-02T00:00:00","highInvestmentRate":"1.55","highYield":"","tips":"No"},
      {"cusip":"note","securityType":"Note","securityTerm":"9-Year 10-Month",
       "originalSecurityTerm":"10-Year","auctionDate":"2020-01-03T00:00:00",
       "highInvestmentRate":"","highYield":"1.61","tips":"No"},
      {"cusip":"tips","securityType":"Note","securityTerm":"10-Year","originalSecurityTerm":"10-Year",
       "auctionDate":"2020-01-04T00:00:00","highYield":"0.20","tips":"Yes"},
    ]
    history=provider._convert(records)
    assert history["4-Week Bill"]==[["2020-01-02",1.55]]
    assert history["10-Year Note"]==[["2020-01-03",1.61]]
