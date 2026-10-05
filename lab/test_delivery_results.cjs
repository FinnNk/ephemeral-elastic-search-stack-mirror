const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const id='a'.repeat(32),url='http://control.test/api/delivery/operations/'+id;
 let denied=false,operation={id,state:'running',progress:'Capturing fresh results: standard',created_at:'2026-10-05T19:59:00Z',updated_at:'2026-10-05T20:00:00Z',request:{kind:'compare',pr:31,source_sha:'b'.repeat(40)},result:null};
 const standard={kind:'variant-evaluation-report',complete:true,baseline_variant:'baseline',query_count:1000,execution:{seconds:12.5,worker_count:8,pacing:{'lab-baseline':{attempts:1001,successes:1000,retries:1,transient_failures:0,terminal_failures:0,wait_seconds:0}}},variants:{baseline:{},'ranker-a':{}},metrics:{baseline:{'nDCG@10':.7,'Judged@10':.81},'ranker-a':{'nDCG@10':.71,'Judged@10':.82}},result_changes:{'ranker-a':{changed_queries:2}},result_similarity:{baseline:{rbo_at_10_p_0_9:1,jaccard_at_10:1},'ranker-a':{rbo_at_10_p_0_9:.98,jaccard_at_10:.99}},coverage:{baseline:{fraction:.81,judged:8100,returned:10000},'ranker-a':{fraction:.82,judged:8200,returned:10000}}};
 const extra={...standard,execution:{seconds:2,worker_count:8},query_count:4,metrics:null,relevance_available:false,coverage:{baseline:{fraction:0,judged:0,returned:40},'ranker-a':{fraction:0,judged:0,returned:40}}};
 standard.ndcg_significance={comparisons:{'ranker-a':{'nDCG@10':{mean_difference:.01,confidence_interval_95:[.002,.018],p_value:.01,adjusted_p_value:.02,significant:true,paired_queries:998,request_groups:990,excluded_queries:2}}}};
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
 assert.equal(await page.locator('#state').innerText(),'Merge gate: Passed');
 assert.ok((await page.locator('#content').innerText()).includes('60 s'));
 assert.ok((await page.locator('#content').innerText()).includes('12.5 s'));
 assert.ok((await page.locator('#content').innerText()).includes('not a load test'));
 const captureTable=page.getByRole('heading',{name:'Search capture requests',exact:true}).locator('..').locator('table');
 assert.deepEqual(await captureTable.locator('thead th').allTextContents(),['Query set','API environment','Attempts','Successes','Retries','Transient failures','Terminal failures','Pacing wait (s)']);
 assert.deepEqual((await captureTable.locator('tbody tr').first().locator('td').allTextContents()).slice(2,5),['1,001','1,000','1']);
 assert.equal(await page.locator('#decision').isVisible(),false);
 const stats=page.getByRole('heading',{name:'Standard suite — nDCG significance',exact:true}).locator('..');
 assert.ok((await stats.innerText()).includes('Informational only; gates are unchanged.'));
 assert.equal(await stats.getByRole('cell',{name:'Yes',exact:true}).count(),1);
 assert.ok((await stats.innerText()).includes('0.002 to 0.018'));
 assert.ok((await stats.innerText()).includes('998'));
 assert.equal(await page.locator('#content section h2').first().innerText(),'Merge gate');
 assert.ok((await page.locator('#content').innerText()).includes('Relevance scores are unavailable'));
 assert.ok((await page.locator('#content').innerText()).includes('accuracy remains unqualified'));
 assert.equal(await page.getByRole('heading',{name:'Combined view',exact:true}).count(),1);
 assert.equal(await page.getByRole('cell',{name:'ranker-a vs baseline',exact:true}).count(),5);
 assert.equal(await page.getByRole('cell',{name:'baseline vs baseline',exact:true}).count(),0);
 assert.equal(await page.getByRole('columnheader',{name:'RBO@10 (p = 0.9)',exact:true}).count(),3);
 assert.ok((await page.locator('#content').innerText()).includes('no usable judgement snapshot'));
 assert.equal(await page.getByRole('columnheader',{name:'nDCG@10',exact:true}).count(),3);
 // New resolution receipts explain why a score cannot be calculated.
 const resolved={...extra,ndcg_significance:{comparisons:{'ranker-a':{'nDCG@10':{paired_queries:0,request_groups:0,excluded_queries:4,unavailable_reason:'No paired finite scores with positive reference gain.'}}}},relevance_unavailable_reason:'All model responses abstained.',delta_from_baseline:{'ranker-a':{'nDCG@10':null,'nDCG@5':null}},judgement_resolution:{counts:{pool:{required:6,stored:0,newly_labelled:0,abstained:6,failed:0}},execution:{stored_pairs:0,cache_hits:0,inferred_pairs:6}}};
 report={...standard,query_sets:{standard,sneakers:resolved},query_set_metadata:{standard:{required:true},sneakers:{required:false}}};
 await page.goto(url+'/report');await page.getByRole('heading',{name:'sneakers — judgement resolution',exact:true}).waitFor();
 assert.ok((await page.locator('#content').innerText()).includes('Not calculable: All model responses abstained.'));
 assert.ok((await page.locator('#content').innerText()).includes('Pairs sent to the model'));
 assert.equal(await page.getByRole('cell',{name:'Insufficient data',exact:true}).count(),1);
 // Each candidate has its own comparison against the named baseline.
 report={...standard,variants:{...standard.variants,'ranker-b':{}},metrics:{...standard.metrics,'ranker-b':{'nDCG@10':.69}},result_changes:{...standard.result_changes,'ranker-b':{changed_queries:10}},result_similarity:{...standard.result_similarity,'ranker-b':{rbo_at_10_p_0_9:.9,jaccard_at_10:.95}}};
 await page.goto(url+'/report');await page.getByRole('cell',{name:'ranker-b vs baseline',exact:true}).waitFor();
 assert.equal(await page.getByRole('cell',{name:'ranker-a vs baseline',exact:true}).count(),3);
 report={...standard,judgement_selection:'demo',query_sets:{standard,sneakers:extra},query_set_metadata:{standard:{required:true},sneakers:{required:false}},combined:{metrics:standard.metrics,result_similarity:standard.result_similarity,query_count:1004,relevance_query_count:1000,unlabelled_query_count:4}};
 await page.goto(url+'/report');await page.getByRole('heading',{name:'sneakers',exact:true}).waitFor();
 assert.equal(await page.getByRole('heading',{name:'Standard suite — judgement coverage',exact:true}).count(),1);
 assert.equal(await page.locator('#json').getAttribute('href'),'/api/delivery/operations/'+id+'/report?format=json');
 const out=path.join(process.env.LAB_STATE_DIR||'.lab','ui-qa');fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'readable-report-fixture.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,'readable-report-mobile-fixture.png'),fullPage:true});
 for(const state of ['decision_required','blocked','approved_exception']){
  operation={...operation,decision_url:state==='decision_required'?'/relevance-decision?operation='+id:null,result:{...operation.result,gate:{state}}};
  await page.goto(url+'/report');await page.waitForFunction(()=>document.getElementById('state').textContent.startsWith('Merge gate:'));
  assert.equal(await page.locator('#decision').isVisible(),state==='decision_required');
  assert.ok(!(await page.locator('#stage').innerText()).includes('No relevance decision is needed'));
 }
 operation={...operation,request:{kind:'promotion'},result:null,decision_url:null};
 report={kind:'controlled-api-comparison',query_count:4,metrics:{baseline:{ndcg_at_10:.7},candidate:{ndcg_at_10:.71}},changed_query_ids:['q1'],result_similarity:{rbo_at_10_p_0_9:.8,jaccard_at_10:.9}};await page.goto(url+'/report');await page.getByRole('cell',{name:'candidate vs baseline',exact:true}).waitFor();
 report={reports:{relevance:{sha256:'b'.repeat(64)},performance:{sha256:'c'.repeat(64)}}};await page.goto(url+'/report');await page.getByRole('link',{name:'Open relevance report'}).waitFor();assert.equal(await page.getByRole('link',{name:'Open relevance report'}).getAttribute('href'),'/api/delivery/operations/'+id+'/report/relevance');
 operation={...operation,state:'complete',request:{kind:'promotion'},report_url:url+'/report',result:{validation:{passed:true,detail:'Exact release verified; review required'},url:'https://gitea-internal.lab-ingress.svc.cluster.local/elastic-agent/delivery-state/pulls/17'}};
 await page.goto(url);await page.getByText('Ready for review',{exact:true}).waitFor();assert.equal(await page.locator('#report').innerText(),'Review promotion checks');
 report={state:'verified',environment:'lab-delivery-staging',seconds:4.5,merge_to_verified_seconds:9,verified_at:'2026-10-05T20:00:00Z',sample_ids:['p1','p2'],deployment:{build_run:108,fields:{image:'registry/search@sha256:abc',index:'esci-gb-v1',source_sha:'b'.repeat(40)}}};
 operation={...operation,request:{kind:'merge-reviewed'},result:{state:'verified'}};
 await page.goto(url+'/report');await page.getByRole('heading',{name:'Verified release',exact:true}).waitFor();assert.equal(await page.locator('#state').innerText(),'Deployment verified');assert.ok((await page.locator('#content').innerText()).includes('Merge to verified'));
 report={kind:'paired-api-performance',valid:true,profile:'production-load',verdict:'within-budget',baseline:{duration_seconds:15},candidate:{duration_seconds:15},measured_phases:{normal:{budget:{p95_ms:250,p99_ms:500,failed_percent:1},baseline:{p95_ms:20,p99_ms:40,failed_percent:0,within_budget:true},candidate:{p95_ms:25,p99_ms:45,failed_percent:0,within_budget:true}}}};await page.goto(url+'/report/performance');await page.getByRole('heading',{name:'normal',exact:true}).waitFor();assert.ok((await page.locator('#content').innerText()).includes('p95 ≤250 ms'));assert.equal(await page.getByRole('heading',{name:'Gatling workload duration',exact:true}).count(),1);
 operation={...operation,state:'failed',progress:'Operation failed',error:'<script>alert(1)</script>',result:null};await page.goto(url);await page.getByRole('heading',{name:'What happened'}).waitFor();assert.equal(await page.locator('#state').innerText(),'Failed');assert.ok((await page.locator('#content').innerText()).includes('<script>'));
 denied=true;await page.locator('#refresh').click();await page.getByText('Sign in to the lab.',{exact:true}).waitFor();assert.equal(await page.locator('#signin').isVisible(),true);
 assert.deepEqual(errors,[]);console.log('Progress refresh, gate/coverage separation, extra sets, mobile layout, failure escaping and sign-in passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
