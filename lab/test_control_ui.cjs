const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const output=path.join(process.env.LAB_STATE_DIR||path.join(process.cwd(),'.lab'),'ui-qa');fs.mkdirSync(output,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const environments=Array.from({length:55},(_,i)=>({id:'environment-'+i,name:'lab-'+String(i).padStart(3,'0'),
  owner:i%2?'alice':'bob',state:i%5?'ready':'deleted',release_id:'esci-gb-v1',build_run:6,
  created_at:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),expires_at:'2027-01-01T00:00:00Z',
  source_sha:'a'.repeat(40),image:'nexus/image@sha256:'+'b'.repeat(64),index_name:'esci-frozen',index_kind:'shared'}));
const delivery=[{id:'delivery:integration',name:'lab-delivery-integration',label:'Integration — build 158',owner:'lab',managed_by:'delivery',state:'ready',release_id:'esci-gb-v1',build_run:158,created_at:'2026-10-06T00:00:00Z'},{id:'delivery:blue',name:'lab-delivery-production-blue',label:'Production blue — active — build 108',owner:'lab',managed_by:'delivery',state:'ready',release_id:'esci-gb-v1',build_run:108,created_at:'2026-10-06T00:00:00Z'}];
let reader=true;
const comparisons=Array.from({length:100},(_,i)=>({id:'comparison-'+i,baseline_id:'environment-1',candidate_id:'environment-'+(i%55),
  mode:i%3?'relevance':'performance',state:'complete',verdict:'unchanged',report_blob:'report.json',
  created_at:new Date(Date.UTC(2026,0,2,0,i)).toISOString(),summary:{completed_query_count:1000,query_count:1000}}));
const report={mode:'relevance',verdict:'unchanged',completed_query_count:1000,query_count:1000,
 judgement_coverage:{baseline:{fraction:.8122},candidate:{fraction:.8122}},judgement_selection:'demo',judgement_sha256:'a'.repeat(64),
 queries:Array.from({length:1000},(_,i)=>({query_id:'q-'+String(i).padStart(4,'0'),query:i===15?'café chair':'query '+i,
 equal_top_10:i%2===0,rbo_at_10_p_0_9:.9,ndcg_delta_at_10:0,baseline:{ids:[],unjudged_top_10_ids:[]},candidate:{ids:[],unjudged_top_10_ids:[]}}))};
