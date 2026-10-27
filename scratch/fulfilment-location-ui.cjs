const {chromium}=require('/Users/sandeeps/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {execFileSync}=require('child_process');
const assert=require('assert');
const raw=execFileSync('docker',['exec','dcrystal-server-1','python','-c',`from app import create_app
from flask import render_template
from app.dashboard.routes.customer_order_fulfilment_summary import HIERARCHIES
a=create_app()
with a.test_request_context('/customerorderfulfilmentsummary?hierarchy=7&location=ERNAKULAM&page=2'):
 print(render_template('customer_order_fulfilment_summary.html',unread_count=0,sync_time='',stats=None,rows=[],pagination=None,hierarchies=HIERARCHIES,current_hierarchy=HIERARCHIES[7],current_level_idx=0,filter_options={'locations':['ERNAKULAM','THRISSUR ROUND']}))`],{encoding:'utf8'});
const html=raw.slice(raw.toLowerCase().indexOf('<!doctype html>'));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{localStorage.setItem('access_token','fixture');localStorage.removeItem('fulfilment_filter_visible');});
  await page.route('**/customerorderfulfilmentsummary?*',r=>r.fulfill({contentType:'text/html',body:html}));
  await page.route('**/api/**',r=>r.fulfill({contentType:'application/json',body:'{}'}));
  await page.route('**/partial/**',r=>{requests.push(new URL(r.request().url()));return r.fulfill({contentType:'text/html',body:'<div>Filtered report fixture</div>'});});
  await page.goto('http://127.0.0.1:8091/customerorderfulfilmentsummary?hierarchy=7&location=ERNAKULAM&page=2');
  assert.equal(await page.locator('#filter-location').inputValue(),'ERNAKULAM');
  await page.locator('#filter-location').selectOption('THRISSUR ROUND');
  await page.locator('button[onclick="applyFulfilmentFilters()"]').click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('location')==='THRISSUR ROUND');
  assert.equal(requests.at(-1).searchParams.get('location'),'THRISSUR ROUND');
  assert.equal(requests.at(-1).searchParams.get('hierarchy'),'7');
  assert.equal(requests.at(-1).searchParams.get('page'),'1');
  await page.screenshot({path:'/tmp/fulfilment-location-desktop.png'});
  await page.locator('button[onclick="resetFulfilmentFilters()"]').click();
  await page.waitForFunction(()=>!new URLSearchParams(location.search).has('location'));
  assert.equal(await page.locator('#filter-location').inputValue(),'');
  assert.deepEqual(errors,[]);
  console.log('PASS: persisted location, Apply, query propagation, pagination reset, hierarchy retained, Reset, no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
