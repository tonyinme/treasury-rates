from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional
import csv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .calculations import accrued_interest, analyze, current_yield, price_from_yield
from .data_loader import DataValidationError, SampleDataProvider, TreasuryAuctionHistoryProvider, TreasuryDirectAuctionProvider, TreasuryDailyRateProvider, load_csv

ROOT=Path(__file__).parent.parent
app=FastAPI(title="Treasury Income Screener")
try:
    securities=TreasuryDirectAuctionProvider().fetch_securities()
except DataValidationError:
    securities=SampleDataProvider().fetch_securities()
try:
    market_rates,market_rate_status=TreasuryDailyRateProvider().fetch_rates()
except DataValidationError:
    market_rates,market_rate_status={},"DAILY MARKET ESTIMATES UNAVAILABLE"
try:
    auction_history,auction_history_status=TreasuryAuctionHistoryProvider().fetch_history()
except DataValidationError:
    auction_history,auction_history_status={},"AUCTION HISTORY UNAVAILABLE"

def rows(settlement: date, investment: float, price_basis: str):
    results=[]
    for sec in securities:
        if sec.maturity_date<=settlement: continue
        row=analyze(sec,settlement,investment,price_basis)
        rate=market_rates.get(sec.security_type)
        if rate:
            rate_date=date.fromisoformat(rate["date"])
            estimate_price=price_from_yield(rate["yield"],sec.coupon_rate,sec.maturity_date,rate_date)
            row["market_estimate"]={"date":rate["date"],"price":estimate_price,"ytm":rate["yield"],
              "current_yield":current_yield(sec.coupon_rate,estimate_price) if sec.coupon_rate else None,
              "annual_cash_per_100k":100000/estimate_price*100*sec.coupon_rate,
              "status":market_rate_status}
        else: row["market_estimate"]=None
        results.append(row)
    return results

@app.get("/api/securities")
def get_securities(settlement:date=Query(default_factory=date.today),investment:float=100000,price_basis:str="ask"):
    if investment<=0 or price_basis not in {"ask","bid","midpoint","last"}: raise HTTPException(400,"Invalid calculation settings")
    return {"items":rows(settlement,investment,price_basis),"sample_data":all("SAMPLE" in s.data_status.upper() for s in securities)}

@app.get("/api/securities/{cusip}")
def get_security(cusip:str,settlement:date=Query(default_factory=date.today),investment:float=100000,price_basis:str="ask"):
    sec=next((s for s in securities if s.CUSIP==cusip),None)
    if not sec: raise HTTPException(404,"CUSIP not found")
    return analyze(sec,settlement,investment,price_basis)

@app.get("/api/summary")
def get_summary(settlement:date=Query(default_factory=date.today),investment:float=100000,price_basis:str="ask"):
    data=rows(settlement,investment,price_basis)
    def best(key,rev=True):
        vals=[r for r in data if r.get(key) is not None]
        return max(vals,key=lambda x:x[key]) if rev and vals else min(vals,key=lambda x:x[key]) if vals else None
    return {"highest_current_yield":best("current_yield_clean"),"highest_annual_cash":best("annual_coupon_cash"),
      "highest_ytm":best("ytm"),"lowest_duration":best("modified_duration",False),
      "largest_gain_to_par":best("principal_gain_loss_dirty"),"count":len(data)}

@app.get("/api/auction-history")
def get_auction_history():
    return {"series":auction_history,"status":auction_history_status,"available_since":"1998-07-27"}

@app.post("/api/import")
async def import_csv(file:UploadFile=File(...)):
    global securities
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Please upload a CSV file")
    try: incoming=load_csv(BytesIO(await file.read()))
    except DataValidationError as exc: raise HTTPException(422,str(exc))
    securities=incoming
    return {"imported":len(securities),"sample_data":all("SAMPLE" in s.data_status.upper() for s in securities)}

@app.get("/api/export")
def export(settlement:date=Query(default_factory=date.today),investment:float=100000,price_basis:str="ask",
           cusips:Optional[str]=None):
    data=rows(settlement,investment,price_basis)
    if cusips:
        selected=set(cusips.split(",")); data=[r for r in data if r["CUSIP"] in selected]
    out=StringIO()
    if data:
        w=csv.DictWriter(out,fieldnames=data[0].keys()); w.writeheader(); w.writerows(data)
    return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",
      headers={"Content-Disposition":"attachment; filename=treasury_screener_export.csv"})

app.mount("/static",StaticFiles(directory=ROOT/"app"/"static"),name="static")
@app.get("/")
def index(): return FileResponse(ROOT/"app"/"static"/"index.html")
