const {chromium}=require('/Users/sandeeps/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {execFileSync}=require('child_process');
const assert=require('assert');
const py=`from app import create_app
from flask import render_template
a=create_app()
with a.test_request_context('/location-wise-old-gold-settlement-transfer-summary?office=RO+A&page=2&per_page=50'):
 print(render_template('location_wise_old_gold_settlement_transfer.html',permissions={'ADMIN'},unread_count=0,sync_time='',stats=None,filter_options={'offices':['RO A'],'locations':[],'locationtypes':[],'divisions':[],'groups':[],'purities':[]}))`;
const raw=execFileSync('docker',['exec','dcrystal-server-1','python','-c',py],{encoding:'utf8'});
const html=raw.slice(raw.toLowerCase().indexOf('<!doctype html>'));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{localStorage.setItem('access_token','fixture');localStorage.removeItem('last_old_gold_export_time');});
  await page.route('**/location-wise-old-gold-settlement-transfer-summary?*',r=>r.fulfill({contentType:'text/html',body:html}));
  await page.route('**/partial/location-wise-old-gold-settlement-transfer?*',r=>r.fulfill({contentType:'text/html',body:'<div>Fixture report</div>'}));
  const requests=[];
  await page.route('**/api/**',r=>{
   if(r.request().url().endsWith('/api/location-wise-old-gold-settlement-transfer/export')) requests.push(r.request().postDataJSON());
   return r.fulfill({contentType:'application/json',body:JSON.stringify({status:'success',notifications:[]})});
  });
  await page.goto('http://127.0.0.1:8091/location-wise-old-gold-settlement-transfer-summary?office=RO+A&page=2&per_page=50');
  await page.waitForFunction(()=>typeof exportOldGoldToExcel==='function');
  await page.evaluate(()=>window.showToast=(...args)=>{window.lastToast=args;});
  await page.locator('#filter-from-date').fill('2026-01-01');
  await page.locator('#old-gold-export').click();
  await page.waitForFunction(()=>document.getElementById('old-gold-export-label').textContent==='Export');
  assert.deepEqual(requests[0].filters,{office:'RO A'});
  assert.equal(requests.length,1);
  await page.locator('#old-gold-export').click();
  assert.equal(requests.length,1);
  assert((await page.evaluate(()=>window.lastToast[1])).includes('recently queued'));
  await page.screenshot({path:'/tmp/old-gold-export-desktop.png'});
  await page.evaluate(()=>localStorage.removeItem('last_old_gold_export_time'));
  await page.route('**/api/location-wise-old-gold-settlement-transfer/export',r=>r.fulfill({status:403,contentType:'application/json',body:JSON.stringify({msg:'No export permission'})}));
  await page.locator('#old-gold-export').click();
  await page.waitForFunction(()=>window.lastToast?.[1]==='No export permission');
  assert.equal(await page.locator('#old-gold-export').isDisabled(),false);
  assert.deepEqual(errors,[]);
  console.log('PASS: applied filters only, pagination excluded, queue notification, cooldown, permission errors, button reset, no page errors');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