await page.route('http://control.test/**',route=>{
 const pathname=new URL(route.request().url()).pathname;
 if(pathname==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(process.cwd(),'lab/control-ui.html'),'utf8')});
 if(pathname==='/control_lists.js')return route.fulfill({contentType:'text/javascript; charset=utf-8',body:fs.readFileSync(path.join(process.cwd(),'lab/control_lists.js'),'utf8')});
 const data=pathname==='/api/auth'?{oidc:true}:pathname==='/api/me'?{username:reader?'demo-reader':'demo-admin',is_reader:reader,is_admin:!reader}:
 pathname==='/api/environments'?environments:pathname==='/api/comparison-targets'?delivery:pathname==='/api/comparisons'?comparisons:pathname.endsWith('/report')?report:
 pathname==='/api/datasets'?[{release:'esci-gb-v1',manifest:{count:1215854,query_count:1000}}]:
 pathname==='/api/index-kinds'?{'esci-gb-v1':[]}:pathname==='/api/notebooks'?['comparison-explorer.ipynb']:{};
 return route.fulfill({contentType:'application/json; charset=utf-8',body:JSON.stringify(data)});
});
await page.goto('http://control.test/');await page.locator('#environment-paging').getByText('1–12 of 46',{exact:true}).waitFor();
assert.equal(await page.locator('#environments .card').count(),12);assert.equal(await page.locator('#comparisons .card').count(),12);
await page.locator('#environment-paging').getByRole('button',{name:'Next',exact:true}).click();
await page.locator('#environment-paging').getByText('13–24 of 46',{exact:true}).waitFor();
await page.locator('#environment-search').fill('alice');await page.locator('#environment-paging').getByText('1–12 of 22',{exact:true}).waitFor();
assert.equal(await page.locator('#baseline option').count(),46);
assert.equal(await page.locator('#environments').getByRole('button',{name:'Delete',exact:true}).count(),0);
await page.locator('#comparison-mode').selectOption('performance');await page.locator('#comparison-paging').getByText('1–12 of 34',{exact:true}).waitFor();
await page.locator('#comparisons').getByRole('button',{name:'Open report',exact:true}).first().click();
await page.locator('#report-coverage-summary').getByText('Judged results: baseline 81.2%',{exact:false}).waitFor();
assert.ok(!(await page.locator('#report-summary').innerText()).includes('judged'));
assert.ok(await page.locator('#report-quality-note').isVisible());
// Use a relevance report fixture independently of the selected comparison filter.
await page.locator('#query-paging').getByText('1–25 of 500',{exact:true}).waitFor();
await page.locator('#query-paging').getByRole('button',{name:'Next',exact:true}).click();await page.locator('#query-paging').getByText('26–50 of 500',{exact:true}).waitFor();
await page.locator('#query-search').fill('café');await page.locator('#query-paging').getByText('1–1 of 1',{exact:true}).waitFor();
assert.ok((await page.locator('#query-list').innerText()).includes('café chair · changed · ΔnDCG 0'));
assert.equal(await page.locator('#release option').first().textContent(),'esci-gb-v1 · 1,215,854 products · 1,000 queries');
await page.evaluate(()=>window.scrollTo(0,0));
const section=await page.locator('section').filter({has:page.getByRole('heading',{name:'Environments',exact:true})}).boundingBox();
const firstCard=await page.locator('#environments .card').first().boundingBox();
await page.screenshot({path:path.join(output,'control-environments.png'),fullPage:true,clip:{x:section.x,y:section.y,width:section.width,height:firstCard.y+firstCard.height-section.y+16}});
await page.screenshot({path:path.join(output,'control-lists-desktop.png'),fullPage:true});
await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'control-lists-mobile.png'),fullPage:true});
assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
reader=false;await page.setViewportSize({width:1440,height:1100});await page.goto('http://control.test/');await page.locator('#environment-paging').getByText('1–12 of 46',{exact:true}).waitFor();
await page.locator('#environment-search').fill('lab-delivery');
assert.equal(await page.locator('#environments .card').count(),2);
assert.equal(await page.locator('#environments').getByRole('button',{name:'Delete',exact:true}).count(),0);
assert.equal(await page.locator('#environments').getByRole('button',{name:'Extend lease',exact:true}).count(),0);
await page.locator('#baseline').selectOption('delivery:blue');
assert.equal(await page.locator('#baseline option:checked').textContent(),'Production blue — active — build 108');
await page.locator('#baseline').selectOption('environment-52');await page.locator('#candidate').selectOption('environment-54');
await page.locator('#notebook').selectOption('comparison-explorer.ipynb');
let releaseComparison,submitCount=0;
const pendingComparison=new Promise(resolve=>releaseComparison=resolve);
await page.route('http://control.test/api/comparisons',async route=>{
 if(route.request().method()!=='POST')return route.fallback();
 submitCount++;await pendingComparison;
 return route.fulfill({contentType:'application/json',body:JSON.stringify({id:'new-comparison',state:'complete',verdict:'measured',report_blob:'report.json',summary:{notebook:{state:'complete'}}})});
});
await page.locator('#compare').getByRole('button',{name:'Run comparison',exact:true}).click();
await page.locator('#comparison-feedback').getByText('Comparison running.',{exact:false}).waitFor();
assert.ok(await page.locator('#compare button').isDisabled());
await page.locator('#compare').evaluate(form=>form.requestSubmit());
releaseComparison();
await page.locator('#comparison-feedback').getByText('Comparison complete · measured. Notebook complete.',{exact:true}).waitFor();
assert.equal(submitCount,1);
assert.equal(await page.locator('#comparison-feedback a').getAttribute('href'),'/?comparison=new-comparison');
await page.waitForFunction(()=>!document.querySelector('#compare button').disabled);
await page.unroute('http://control.test/api/comparisons');
await page.route('http://control.test/api/comparisons',route=>route.request().method()==='POST'?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Refresh and select the target again.'})}):route.fallback());
await page.locator('#compare button').click();
await page.locator('#comparison-feedback').getByText('Comparison could not finish: Refresh and select the target again.',{exact:true}).waitFor();
assert.ok(await page.locator('#compare button').isEnabled());
await page.unroute('http://control.test/api/comparisons');
await page.locator('#compare').screenshot({path:path.join(output,'comparison-controls-current.png')});
await page.locator('#environment-search').fill('alice');await page.locator('#environment-paging').getByRole('button',{name:'Next',exact:true}).click();
comparisons[99].id='after-refresh';await page.locator('#refresh').click();await page.locator('#comparisons').getByText('Comparison after-refresh',{exact:true}).waitFor();
assert.equal(await page.locator('#baseline').inputValue(),'environment-52');assert.equal(await page.locator('#candidate').inputValue(),'environment-54');
await page.locator('#environment-paging').getByText('13–22 of 22',{exact:true}).waitFor();
await page.locator('#environment-search').fill('no-such-environment');await page.locator('#environment-paging').getByText('No matches',{exact:true}).waitFor();
assert.equal(await page.locator('#environments .card').count(),0);
assert.deepEqual(errors,[]);
const receipt={browser:browser.version(),fixture:{environments:55,comparisons:100,queries:1000},paging:'passed',filters:'passed',refresh_selection:'passed',empty_results:'passed',reader:'passed',unicode:'passed',mobile_overflow:'none',page_errors:errors};fs.writeFileSync(path.join(output,'control-lists-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
}finally{await browser.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1});
