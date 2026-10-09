'use strict';
// Browser verification: navigation, responsive tree and GET-only requests.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fields={software_version:'1.0.0+build.158.1',source_sha:'a'.repeat(40),software_release_id:'b'.repeat(64),dataset_release:'esci-gb-v1',index:'catalogue',image:'search@sha256:'+'c'.repeat(64)};
const envs=['integration','staging','production-blue','production-green'].map(name=>({name,definition:fields,ready:true,active:name==='production-blue',slot:name.startsWith('production-')?name.split('-')[1]:null,replicas:1,ready_replicas:1,sync:'Synced',health:'Healthy'}));
const operation={id:'123',kind:'promotion',target:'staging',state:'complete',progress:'Complete',intent:'ranking-change',updated_at:'2026-10-06T15:00:00Z',duration_seconds:123,url:'/api/delivery/operations/123',report_url:'/api/delivery/operations/123/report',pr:{number:24,state:'merged',url:'https://gitea.localhost:34443/elastic-agent/delivery-state/pulls/24'}};
const fixture={updated_at:'2026-10-06T16:00:00Z',releases:Array.from({length:12},(_,i)=>({run:158-i,source_sha:'a'.repeat(40),state:i===0?'candidate ready':'built',environments:i===0?['staging']:[],created_at:'2026-10-06T13:00:00Z'})),selected:{run:158,source_sha:fields.source_sha,release_id:fields.software_release_id},build:{state:'success',url:'https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/158',duration_seconds:45},source:{state:'merged',number:31,title:'<img src=x onerror=alert(1)>',message:'Recorded source gate before merge.',gate:{state:'pass',variants:[{variant:'ranker-a',state:'pass'}]},gate_url:'/api/delivery/operations/source'},release:fields,stages:['integration','staging','candidate','production'].map((name,i)=>({name,title:['Integration','Staging','Production candidate','Active production'][i],state:['verified','verified','prepared','pending'][i],message:'Recorded release progress.',environment:i===3?null:envs[i],operation:i===1?operation:null,checks:i===1?[{name:'performance',verdict:'within-budget',url:'/report/performance'}]:[],verification:i<2?{verified_at:'2026-10-06T15:00:00Z',seconds:2,git_revision:'d'.repeat(40)}:null})),active_production:envs[2],environments:envs,activity:[operation],unbound_operations:[],notices:[],limits:'Bounded recorded history.'};
async function main(){
  const requests=[],errors=[];let responseStatus=200;
  const livePath=process.argv[2],live=livePath?JSON.parse(fs.readFileSync(livePath,'utf8')):null;
  const server=http.createServer((req,res)=>{
    requests.push(req.method+' '+req.url);
    if(req.url.startsWith('/api/delivery/dashboard/actions')){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({context:'a'.repeat(64),actions:['integration','staging','prepare','release','deploy','rollback'].map(name=>({name,label:name,enabled:false,reason:'Read-only fixture'})),approved_prs:[]}));return;}
    if(req.url.startsWith('/api/delivery/dashboard')){
      res.writeHead(responseStatus,{'Content-Type':'application/json'});
      const run=Number(new URL(req.url,'http://localhost').searchParams.get('run'))||158;
      res.end(JSON.stringify(responseStatus===200?(live||{...fixture,selected:{...fixture.selected,run}}):{error:'Sign in'}));return;
    }
    const file=req.url.startsWith('/release_control.js')?'release_control.js':req.url.startsWith('/lab-design.css')?'lab-design.css':req.url.startsWith('/release_dashboard.js')?'release_dashboard.js':'release-dashboard.html';
    res.writeHead(200,{'Content-Type':file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html'});res.end(fs.readFileSync(path.join(__dirname,file)));
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1600,height:1100}});page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/release-dashboard');await page.locator('.release-card').first().waitFor();
    if(!live){
      assert.equal(await page.locator('.release-card').count(),9);
      await page.locator('#next-page').click();assert.equal(await page.locator('.release-card').count(),3);
      await page.locator('#release-status').selectOption('candidate ready');assert.equal(await page.locator('.release-card').count(),1);
      await page.locator('#release-search').fill('missing');assert.equal(await page.locator('.release-card').count(),0);
      await page.locator('#release-search').fill('158');assert.equal(await page.locator('.release-card').count(),1);
    }
    const out=process.env.DASHBOARD_SCREENSHOTS;
    if(out){await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(300);}if(out)await page.screenshot({path:path.join(out,'release-catalogue.png'),fullPage:true});
    await page.goto(base+'/release-dashboard?run=158');await page.locator('.tree-node').first().waitFor();
    assert.equal(await page.locator('.tree-node').count(),5);assert.ok(await page.locator('svg .edge').count()>=8);
    assert.equal(await page.locator('.tree-detail img').count(),0);
    if(!live)assert.ok((await page.locator('body').innerText()).includes('1.0.0+build.158.1'));
    await page.getByRole('tab',{name:'Inputs & policy'}).click();assert.ok(await page.locator('#view-inputs').isVisible());
    await page.getByRole('tab',{name:'Inputs & policy'}).press('ArrowRight');assert.ok(await page.locator('#view-activity').isVisible());
    await page.getByRole('tab',{name:'Overview',exact:true}).click();
    if(out){await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(300);}if(out)await page.screenshot({path:path.join(out,'release-tree.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
    assert.ok(await page.locator('.tree-viewport').evaluate(e=>e.scrollWidth>e.clientWidth));
    if(out){await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(300);}if(out)await page.screenshot({path:path.join(out,'release-tree-mobile.png'),fullPage:true});
    responseStatus=401;await page.locator('#refresh').click();await page.getByRole('link',{name:'Sign in to the lab'}).waitFor();
    assert.equal(requests.some(r=>!r.startsWith('GET ')),false);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,read_only_requests:requests.length,tree_nodes:5,fixture:live?'retained live snapshot':'synthetic scenarios'}));
  }finally{await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
