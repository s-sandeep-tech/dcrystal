const {chromium}=require('/Users/sandeeps/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {execFileSync}=require('child_process');const assert=require('assert');
const py=`from app import create_app
from flask import render_template
from app.services.nip_stock_trend import DIMENSIONS,FILTER_FIELDS
a=create_app()
with a.test_request_context('/nip-stock-trend-analysis'):
 print(render_template('nip_stock_trend.html',permissions={'ADMIN'},dimensions=DIMENSIONS,filter_fields=FILTER_FIELDS,unread_count=0,sync_time=''))`;
const raw=execFileSync('docker',['exec','dcrystal-server-1','python','-c',py],{encoding:'utf8'}),html=raw.slice(raw.toLowerCase().indexOf('<!doctype html>'));
const fields=['location','division','group_name','purity','classification','sub_classification','make','master_collection','collection','section','sub_section','type','gender','wide_range','branch_type','prov_type'];
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),requests=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('access_token','fixture'));
 await page.route('**/nip-stock-trend-analysis',r=>r.fulfill({contentType:'text/html',body:html}));
 await page.route('**/api/**',r=>{
  const url=new URL(r.request().url());
  if(url.pathname.endsWith('/options'))return r.fulfill({contentType:'application/json',body:JSON.stringify({options:Object.fromEntries(fields.map(k=>[k,k==='location'?['ERNAKULAM','THRISSUR ROUND']:['Gold','Silver']]))})});
  requests.push(url);
  const periods=Array.from({length:21},(_,i)=>`2026-10-${String(i+1).padStart(2,'0')}`);
  const body={periods,balance_dates:periods,series:['Gold','Silver','Platinum'].map((name,i)=>({name,values:periods.map((_,j)=>10+i*10+j)})),
   metric:url.searchParams.get('metric')||'gross_wt',group_by:url.searchParams.get('group_by')||'division',interval:url.searchParams.get('interval')||'daily',
   stats:{total_stock:120,total_nip:60,total_excess:30,change:60,change_pct:100,average:90},first_date:periods[0],last_date:periods.at(-1),observed_days:21};
  const groups=body.group_by==='purity'?['750.00','920.00','995.00','999.00'].map((name,i)=>({name,values:periods.map(()=>i+1)})):body.series;
  body.unit=body.metric==='pieces'?'Nos.':'kg';
  body.table_rows=periods.flatMap((period,p)=>groups.map(s=>({period,balance_date:period,group:s.name,total:s.values[p],nip:s.values[p]/2,excess:s.values[p]/4})));
  body.series=groups.flatMap(s=>[['total',1],['nip',.5],['excess',.25]].map(([kind,factor])=>({name:s.name+' - '+kind,group:s.name,kind,values:s.values.map(v=>v*factor)})));
  body.series[0].values[0]=0.0001;
  body.series[2].values[0]=0;
  return r.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:8091/nip-stock-trend-analysis');
 try {await page.waitForFunction(()=>document.getElementById('nip-stat-total_nip')?.textContent==='60.000',{},{timeout:10000});}
 catch(error){console.log({errors,requests:requests.map(String),url:page.url(),status:await page.locator('#nip-status').textContent()});await page.screenshot({path:'/tmp/nip-debug.png'});throw error;}
 assert.equal(await page.locator('#nip-table tbody tr').count(),50);
 assert.equal(await page.locator('#nip-stat-total_stock').textContent(),'120.000');
 assert.equal(await page.locator('.nip-stats>div').count(),6);
 assert.equal(await page.locator('.nip-unit[data-stat="change_pct"]').textContent(),'');
 assert.equal(await page.locator('#nip-limiter').inputValue(),'top');
 assert.equal(await page.locator('#nip-limiter option:checked').textContent(),'Top 16');
 assert.equal(await page.locator('#nip-order').inputValue(),'desc');
 assert(!(await page.locator('#nip-table thead').textContent()).includes('undefined'));
 assert.equal(await page.locator('[data-view="combined"]').count(),0);
 await page.locator('[data-view="table"]').click();
 assert.equal(await page.locator('#nip-graph').isVisible(),false);
 const outputBox=await page.locator('#nip-output').boundingBox();
 const tableBox=await page.locator('#nip-table').boundingBox();
 assert(Math.abs(outputBox.height-tableBox.height)<2);
 await page.getByRole('button',{name:'Next page',exact:true}).click();assert.equal(await page.locator('#nip-table tbody tr').count(),13);
 await page.locator('[data-view="graph"]').click();assert.equal(await page.locator('#nip-table').isVisible(),false);
 const graphBox=await page.locator('#nip-graph').boundingBox();
 assert(Math.abs(outputBox.height-graphBox.height)<2);
 await page.locator('#nip-average').check();
 assert.equal(await page.evaluate(()=>Chart.getChart(document.getElementById('nip-chart')).data.datasets.filter(d=>!d.groupSpacer).length),18);
 assert.equal(await page.evaluate(()=>Chart.getChart(document.getElementById('nip-chart')).config.type),'bar');
 assert.deepEqual(await page.evaluate(()=>Chart.getChart(document.getElementById('nip-chart')).data.datasets.filter(d=>!d.groupSpacer).map(d=>d.type)),Array.from({length:9},()=>['bar','line']).flat());
 await page.waitForTimeout(1000);
 const gaps=await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart'));
  const bars=c.data.datasets.flatMap((d,i)=>d.type==='bar'&&!d.groupSpacer?[c.getDatasetMeta(i).data[0]]:[]);
  return {inside:bars[1].x-bars[0].x-(bars[0].width+bars[1].width)/2,
   between:bars[3].x-bars[2].x-(bars[2].width+bars[3].width)/2};
 });
 assert(gaps.between>gaps.inside*5,JSON.stringify(gaps));
 const smallBars=await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart'));
  const bars=c.data.datasets.flatMap((d,i)=>d.type==='bar'&&!d.groupSpacer?[c.getDatasetMeta(i).data[0]]:[]);
  return {tiny:Math.abs(bars[0].base-bars[0].y),zero:Math.abs(bars[2].base-bars[2].y)};
 });
 assert(smallBars.tiny>=2.5,JSON.stringify(smallBars));
 assert(smallBars.zero===0,JSON.stringify(smallBars));
 await page.locator('#nip-metric').selectOption('pieces');await page.waitForFunction(()=>document.getElementById('nip-stat-total_nip').textContent==='60');
 await page.locator('#nip-interval').selectOption('monthly');
 await page.locator('#nip-from').fill('2026-10-01');await page.locator('#nip-to').fill('2026-10-21');
 await page.locator('#nip-apply').click();await page.waitForFunction(()=>document.getElementById('nip-status').textContent.includes('Last reporting date'));
 assert.equal(requests.at(-1).searchParams.get('from_date'),'2026-10-01');
 assert.equal(requests.at(-1).searchParams.get('metric'),'pieces');
 await page.locator('#nip-limiter').selectOption('top');
 await page.waitForResponse(response=>response.url().includes('/data?')&&new URL(response.url()).searchParams.get('limiter')==='top');
 await page.locator('#nip-order').selectOption('asc');
 await page.waitForResponse(response=>response.url().includes('/data?')&&new URL(response.url()).searchParams.get('order')==='asc');
 assert.equal(requests.at(-1).searchParams.get('limiter'),'top');
 await page.locator('#nip-rank-by').selectOption('excess');
 await page.waitForResponse(response=>response.url().includes('/data?')&&new URL(response.url()).searchParams.get('rank_by')==='excess');
 assert.equal(requests.at(-1).searchParams.get('limiter'),'top');
 const pixels=await page.evaluate(()=>{const c=Chart.getChart(document.getElementById('nip-chart'));return c.ctx.getImageData(0,0,c.width,c.height).data.filter((v,i)=>i%4===3&&v>0).length;});assert(pixels>1000);
 await page.screenshot({path:'/tmp/nip-stock-trend-desktop.png'});
 await page.locator('#nip-expand').click();await page.waitForFunction(()=>!!document.fullscreenElement);
 await page.locator('#nip-expand').click();await page.waitForFunction(()=>!document.fullscreenElement);
 const downloadPromise=page.waitForEvent('download');await page.locator('#nip-png').click();assert.equal((await downloadPromise).suggestedFilename(),'nip-stock-trend.png');
 await page.locator('#nip-clear').click();await page.waitForFunction(()=>!document.getElementById('nip-from').value);
 await page.locator('#nip-group').selectOption('purity');
 await page.waitForFunction(()=>Chart.getChart(document.getElementById('nip-chart')).data.datasets.some(d=>d.comparisonGroup==='999.00'));
 const purityLabels=await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart')),labels=[],original=c.ctx.fillText;
  c.ctx.fillText=function(text,...args){labels.push(text);return original.call(this,text,...args);};
  c.draw();c.ctx.fillText=original;return labels;
 });
 for(const purity of ['750','920','995','999'])assert(purityLabels.includes(purity));
 for(const value of ['1','2','3','4'])assert(purityLabels.includes(value),'Missing bar value '+value);
 const hoverPoint=await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart'));
  const index=c.data.datasets.findIndex(d=>d.type==='bar'&&d.comparisonGroup==='920.00'&&d.stockKind==='total');
  const bar=c.getDatasetMeta(index).data[5],rect=c.canvas.getBoundingClientRect();
  return {x:rect.left+bar.x,y:rect.top+(bar.y+bar.base)/2};
 });
 await page.mouse.move(hoverPoint.x,hoverPoint.y);
 await page.waitForTimeout(100);
 const tooltipGroups=await page.evaluate(()=>Chart.getChart(document.getElementById('nip-chart')).tooltip.dataPoints.map(point=>point.dataset.comparisonGroup));
 assert.deepEqual(tooltipGroups,['920.00','920.00','920.00']);
 const tooltipText=await page.evaluate(()=>{
  const tooltip=Chart.getChart(document.getElementById('nip-chart')).tooltip;
  return {heading:tooltip.title[0],rows:tooltip.body.flatMap(row=>row.lines)};
 });
 assert.equal(tooltipText.heading,'920');
 assert.deepEqual(tooltipText.rows.map(row=>row.split(':')[0]),['Total Stock','NIP Stock','Excess Stock']);
 assert.deepEqual(await page.evaluate(()=>Chart.getChart(document.getElementById('nip-chart')).legend.legendItems.map(item=>item.text)),['Total Stock','NIP Stock','Excess Stock']);
 const legendPoint=await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart')),box=c.legend.legendHitBoxes[1],rect=c.canvas.getBoundingClientRect();
  return {x:rect.left+box.left+box.width/2,y:rect.top+box.top+box.height/2};
 });
 await page.mouse.click(legendPoint.x,legendPoint.y);
 await page.waitForTimeout(100);
 assert.equal(await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart'));
  return c.data.datasets.every((d,i)=>d.stockKind!=='nip'||!c.isDatasetVisible(i));
 }),true);
 await page.mouse.click(legendPoint.x,legendPoint.y);
 await page.waitForTimeout(100);
 assert.equal(await page.evaluate(()=>{
  const c=Chart.getChart(document.getElementById('nip-chart'));
  return c.data.datasets.every((d,i)=>d.stockKind!=='nip'||c.isDatasetVisible(i));
 }),true);
 await page.locator('#nip-filter-toggle').click();await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'/tmp/nip-stock-trend-mobile.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);console.log('PASS: chart pixels, table pagination, view modes, moving average, metric/interval/filter controls, fullscreen, PNG export, clear, mobile overflow, no page errors');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
