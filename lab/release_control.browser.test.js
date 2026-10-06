const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const errors=[],posts=[];let admin=true,failTransport=true;
 const names=['integration','staging','prepare','release','deploy','rollback'];
 const server=http.createServer((req,res)=>{
  if(req.url.startsWith('/api/delivery/dashboard/actions')){
   res.setHeader('Content-Type','application/json');
   if(req.method==='POST'){
    let body='';req.on('data',c=>body+=c);req.on('end',()=>{
     posts.push({body:JSON.parse(body),key:req.headers['idempotency-key']});assert.equal(req.headers['x-lab-intent'],'1');
     if(failTransport){failTransport=false;res.writeHead(503);res.end(JSON.stringify({error:'Temporary transport failure; retry the same request.'}));return;}
     res.writeHead(202);res.end(JSON.stringify({id:'a'.repeat(32),state:'queued'}));
    });return;
   }
   res.end(JSON.stringify({context:'b'.repeat(64),actions:names.map(name=>({name,label:{release:'Check and request production release',deploy:'Deploy approved proposal'}[name]||name,enabled:admin,reason:admin?'':'Administrator access is required.'})),approved_prs:[{number:25,url:'https://gitea.test/pulls/25'}]}));return;
  }
  if(req.url.startsWith('/api/delivery/dashboard')){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));return;}
  const name=req.url.split('?')[0].slice(1);const file=['lab-design.css','release_control.js','release_dashboard.js'].includes(name)?name:'release-dashboard.html';
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(path.join(__dirname,file)));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/release-dashboard?run=158');
  await page.locator('#control-state').filter({hasText:'select a stage'}).waitFor();
  await page.locator('.tree-node').last().press('Enter');assert.equal(await page.locator('#promotion-stage').inputValue(),'production');
  const release=page.getByRole('button',{name:'Check and request production release',exact:true});await release.click();await page.locator('#promotion-feedback').filter({hasText:'Temporary transport failure'}).waitFor();
  await release.click();await page.getByRole('link',{name:'Open progress and review links',exact:true}).waitFor();
  assert.equal(posts.length,2);assert.equal(posts[0].key,posts[1].key);assert.equal(posts[1].body.run,158);assert.equal(posts[1].body.action,'release');
  await page.locator('#approved-proposal').selectOption('25');await page.getByRole('button',{name:'Deploy approved proposal',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#promotion-feedback').textContent.includes('queued'));assert.equal(posts.at(-1).body.pr,25);
  admin=false;await page.locator('#refresh').click();await page.locator('#deploy-reason').filter({hasText:'Administrator access'}).waitFor();assert.equal(await release.isDisabled(),true);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,keyboard:true,stable_retry_key:true,approved_selection:true,reader:true,mobile_overflow:false,posts:posts.length}));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
