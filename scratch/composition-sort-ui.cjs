const {chromium}=require('/Users/sandeeps/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {execFileSync}=require('child_process');
const assert=require('assert');
const py=`import json
from app import create_app
from flask import render_template
from app.services.sales_stock_composition_analysis import sort_composition_rows,SORT_COLUMNS
a=create_app()
with a.test_request_context('/sales-stock-composition-analysis'):
 rows=[dict(label=label,**{k:value for k in SORT_COLUMNS[1:]}) for label,value in [('Alpha',2),('Beta',10),('Gamma',None),('Delta',0)]]
 total=dict(label='Grand Total',**{k:100 for k in SORT_COLUMNS[1:]})
 result={'main':render_template('sales_stock_composition_analysis.html',permissions={'ADMIN'},unread_count=0,sync_time='',stats={},factor=1,fy_label='FY',rows=[],total=None),'roots':{},'branches':{}}
 for key in SORT_COLUMNS:
  for order in ['asc','desc']:
   values=sort_composition_rows(rows,key,order)
   result['roots'][key+':'+order]=render_template('partials/_view_sales_stock_composition_analysis.html',rows=values,total=total,stats={},can_expand=True,sort_by=key,sort_order=order)
   result['branches'][key+':'+order]=render_template('partials/_view_sales_stock_composition_analysis_branch.html',rows=values,parent_path=['Alpha'],can_expand=False)
 print('FIXTURE_JSON'+json.dumps(result))`;
const raw=execFileSync('docker',['exec','dcrystal-server-1','python','-c',py],{encoding:'utf8'});
const fixture=JSON.parse(raw.slice(raw.indexOf('FIXTURE_JSON')+12));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('access_token','fixture'));
  await page.route('**/sales-stock-composition-analysis',r=>r.fulfill({contentType:'text/html',body:fixture.main}));
  await page.route('**/api/**',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({dates:['2026-10-22'],locations:[],sections:[],classifications:[]})}));
  await page.route('**/partial/**',r=>{
   const url=new URL(r.request().url());requests.push(url);
   const key=(url.searchParams.get('sort_by')||'label')+':'+(url.searchParams.get('sort_order')||'asc');
   return r.fulfill({contentType:'text/html',body:(url.pathname.endsWith('/branch')?fixture.branches:fixture.roots)[key]});
  });
  await page.goto('http://127.0.0.1:8091/sales-stock-composition-analysis');
  await page.waitForSelector('[data-composition-sort="label"]');
  assert.equal(await page.locator('[data-composition-sort]').count(),6);
  await page.locator('[data-composition-sort="sales_composition"]').click();
  await page.waitForSelector('th[aria-sort="ascending"] [data-composition-sort="sales_composition"]');
  const labels=()=>page.locator('#composition-analysis-table tbody tr.parent-row td:first-child').allTextContents().then(v=>v.map(s=>s.replace('▶','').trim()));
  assert.deepEqual(await labels(),['Delta','Alpha','Beta','Gamma']);
  await page.locator('[data-composition-sort="sales_composition"]').click();
  await page.waitForSelector('th[aria-sort="descending"] [data-composition-sort="sales_composition"]');
  assert.deepEqual(await labels(),['Beta','Alpha','Delta','Gamma']);
  await page.locator('#composition-analysis-table tbody tr.parent-row td:first-child').first().click();
  await page.waitForSelector('#composition-analysis-table tr.child-row');
  const branch=requests.findLast(u=>u.pathname.endsWith('/branch'));
  assert.equal(branch.searchParams.get('sort_by'),'sales_composition');
  assert.equal(branch.searchParams.get('sort_order'),'desc');
  assert.equal(branch.searchParams.get('date'),'2026-10-22');
  assert.equal(await page.locator('#composition-analysis-table tfoot tr').count(),1);
  await page.locator('[data-composition-sort="label"]').click();
  await page.waitForSelector('th[aria-sort="ascending"] [data-composition-sort="label"]');
  assert.equal(await page.locator('tr.child-row').count(),0);
  await page.screenshot({path:'/tmp/composition-sort-desktop.png'});
  await page.locator('#composition-filter-toggle').click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/tmp/composition-sort-mobile-before.png'});
  await page.locator('[data-composition-sort="tsk_pct"]').click({timeout:10000});
  await page.waitForSelector('th[aria-sort="ascending"] [data-composition-sort="tsk_pct"]');
  await page.screenshot({path:'/tmp/composition-sort-mobile.png'});
  assert.deepEqual(await labels(),['Delta','Alpha','Beta','Gamma']);
  assert.deepEqual(errors,[]);
  console.log('PASS: six accessible sort headers, numeric asc/desc, N/A last, branch propagation, fixed total, desktop/mobile clicks, no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
