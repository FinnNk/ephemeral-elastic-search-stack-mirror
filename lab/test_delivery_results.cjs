const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const id='a'.repeat(32),url='http://control.test/api/delivery/operations/'+id;
 let denied=false,operation={id,state:'running',progress:'Capturing fresh results: standard',updated_at:'2026-10-05T20:00:00Z',request:{kind:'compare',pr:31,source_sha:'b'.repeat(40)},result:null};
 const standard={kind:'variant-evaluation-report',complete:true,baseline_variant:'baseline',query_count:1000,variants:{baseline:{},'ranker-a':{}},metrics:{baseline:{'nDCG@10':.7,'Judged@10':.81},'ranker-a':{'nDCG@10':.71,'Judged@10':.82}},result_changes:{'ranker-a':{changed_queries:2}},result_similarity:{baseline:{rbo_at_10_p_0_9:1,jaccard_at_10:1},'ranker-a':{rbo_at_10_p_0_9:.98,jaccard_at_10:.99}},coverage:{baseline:{fraction:.81,judged:8100,returned:10000},'ranker-a':{fraction:.82,judged:8200,returned:10000}}};
 const extra={...standard,query_count:4,metrics:null,relevance_available:false,coverage:{baseline:{fraction:0,judged:0,returned:40},'ranker-a':{fraction:0,judged:0,returned:40}}};
 let report={...standard,judgement_selection:'demo',query_sets:{standard,sneakers:extra},query_set_metadata:{standard:{required:true},sneakers:{required:false}},combined:{metrics:standard.metrics,result_similarity:standard.result_similarity,query_count:1004,relevance_query_count:1000,unlabelled_query_count:4}};
 await page.route('http://control.test/**',async route=>{
 const req=route.request(),u=new URL(req.url());
 if(u.pathname==='/delivery_results.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(__dirname,'delivery_results.js'),'utf8')});
 if(req.headers().accept?.includes('text/html'))return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'delivery-results.html'),'utf8')});
 return route.fulfill({status:denied?401:200,contentType:'application/json',body:JSON.stringify(denied?{error:'Sign in to the lab.'}:u.pathname.includes('/report')?report:operation)});
 });
 await page.clock.install();await page.goto(url);await page.getByText('Capturing fresh results: standard',{exact:true}).waitFor();
 operation={...operation,state:'complete',progress:'Complete',report_url:url+'/report',result:{baseline_url:'https://baseline.preview.relevance.test:34443',candidate_url:'https://candidate.preview.relevance.test:34443',gate:{state:'pass',variants:[{variant:'ranker-a',intent:'ranking-change',state:'pass',delta:.01,judged_fraction:.82}]}}};
 await page.clock.fastForward(5000);await page.getByRole('heading',{name:'Merge gate',exact:true}).waitFor();
 assert.equal(await page.locator('#report').getAttribute('href'),url+'/report');assert.ok((await page.locator('#content').innerText()).includes('A passing gate does not deploy'));
 await page.goto(url+'/report');await page.getByRole('heading',{name:'sneakers',exact:true}).waitFor();
 assert.ok((await page.locator('#content').innerText()).includes('Relevance scores are unavailable'));
 assert.ok((await page.locator('#content').innerText()).includes('accuracy remains unqualified'));
 assert.equal(await page.getByRole('heading',{name:'Combined view',exact:true}).count(),1);
 assert.equal(await page.getByRole('cell',{name:'ranker-a vs baseline',exact:true}).count(),3);
 assert.equal(await page.getByRole('cell',{name:'baseline vs baseline',exact:true}).count(),0);
 assert.equal(await page.getByRole('columnheader',{name:'RBO@10 (p = 0.9)',exact:true}).count(),3);
 assert.ok(!(await page.locator('#content').innerText()).includes('Not available'));
 // Each candidate has its own comparison against the named baseline.
 report={...standard,variants:{...standard.variants,'ranker-b':{}},metrics:{...standard.metrics,'ranker-b':{'nDCG@10':.69}},result_changes:{...standard.result_changes,'ranker-b':{changed_queries:10}},result_similarity:{...standard.result_similarity,'ranker-b':{rbo_at_10_p_0_9:.9,jaccard_at_10:.95}}};
 await page.goto(url+'/report');await page.getByRole('cell',{name:'ranker-b vs baseline',exact:true}).waitFor();
 assert.equal(await page.getByRole('cell',{name:'ranker-a vs baseline',exact:true}).count(),1);
 report={...standard,judgement_selection:'demo',query_sets:{standard,sneakers:extra},query_set_metadata:{standard:{required:true},sneakers:{required:false}},combined:{metrics:standard.metrics,result_similarity:standard.result_similarity,query_count:1004,relevance_query_count:1000,unlabelled_query_count:4}};
 await page.goto(url+'/report');await page.getByRole('heading',{name:'sneakers',exact:true}).waitFor();
 assert.equal(await page.getByRole('heading',{name:'Standard suite — judgement coverage',exact:true}).count(),1);
 assert.equal(await page.locator('#json').getAttribute('href'),'/api/delivery/operations/'+id+'/report?format=json');
 const out=path.join(process.env.LAB_STATE_DIR||'.lab','ui-qa');fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'readable-report-fixture.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,'readable-report-mobile-fixture.png'),fullPage:true});
 report={kind:'controlled-api-comparison',query_count:4,metrics:{baseline:{ndcg_at_10:.7},candidate:{ndcg_at_10:.71}},changed_query_ids:['q1'],result_similarity:{rbo_at_10_p_0_9:.8,jaccard_at_10:.9}};await page.goto(url+'/report');await page.getByRole('cell',{name:'candidate vs baseline',exact:true}).waitFor();
 report={reports:{relevance:{sha256:'b'.repeat(64)},performance:{sha256:'c'.repeat(64)}}};await page.goto(url+'/report');await page.getByRole('link',{name:'Open relevance report'}).waitFor();assert.equal(await page.getByRole('link',{name:'Open relevance report'}).getAttribute('href'),'/api/delivery/operations/'+id+'/report/relevance');
 report={kind:'paired-api-performance',valid:true,profile:'production-load',verdict:'within-budget',measured_phases:{normal:{budget:{p95_ms:250,p99_ms:500,failed_percent:1},baseline:{p95_ms:20,p99_ms:40,failed_percent:0,within_budget:true},candidate:{p95_ms:25,p99_ms:45,failed_percent:0,within_budget:true}}}};await page.goto(url+'/report/performance');await page.getByRole('heading',{name:'normal',exact:true}).waitFor();assert.ok((await page.locator('#content').innerText()).includes('p95 ≤250 ms'));
 operation={...operation,state:'failed',progress:'Operation failed',error:'<script>alert(1)</script>',result:null};await page.goto(url);await page.getByRole('heading',{name:'What happened'}).waitFor();assert.equal(await page.locator('#state').innerText(),'Failed');assert.ok((await page.locator('#content').innerText()).includes('<script>'));
 denied=true;await page.locator('#refresh').click();await page.getByText('Sign in to the lab.',{exact:true}).waitFor();assert.equal(await page.locator('#signin').isVisible(),true);
 assert.deepEqual(errors,[]);console.log('Progress refresh, gate/coverage separation, extra sets, mobile layout, failure escaping and sign-in passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
