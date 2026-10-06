const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1000,height:1000}}),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 let admin=true,prepared=true,same=false;
 const slots={blue:{software_release_id:'a'.repeat(64),source_sha:'b'.repeat(40),fingerprint:'c'.repeat(64)},green:{software_release_id:'d'.repeat(64),source_sha:'e'.repeat(40),fingerprint:'f'.repeat(64)}};
 const production={...slots.blue,build_run:108,image:'nexus.test/search@sha256:'+ 'a'.repeat(64),dataset_release:'esci-gb-v1',index:'esci-frozen',engine:'9.5.4',verified:true};
 const candidate={...slots.green,build_run:109,image:'nexus.test/search@sha256:'+ 'd'.repeat(64),dataset_release:'esci-gb-v1',index:'esci-frozen',engine:'9.5.4',verified:true};
 await page.route('https://control.test/**',async route=>{
 const req=route.request(),u=new URL(req.url());
 if(u.pathname==='/production-release')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'production-release.html'),'utf8')});
 if(u.pathname==='/api/me')return route.fulfill({json:{username:'reviewer',is_admin:admin}});
 if(u.pathname==='/api/delivery/production')return route.fulfill({json:{active:prepared?'blue':null,slots:prepared?slots:{},production,candidate:{...(same?production:candidate),prepared_slot:prepared?'green':null},can_rollback:prepared,browser_url:'https://production.test/'}});
 if(u.pathname==='/api/delivery/operations'){requests.push(req.postDataJSON());assert.equal(req.headers()['x-lab-intent'],'1');assert.ok(req.headers()['idempotency-key']);return route.fulfill({status:202,json:{id:'a'.repeat(32)}})}
 throw new Error('Unexpected route '+u.pathname);
 });
 await page.goto('https://control.test/production-release');await page.getByText('Active slot: blue',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Prepare production candidate'}).click();await page.getByRole('link',{name:'Open progress and review links'}).waitFor();assert.deepEqual(requests.pop(),{kind:'prepare-production'});
 await page.getByRole('button',{name:'Check and release production'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'release-production',intent:'ranking-change'});
 await page.locator('#pr').fill('42');await page.getByRole('button',{name:'Deploy approved PR'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'merge-reviewed',pr:42});
 await page.getByRole('button',{name:'Request rollback to the other slot'}).click();await page.getByText('Operation queued.',{exact:false}).waitFor();assert.deepEqual(requests.pop(),{kind:'rollback',target:'production',fingerprint:'f'.repeat(64),intent:'ranking-change'});
 admin=false;await page.getByRole('button',{name:'Refresh status'}).click();await page.waitForFunction(()=>document.querySelector('#prepare').disabled);assert.equal(await page.locator('#release').isDisabled(),true);assert.deepEqual(errors,[]);
 admin=true;prepared=false;await page.getByRole('button',{name:'Refresh status'}).click();await page.getByText('Candidate is in staging; not yet prepared in production.').waitFor();
 assert.equal(await page.locator('#release-details').getByRole('link',{name:'108',exact:true}).count(),1);
 assert.equal(await page.locator('#release-details').getByRole('link',{name:'109',exact:true}).count(),1);
 assert.equal(await page.locator('#release').isDisabled(),true);assert.equal(await page.locator('#prepare').isEnabled(),true);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 same=true;await page.getByRole('button',{name:'Refresh status'}).click();await page.getByText('Staging matches active production.',{exact:false}).waitFor();assert.equal(await page.locator('#prepare').isDisabled(),true);
 assert.deepEqual(errors,[]);console.log('Release details before preparation, build links, mobile layout, matching releases, named operations and reader restrictions passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

