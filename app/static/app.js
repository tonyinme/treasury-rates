const termOrder = ["4-Week Bill","6-Week Bill","8-Week Bill","13-Week Bill","17-Week Bill","26-Week Bill","52-Week Bill","2-Year Note","3-Year Note","5-Year Note","7-Year Note","10-Year Note","20-Year Bond","30-Year Bond"];
const pct = value => value == null ? "—" : (value * 100).toFixed(3) + "%";
const shortDate = value => {
  if (!value) return "—";
  const [year,month,day] = value.slice(0,10).split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", {month:"short",day:"numeric",year:"numeric",timeZone:"UTC"})
    .format(new Date(Date.UTC(year,month-1,day)));
};

async function load() {
  const status = document.querySelector("#status");
  try {
    const response = await fetch("/api/securities?investment=100000&price_basis=ask");
    if (!response.ok) throw new Error("The table could not be loaded.");
    const {items} = await response.json();
    items.sort((a,b) => termOrder.indexOf(a.security_type) - termOrder.indexOf(b.security_type));
    document.querySelector("#rows").innerHTML = items.map(row => {
      const market = row.market_estimate;
      return `
      <tr class="auction-row">
        <td rowspan="2" class="term"><strong>${row.security_type}</strong>${row.auction_result_url
          ? `<a href="${row.auction_result_url}" target="_blank" rel="noopener" title="Open official Treasury auction result for ${row.CUSIP}">${row.CUSIP}<span class="external-mark" aria-hidden="true">↗</span></a>`
          : `<span>${row.CUSIP}</span>`}</td>
        <td class="text-col"><span class="marker auction">Auction</span></td>
        <td class="date-col">${shortDate(row.auction_date)}</td>
        <td class="date-col">${shortDate(row.maturity_date)}</td>
        <td>${pct(row.coupon_rate)}</td>
        <td>${row.clean_ask.toFixed(3)}</td>
        <td>${row.coupon_rate === 0 ? "—" : pct(row.current_yield_clean)}</td>
        <td>${pct(row.auction_yield ?? row.ytm)}</td>
      </tr>
      <tr class="trace-row ${market ? "" : "unavailable"}">
        <td class="text-col"><span class="marker market">Market estimate</span></td>
        <td class="date-col">${shortDate(market?.date)}</td>
        <td class="date-col">${shortDate(row.maturity_date)}</td>
        <td>${pct(row.coupon_rate)}</td>
        ${market ? `<td>${market.price.toFixed(3)}</td>
        <td>${pct(market.current_yield)}</td>
        <td>${pct(market.ytm)}</td>` : `<td colspan="3" class="pending">Daily Treasury market estimate unavailable</td>`}
      </tr>`;
    }).join("");
    const dates = items.map(row => row.auction_date).filter(Boolean).sort();
    const cached = items.some(row => row.data_status.startsWith("CACHED"));
    status.textContent = `${items.length} standard Treasury terms · auctions ${shortDate(dates[0])} through ${shortDate(dates.at(-1))}${cached ? " · cached official results" : " · retrieved from TreasuryDirect"}`;
  } catch (error) {
    status.textContent = error.message;
  }
}
load();
fetch("/api/auction-history")
  .then(response => {
    if (!response.ok) throw new Error("Auction history could not be loaded.");
    return response.json();
  })
  .then(data => window.renderTreasuryHistory(data))
  .catch(error => document.querySelector("#chart-status").textContent = error.message);
