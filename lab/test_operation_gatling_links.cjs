/* Terminal-operation report discovery, without a browser or network access. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.text='';}
 set textContent(value){this.text=String(value);this.children=[];}
 get textContent(){return this.text+this.children.map(c=>c.textContent).join('');}
 append(...items){this.children.push(...items);}
 addEventListener(){}
}
const ids=new Map(),document={createElement:tag=>new Element(tag),getElementById:id=>{if(!ids.has(id))ids.set(id,new Element('div'));return ids.get(id);}};
const operationPath='/api/delivery/operations/'+'a'.repeat(32),reportPath=operationPath+'/report';
let documents={},requests=[];
const context=vm.createContext({document,Node:Element,location:{pathname:operationPath},Date,URL,console,fetch:async url=>{
 requests.push(url);return {ok:Object.hasOwn(documents,url),json:async()=>documents[url]};
}});
const source=fs.readFileSync(path.join(__dirname,'delivery_results.js'),'utf8').replace("$('refresh').addEventListener('click',load);load();","$('refresh').addEventListener('click',load);");
vm.runInContext(source,context);
const performance={kind:'paired-api-performance',baseline:{native_report_blob:'baseline.zip',native_report_sha256:'b'.repeat(64)},candidate:{native_report_blob:'candidate.zip',native_report_sha256:'c'.repeat(64)}};
function descendants(n){return [n,...n.children.flatMap(descendants)];}
function links(){return descendants(document.getElementById('content')).filter(n=>n.tag==='a').map(n=>({text:n.textContent,href:n.href}));}
async function show(state,root,extra={}){
 document.getElementById('content').children=[];requests=[];documents={[reportPath]:root,...extra};context.row={state,report_url:reportPath};
 await vm.runInContext('operationGatlingReports(row)',context);
}
(async()=>{
 const check={variant:'ranker-a',evidence:{sha256:'saved'},performance_status:'completed'},root={kind:'delivery-variant-evidence',checks:[check]};
 for(const state of ['failed','complete','interrupted']){
  await show(state,root,{[reportPath+'/variant/ranker-a/performance']:performance});
  for(const side of ['baseline','candidate']){
   assert.ok(links().some(l=>l.text==='View '+side+' Gatling report'&&l.href===operationPath+'/gatling/ranker-a/'+side+'/index.html'));
   assert.ok(links().some(l=>l.text==='Download '+side+' ZIP'&&l.href===operationPath+'/gatling/ranker-a/'+side+'/download.zip'));
  }
 }
 await show('failed',{...root,checks:[{...check,performance_status:'not_run'}]});
 assert.deepEqual(links(),[]);assert.equal(requests.length,1);assert.ok(ids.get('content').textContent.includes('No performance evidence'));
 await show('failed',root);assert.deepEqual(links(),[]);assert.ok(ids.get('content').textContent.includes('temporarily unavailable'));
 await show('failed',root,{[reportPath+'/variant/ranker-a/performance']:{...performance,candidate:{}}});
 assert.equal(links().length,2);assert.ok(ids.get('content').textContent.includes('Candidate native report unavailable'));
 await show('failed',{kind:'paired-api-performance',...performance});assert.ok(links()[0].href.includes('/gatling/pair/'));
 await show('complete',{kind:'variant-evaluation-report',query_sets:{}});assert.equal(ids.get('content').textContent,'');
 await show('running',root);assert.equal(requests.length,0);
 documents={};context.row={state:'failed',report_url:reportPath};await vm.runInContext('operationGatlingReports(row)',context);
 assert.ok(ids.get('content').textContent.includes('availability could not be checked'));assert.deepEqual(links(),[]);
 console.log('Terminal states retain Gatling links; skipped, missing, unreadable and unrelated evidence is handled explicitly.');
})().catch(e=>{console.error(e);process.exitCode=1;});
