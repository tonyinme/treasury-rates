(function () {
  const order=["4-Week Bill","6-Week Bill","8-Week Bill","13-Week Bill","17-Week Bill","26-Week Bill","52-Week Bill","2-Year Note","3-Year Note","5-Year Note","7-Year Note","10-Year Note","20-Year Bond","30-Year Bond"];
  const colors=["#236a5b","#d47b2f","#5478a2","#9a5c8e","#7d8b38","#c04f52","#1787a1","#6b61a8","#aa7422","#287fb8","#8f4f42","#4b7d53","#a84f78","#173a55"];
  const short=term=>term.replace(" Bill","").replace(" Note","").replace(" Bond","");

  window.renderTreasuryHistory=function(payload){
    const series=payload.series||{};
    const picker=document.querySelector("#term-picker");
    const canvas=document.querySelector("#history-chart");
    const tooltip=document.querySelector("#chart-tooltip");
    const status=document.querySelector("#chart-status");
    picker.innerHTML=order.map(term=>`<label class="term-toggle"><input type="checkbox" value="${term}" ${["4-Week Bill","2-Year Note","10-Year Note","30-Year Bond"].includes(term)?"checked":""}><span>${short(term)}</span></label>`).join("")+
      `<button type="button" id="clear-series">Clear all</button>`;
    const clearButton=picker.querySelector("#clear-series");
    const chosen=()=>[...picker.querySelectorAll("input:checked")].map(input=>input.value);

    function draw(){
      const selected=chosen();
      clearButton.disabled=!selected.length;
      const box=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
      canvas.width=Math.round(box.width*dpr);canvas.height=Math.round(box.height*dpr);
      const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);
      const w=box.width,h=box.height,p={l:54,r:18,t:18,b:42};
      const all=selected.flatMap(term=>(series[term]||[]).map(point=>[new Date(point[0]+"T00:00:00Z").getTime(),point[1],term]));
      ctx.clearRect(0,0,w,h);
      if(!all.length){
        canvas._chart=null;tooltip.style.display="none";
        ctx.font="14px -apple-system, sans-serif";ctx.fillStyle="#677580";ctx.textAlign="center";
        ctx.fillText("Select a Treasury term to plot",w/2,h/2);
        status.textContent="No terms selected.";return
      }
      const x0=Math.min(...all.map(p=>p[0])),x1=Math.max(...all.map(p=>p[0]));
      const ymax=Math.max(1,Math.ceil(Math.max(...all.map(p=>p[1]))/2)*2);
      const x=v=>p.l+(v-x0)/(x1-x0)*(w-p.l-p.r),y=v=>p.t+(ymax-v)/ymax*(h-p.t-p.b);
      ctx.font="11px -apple-system, sans-serif";ctx.fillStyle="#677580";ctx.strokeStyle="#e1e6e9";ctx.lineWidth=1;
      for(let rate=0;rate<=ymax;rate+=2){const py=y(rate);ctx.beginPath();ctx.moveTo(p.l,py);ctx.lineTo(w-p.r,py);ctx.stroke();ctx.fillText(rate+"%",8,py+4)}
      const startYear=new Date(x0).getUTCFullYear(),endYear=new Date(x1).getUTCFullYear();
      const step=w<650?5:4;
      for(let yr=startYear;yr<=endYear;yr++){
        for(const month of [0,6]){
          const px=x(Date.UTC(yr,month,1));if(px<p.l||px>w-p.r)continue;
          ctx.strokeStyle=month===0?"#d7dfe4":"#edf0f2";ctx.lineWidth=1;
          ctx.beginPath();ctx.moveTo(px,p.t);ctx.lineTo(px,h-p.b);ctx.stroke();
        }
        if(yr%step===0){
          const px=x(Date.UTC(yr,0,1));
          ctx.fillStyle="#677580";ctx.textAlign="center";ctx.fillText(String(yr),px,h-17);
        }
      }
      ctx.textAlign="left";
      selected.forEach(term=>{
        const points=series[term]||[];if(!points.length)return;
        ctx.strokeStyle=colors[order.indexOf(term)];ctx.lineWidth=1.6;ctx.beginPath();
        points.forEach((point,i)=>{const px=x(new Date(point[0]+"T00:00:00Z").getTime()),py=y(point[1]);i?ctx.lineTo(px,py):ctx.moveTo(px,py)});
        ctx.stroke();
      });
      status.textContent=`Showing ${selected.length} term${selected.length===1?"":"s"} · ${all.length.toLocaleString()} official auction results${payload.status?.startsWith("CACHED")?" · cached":""}`;
      canvas._chart={all,x,x0,x1,p,w,h};
    }
    picker.addEventListener("change",draw);
    clearButton.addEventListener("click",()=>{
      picker.querySelectorAll("input:checked").forEach(input=>input.checked=false);
      draw();
    });
    canvas.addEventListener("pointermove",event=>{
      const chart=canvas._chart;if(!chart)return;
      const rect=canvas.getBoundingClientRect(),mx=event.clientX-rect.left;
      const time=chart.x0+(mx-chart.p.l)/(chart.w-chart.p.l-chart.p.r)*(chart.x1-chart.x0);
      const candidates=chosen().map(term=>{
        const points=series[term]||[];let best=null;
        for(const point of points){const t=new Date(point[0]+"T00:00:00Z").getTime(),d=Math.abs(t-time);if(!best||d<best.d)best={point,t,d,term}}
        return best;
      }).filter(Boolean);
      const best=candidates.sort((a,b)=>a.d-b.d)[0];if(!best)return;
      tooltip.style.display="block";tooltip.textContent=`${short(best.term)} · ${best.point[0]} · ${best.point[1].toFixed(3)}%`;
      tooltip.style.left=Math.min(mx+12,rect.width-tooltip.offsetWidth-6)+"px";tooltip.style.top="12px";
    });
    canvas.addEventListener("pointerleave",()=>tooltip.style.display="none");
    new ResizeObserver(draw).observe(canvas);draw();
  };
}());
