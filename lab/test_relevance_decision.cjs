const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let state='pass',status=200,admin=true;
  await page.route('https://control.test/**',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname==='/relevance-decision')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'relevance-decision.html'),'utf8')});
   const value=status!==200?{error:status===401?'Sign in to the lab.':'Access denied.'}:u.pathname==='/api/me'?{username:'demo',is_admin:admin}:{report_url:'/report',result:{gate:{state,variants:[{variant:'ranker-a',delta:0,judged_fraction:.81,state}]}},request:{pr:31}};
   return route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
  });
  const url='https://control.test/relevance-decision?operation='+'a'.repeat(32);
  for(const value of ['pass','approved_exception','blocked','decision_required']){
   state=value;await page.goto(url);await page.waitForFunction(()=>document.getElementById('message').textContent!=='Loading comparison…');
   assert.equal(await page.locator('#signin').isVisible(),false);
   assert.equal(await page.locator('#decision').isVisible(),value==='decision_required');
   if(value==='pass')assert.equal(await page.locator('#message').innerText(),'Merge gate passed. No relevance decision is needed.');
  }
  admin=false;await page.goto(url);await page.getByText('A human lab administrator must request this decision.',{exact:true}).waitFor();assert.equal(await page.locator('#signin').isVisible(),false);
  for(const code of [403,401]){status=code;await page.goto(url);await page.waitForFunction(()=>document.getElementById('message').textContent!=='Loading comparison…');assert.equal(await page.locator('#signin').isVisible(),code===401);}
  assert.deepEqual(errors,[]);console.log('Passed, accepted, blocked, actionable and unauthorised decision-page states passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
