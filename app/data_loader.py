from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
import json
import pandas as pd
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from xml.etree import ElementTree
from .models import REQUIRED_FIELDS, TreasurySecurity

class DataValidationError(ValueError): pass

def load_csv(path_or_buffer):
    try: df = pd.read_csv(path_or_buffer)
    except Exception as exc: raise DataValidationError(f"Could not read CSV: {exc}") from exc
    missing = [c for c in REQUIRED_FIELDS if c not in df.columns]
    if missing: raise DataValidationError("Missing columns: " + ", ".join(missing))
    if df.empty: raise DataValidationError("CSV contains no securities")
    records=[]
    for i,row in df.iterrows():
        try:
            coupon=float(row.coupon_rate); bid=float(row.clean_bid); ask=float(row.clean_ask); last=float(row.last_price)
            if not (0 <= coupon <= .25 and bid > 0 and ask > 0 and last > 0): raise ValueError("out-of-range numeric value")
            records.append(TreasurySecurity(
              str(row.CUSIP).strip(),str(row.security_type),date.fromisoformat(str(row.issue_date)),
              date.fromisoformat(str(row.maturity_date)),coupon,bid,ask,last,
              datetime.fromisoformat(str(row.quote_timestamp).replace("Z","+00:00")),
              str(row.source),str(row.data_status)))
        except Exception as exc: raise DataValidationError(f"Invalid row {i+2}: {exc}") from exc
    return records

class TreasuryDataProvider(ABC):
    @abstractmethod
    def fetch_securities(self): ...

class CsvDataProvider(TreasuryDataProvider):
    def __init__(self,path): self.path=path
    def fetch_securities(self): return load_csv(self.path)

class SampleDataProvider(CsvDataProvider):
    def __init__(self): super().__init__(Path(__file__).parent.parent/"data"/"treasuries_sample.csv")

class TreasuryDirectAuctionProvider(TreasuryDataProvider):
    """Latest official auction result for each standard Treasury term."""
    BASE = "https://www.treasurydirect.gov/TA_WS/securities/auctioned?format=json&type="
    TERMS = ["4-Week","6-Week","8-Week","13-Week","17-Week","26-Week","52-Week",
             "2-Year","3-Year","5-Year","7-Year","10-Year","20-Year","30-Year"]

    def __init__(self, cache_path=None, timeout=20):
        self.cache_path = Path(cache_path or Path(__file__).parent.parent/"data"/"treasury_auction_cache.json")
        self.timeout = timeout

    @staticmethod
    def _date(value): return date.fromisoformat(value[:10])

    def _download(self):
        records=[]
        for kind in ("Bill","Note","Bond"):
            request=Request(self.BASE+kind,headers={"User-Agent":"TreasuryIncomeScreener/1.0"})
            with urlopen(request,timeout=self.timeout) as response:
                records.extend(json.load(response))
        return records

    def _select_latest(self, records):
        latest={}
        for row in records:
            # Bill reopenings retain a longer original term, so their current
            # auction tenor is securityTerm. Notes/bonds use original tenor.
            term=(row.get("securityTerm") if row.get("securityType")=="Bill"
                  else row.get("originalSecurityTerm") or row.get("securityTerm"))
            if term not in self.TERMS or not row.get("auctionDate") or not row.get("highPrice"):
                continue
            if term not in latest or row["auctionDate"] > latest[term]["auctionDate"]:
                latest[term]=row
        missing=[term for term in self.TERMS if term not in latest]
        if missing: raise DataValidationError("TreasuryDirect did not return: "+", ".join(missing))
        return [latest[term] for term in self.TERMS]

    def _convert(self, rows, status):
        result=[]
        for row in rows:
            term=(row.get("securityTerm") if row.get("securityType")=="Bill"
                  else row.get("originalSecurityTerm") or row["securityTerm"])
            coupon=float(row.get("interestRate") or 0)/100
            auction_yield=float(row.get("highInvestmentRate") or row.get("highYield") or 0)/100
            price=float(row["highPrice"])
            auction_date=self._date(row["auctionDate"])
            result.append(TreasurySecurity(
                row["cusip"],f"{term} {row['securityType']}",self._date(row["issueDate"]),
                self._date(row["maturityDate"]),coupon,price,price,price,
                datetime.fromisoformat(row["auctionDate"]), "U.S. TreasuryDirect", status,
                auction_date, auction_yield))
        return result

    def fetch_securities(self):
        try:
            rows=self._select_latest(self._download())
            self.cache_path.write_text(json.dumps(rows,indent=2))
            return self._convert(rows,"OFFICIAL AUCTION RESULT")
        except Exception as exc:
            if self.cache_path.exists():
                rows=json.loads(self.cache_path.read_text())
                return self._convert(rows,"CACHED OFFICIAL AUCTION RESULT")
            raise DataValidationError(f"TreasuryDirect data unavailable and no cache exists: {exc}") from exc

