const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1000,height:1000}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 let admin=true;
 const slots={blue:{software_release_id:'a'.repeat(64),source_sha:'b'.repeat(40),fingerprint:'c'.repeat(64)},green:{software_release_id:'d'.repeat(64),source_sha:'e'.repeat(40),fingerprint:'f'.repeat(64)}};
 await page.route('https://control.test/**',async route=>{
 const req=route.request(),u=new URL(req.url());
 if(u.pathname==='/production-release')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'production-release.html'),'utf8')});
 if(u.pathname==='/api/me')return route.fulfill({json:{username:'reviewer',is_admin:admin}});
 if(u.pathname==='/api/delivery/production')return route.fulfill({json:{active:'blue',slots,can_rollback:true,browser_url:'https://production.test/'}});
 if(u.pathname==='/api/delivery/operations'){requests.push(req.postDataJSON());assert.equal(req.headers()['x-lab-intent'],'1');assert.ok(req.headers()['idempotency-key']);return route.fulfill({status:202,json:{id:'a'.repeat(32)}})}
 throw new Error('Unexpected route '+u.pathname);
 });
 await page.goto('https://control.test/production-release');await page.getByText('Active slot: blue',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Prepare production candidate'}).click();await page.getByRole('link',{name:'Open progress and review links'}).waitFor();assert.deepEqual(requests.pop(),{kind:'prepare-production'});
 await page.getByRole('button',{name:'Check and release production'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'release-production',intent:'ranking-change'});
 await page.locator('#pr').fill('42');await page.getByRole('button',{name:'Deploy approved PR'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'merge-reviewed',pr:42});
 await page.getByRole('button',{name:'Request rollback to the other slot'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'rollback',target:'production',fingerprint:'f'.repeat(64),intent:'ranking-change'});
 admin=false;await page.getByRole('button',{name:'Refresh status'}).click();await page.waitForFunction(()=>document.querySelector('#prepare').disabled);assert.equal(await page.locator('#release').isDisabled(),true);assert.deepEqual(errors,[]);
 console.log('Production UI named operations, active slot, review links and reader restrictions passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

