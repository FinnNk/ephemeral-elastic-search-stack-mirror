const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 data.variant_selection={state:'ready',source_sha:data.selected.source_sha,variants:[
  {variant:'ranker-a',intent:'ranking-change',default:true},
  {variant:'control',intent:'preserve-results',default:false}]};
 const errors=[],posts=[],acceptedKeys=new Set();let admin=true,failTransport=true,failedAttempt=false;
 const names=['integration','staging','prepare','release','deploy','rollback'];
 const comparisons=Object.fromEntries(names.filter(n=>n!=='deploy').map(name=>[name,{
  baseline:{state:'ready',target:name==='integration'||name==='staging'?name:'production-blue',build_run:108,version:'1.0.0',source_sha:'b'.repeat(40),variant:name==='staging'?'staging-default':'live-default',configuration_sha256:'b'.repeat(64)},
  candidate:{build_run:data.selected.run,version:'1.1.0',source_sha:'a'.repeat(40),selection:data.variant_selection},preparation_only:name==='prepare'}]));
 const server=http.createServer((req,res)=>{
  if(req.url.startsWith('/api/delivery/dashboard/actions')){
   res.setHeader('Content-Type','application/json');
   if(req.method==='POST'){
    let body='';req.on('data',c=>body+=c);req.on('end',()=>{
     posts.push({body:JSON.parse(body),key:req.headers['idempotency-key']});assert.equal(req.headers['x-lab-intent'],'1');
     if(failTransport){failTransport=false;res.writeHead(503);res.end(JSON.stringify({error:'Temporary transport failure; retry the same request.'}));return;}
     const key=req.headers['idempotency-key'],reused=acceptedKeys.has(key);acceptedKeys.add(key);
     res.writeHead(202);res.end(JSON.stringify({id:'a'.repeat(32),state:failedAttempt?'failed':'queued',submission_reused:reused,created_at:'2026-10-15T15:30:00Z',error:failedAttempt?'Performance budget missed <script>private()</script>':null}));
    });return;
   }
   res.end(JSON.stringify({context:'b'.repeat(64),comparisons,actions:names.map(name=>({name,label:{release:'Check and request production release',deploy:'Deploy approved proposal'}[name]||name,enabled:admin,reason:admin?'':'Administrator access is required.'})),approved_prs:[{number:25,url:'https://gitea.test/pulls/25'}]}));return;
  }
  if(req.url.startsWith('/api/delivery/dashboard')){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));return;}
  const name=req.url.split('?')[0].slice(1);const file=['lab-design.css','release_control.js','release_dashboard.js'].includes(name)?name:'release-dashboard.html';
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(path.join(__dirname,file)));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL});
  const page=await browser.newPage({viewport:{width:1600,height:1100}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/release-dashboard?run=158');
  await page.locator('#control-state').filter({hasText:'select a stage'}).waitFor();
  assert.equal(await page.locator('#variant-selection tbody tr').count(),2);
  assert.ok((await page.locator('#variant-selection').innerText()).includes('ranker-a · default'));
  assert.ok((await page.locator('#variant-selection').innerText()).includes('Intentional ranking change'));
  assert.ok((await page.locator('#variant-selection').innerText()).includes('Preserve search results'));
  assert.equal(await page.locator('#promotion-intent').count(),0);
  assert.equal(await page.locator('#promotion-actions tbody tr').count(),3);
  assert.ok((await page.locator('#promotion-actions').innerText()).includes('Intentional ranking change'));
  assert.ok((await page.locator('#promotion-actions').innerText()).includes('Preserve search results'));
  assert.ok((await page.locator('#promotion-actions').innerText()).includes('live-default'));
  assert.ok((await page.locator('#promotion-actions').innerText()).includes('1.1.0 · '+ 'a'.repeat(12)));
  await page.locator('#promotion-stage').selectOption('staging');
  assert.ok((await page.locator('#promotion-actions').innerText()).includes('staging-default'));
  await page.locator('.tree-node').last().press('Enter');assert.equal(await page.locator('#promotion-stage').inputValue(),'production');
  const release=page.getByRole('button',{name:'Check and request production release',exact:true});await release.click();await page.locator('#promotion-feedback').filter({hasText:'Temporary transport failure'}).waitFor();
  await release.click();await page.getByRole('link',{name:'Open progress and review links',exact:true}).waitFor();
  assert.equal(posts.length,2);assert.equal(posts[0].key,posts[1].key);assert.equal(posts[1].body.run,158);assert.equal(posts[1].body.action,'release');
  assert.equal('intent' in posts[1].body,false);
  await page.getByRole('heading',{name:'New attempt — queued',exact:true}).waitFor();
  failedAttempt=true;await page.reload();await page.locator('#control-state').filter({hasText:'select a stage'}).waitFor();
  await page.locator('#promotion-stage').selectOption('production');await release.click();
  await page.getByRole('heading',{name:'Existing attempt — failed',exact:true}).waitFor();
  assert.ok((await page.locator('#promotion-feedback').innerText()).includes('No new checks were started'));
  assert.ok((await page.locator('#promotion-feedback').innerText()).includes('Originally submitted:'));
  assert.ok((await page.locator('#promotion-feedback').innerText()).includes('Performance budget missed <script>'));
  assert.equal(await page.locator('#promotion-feedback script').count(),0);
  assert.equal(await page.getByRole('link',{name:'Review previous attempt',exact:true}).count(),1);
  assert.equal(posts.at(-1).key,posts[1].key);
  failedAttempt=false;await page.getByRole('button',{name:'Start a new attempt',exact:true}).click();
  await page.getByRole('heading',{name:'New attempt — queued',exact:true}).waitFor();
  assert.notEqual(posts.at(-1).key,posts[1].key);
  await release.click();await page.getByRole('heading',{name:'Existing attempt — queued',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'Follow existing attempt',exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Start a new attempt',exact:true}).count(),0);
  await page.locator('#approved-proposal').selectOption('25');await page.getByRole('button',{name:'Deploy approved proposal',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#promotion-feedback').textContent.includes('queued'));assert.equal(posts.at(-1).body.pr,25);
  admin=false;await page.locator('#refresh').click();await page.locator('#deploy-reason').filter({hasText:'Administrator access'}).waitFor();assert.equal(await release.isDisabled(),true);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,keyboard:true,stable_retry_key:true,approved_selection:true,reader:true,mobile_overflow:false,posts:posts.length}));
 }finally{await browser?.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