class TreasuryAuctionHistoryProvider:
    """Official nominal Treasury auction rates from TreasuryDirect's query feed."""
    BASE = "https://www.treasurydirect.gov/TA_WS/securities/jqsearch"
    TERMS = [f"{term} Bill" if "Week" in term else
             f"{term} Bond" if term in {"20-Year", "30-Year"} else f"{term} Note"
             for term in TreasuryDirectAuctionProvider.TERMS]

    def __init__(self, cache_path=None, timeout=30, page_size=1000):
        self.cache_path = Path(cache_path or Path(__file__).parent.parent/"data"/"treasury_auction_history_cache.json")
        self.timeout = timeout
        self.page_size = page_size

    def _page(self, page_number):
        query=urlencode({"format":"json","pagenum":page_number,"pagesize":self.page_size})
        request=Request(f"{self.BASE}?{query}",headers={"User-Agent":"TreasuryIncomeScreener/1.0"})
        with urlopen(request,timeout=self.timeout) as response:
            return json.load(response)

    @staticmethod
    def _term(row):
        base=(row.get("securityTerm") if row.get("securityType")=="Bill"
              else row.get("originalSecurityTerm") or row.get("securityTerm"))
        suffix={"Bill":"Bill","Note":"Note","Bond":"Bond"}.get(row.get("securityType"))
        return f"{base} {suffix}" if base and suffix else None

    def _convert(self, records):
        history={term:[] for term in self.TERMS}
        seen=set()
        for row in records:
            term=self._term(row)
            rate=row.get("highInvestmentRate") if row.get("securityType")=="Bill" else row.get("highYield")
            auction_date=(row.get("auctionDate") or "")[:10]
            if term not in history or not auction_date or not rate or row.get("tips")=="Yes":
                continue
            key=(term,auction_date,row.get("cusip"))
            if key in seen: continue
            seen.add(key)
            history[term].append([auction_date,float(rate)])
        for points in history.values():
            points.sort(key=lambda point:point[0])
        return history

    def _download(self):
        first=self._page(0)
        records=list(first.get("securityList",[]))
        total=int(first.get("totalResultsCount",len(records)))
        pages=(total+self.page_size-1)//self.page_size
        for page in range(1,pages):
            records.extend(self._page(page).get("securityList",[]))
        return self._convert(records)

    def fetch_history(self):
        try:
            history=self._download()
            if not any(history.values()): raise DataValidationError("Auction history feed was empty")
            self.cache_path.write_text(json.dumps(history,separators=(",",":")))
            return history,"OFFICIAL TREASURY AUCTION HISTORY"
        except Exception as exc:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text()),"CACHED OFFICIAL TREASURY AUCTION HISTORY"
            raise DataValidationError(f"Treasury auction history unavailable and no cache exists: {exc}") from exc

class TreasuryDailyRateProvider:
    """Official prior-business-day bill and par-yield-curve observations."""
    BASE="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    BILL_FIELDS={"4-Week Bill":"ROUND_B1_YIELD_4WK_2","6-Week Bill":"ROUND_B1_YIELD_6WK_2",
      "8-Week Bill":"ROUND_B1_YIELD_8WK_2","13-Week Bill":"ROUND_B1_YIELD_13WK_2",
      "17-Week Bill":"ROUND_B1_YIELD_17WK_2","26-Week Bill":"ROUND_B1_YIELD_26WK_2",
      "52-Week Bill":"ROUND_B1_YIELD_52WK_2"}
    CURVE_FIELDS={"2-Year Note":"BC_2YEAR","3-Year Note":"BC_3YEAR","5-Year Note":"BC_5YEAR",
      "7-Year Note":"BC_7YEAR","10-Year Note":"BC_10YEAR","20-Year Bond":"BC_20YEAR",
      "30-Year Bond":"BC_30YEAR"}

    def __init__(self,cache_path=None,timeout=20):
        self.cache_path=Path(cache_path or Path(__file__).parent.parent/"data"/"treasury_daily_rates_cache.json")
        self.timeout=timeout

    @staticmethod
    def _entries(payload):
        root=ElementTree.fromstring(payload)
        entries=[]
        for entry in root.iter():
            if entry.tag.split("}")[-1]!="properties": continue
            entries.append({child.tag.split("}")[-1]:child.text for child in entry})
        return entries

    def _get(self,data_key):
        url=f"{self.BASE}?data={data_key}&field_tdr_date_value={date.today().year}"
        request=Request(url,headers={"User-Agent":"TreasuryIncomeScreener/1.0"})
        with urlopen(request,timeout=self.timeout) as response:
            return self._entries(response.read())

    @staticmethod
    def _latest(rows,date_field):
        usable=[r for r in rows if r.get(date_field)]
        if not usable: raise DataValidationError("Daily Treasury rate feed was empty")
        return max(usable,key=lambda r:r[date_field])

    def fetch_rates(self):
        try:
            bills=self._latest(self._get("daily_treasury_bill_rates"),"INDEX_DATE")
            curve=self._latest(self._get("daily_treasury_yield_curve"),"NEW_DATE")
            rates={}
            for term,field in self.BILL_FIELDS.items():
                rates[term]={"date":bills["INDEX_DATE"][:10],"yield":float(bills[field])/100}
            for term,field in self.CURVE_FIELDS.items():
                rates[term]={"date":curve["NEW_DATE"][:10],"yield":float(curve[field])/100}
            self.cache_path.write_text(json.dumps(rates,indent=2))
            return rates,"OFFICIAL DAILY TREASURY RATES"
        except Exception as exc:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text()),"CACHED OFFICIAL DAILY TREASURY RATES"
            raise DataValidationError(f"Daily Treasury rates unavailable and no cache exists: {exc}") from exc
