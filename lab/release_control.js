/* The panel submits named requests; approval and evidence stay in the coordinator. */
(() => {
 const $=id=>document.getElementById(id);
 let data=null,options=null,loading=false,sending=false,epoch=0;
 const keys=new Map();
 const byStage={integration:['integration'],staging:['staging'],candidate:['prepare'],production:['release','rollback']};
 async function request(path,body,key){
  const r=await fetch(path,{method:body?'POST':'GET',headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-Lab-Intent':'1','Idempotency-Key':key}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const type=r.headers.get('content-type')||'';
  if(!type.includes('application/json'))throw new Error('The service is unavailable or sign-in expired. Refresh and sign in again.');
  const v=await r.json();if(!r.ok)throw new Error(v.error||'Request failed');return v;
 }
 function link(href,label,parent){const a=document.createElement('a');a.href=href;a.textContent=label;parent.append(a);return a;}
 function render(){
  if(!options)return;
  $('promotion-actions').replaceChildren();
  for(const name of byStage[$('promotion-stage').value]){
   const a=options.actions.find(x=>x.name===name),group=document.createElement('div'),button=document.createElement('button');
   button.textContent=a.label;button.disabled=!a.enabled||sending;button.onclick=()=>submit(name);group.append(button);
   const help=document.createElement('p');help.className='action-help';help.textContent=a.reason||(name==='release'?'Runs the production load gate and final comparison.':'Creates a proposal for review.');group.append(help);$('promotion-actions').append(group);
  }
  const deploy=options.actions.find(x=>x.name==='deploy');
  $('deploy-proposal').disabled=!deploy.enabled||!$('approved-proposal').value||sending;
  $('deploy-reason').textContent=deploy.reason||'The coordinator rechecks exact approval and evidence before merging and verifying.';
  $('proposal-link').replaceChildren();const pr=options.approved_prs.find(p=>String(p.number)===$('approved-proposal').value);if(pr)link(pr.url,'Review PR #'+pr.number+' in Gitea',$('proposal-link'));
  for(const node of document.querySelectorAll('.tree-node'))node.setAttribute('aria-pressed',String(node.dataset.stage===$('promotion-stage').value));
 }
 async function load(value){
  data=value;const current=++epoch;options=null;
  if(!data.selected){$('promotion-panel').hidden=true;return;}
  $('promotion-panel').hidden=false;loading=true;$('control-state').textContent='Loading available actions…';$('promotion-actions').replaceChildren();$('deploy-proposal').disabled=true;
  for(const [i,node] of [...document.querySelectorAll('.tree-node')].entries()){
   const stage=['source','integration','staging','candidate','production'][i];if(stage==='source')continue;
   node.dataset.stage=stage;node.setAttribute('role','button');node.tabIndex=0;node.setAttribute('aria-label',node.querySelector('h3').textContent+' promotion controls');
   node.onclick=()=>{ $('promotion-stage').value=stage;render();$('promotion-panel').scrollIntoView({behavior:'smooth',block:'start'});$('promotion-stage').focus({preventScroll:true});};
   node.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();node.click();}};
  }
  try{
   const result=await request('/api/delivery/dashboard/actions?run='+data.selected.run);if(current!==epoch)return;
   options=result;const previous=$('approved-proposal').value;$('approved-proposal').replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent=result.approved_prs.length?'Select an approved proposal':'No approved proposals';$('approved-proposal').append(empty);
   for(const pr of result.approved_prs){const option=document.createElement('option');option.value=pr.number;option.textContent='PR #'+pr.number;$('approved-proposal').append(option);}
   if(result.approved_prs.some(p=>String(p.number)===previous))$('approved-proposal').value=previous;
   $('approved-proposal').disabled=!result.actions.find(a=>a.name==='deploy').enabled;
   $('control-state').textContent='Build '+data.selected.run+' · select a stage to review its next action.';
   const base='https://gitea.localhost:34443/elastic-agent/delivery-source/src/commit/'+encodeURIComponent(data.selected.source_sha);
   $('customisation-links').replaceChildren();for(const [path,label] of [['configurations','Variants'],['gate/selection.json','Query sets and intent'],['gate/policy.json','Gate policy']])link(base+'/'+path,label,$('customisation-links'));
   render();
  }catch(e){if(current===epoch){$('control-state').textContent=e.message;$('approved-proposal').disabled=true;}}
  finally{if(current===epoch)loading=false;}
 }
 async function submit(action){
  if(sending||loading||!options)return;
  const body={run:data.selected.run,action,intent:$('promotion-intent').value,context:options.context};
  if(action==='deploy')body.pr=Number($('approved-proposal').value);
  sending=true;render();
  const encoded=JSON.stringify(body);if(!keys.has(encoded)){
   // Stable across reloads and network retries for the exact semantic request.
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(encoded));keys.set(encoded,'release-'+[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join(''));
  }
  $('promotion-feedback').textContent='Submitting '+action+' for build '+body.run+'…';
  try{const row=await request('/api/delivery/dashboard/actions',body,keys.get(encoded));$('promotion-feedback').replaceChildren();const text=document.createElement('p');text.textContent='Operation '+row.state+'.';$('promotion-feedback').append(text);link('/api/delivery/operations/'+encodeURIComponent(row.id),'Open progress and review links',$('promotion-feedback'));
   if(['failed','interrupted'].includes(row.state)){const retry=document.createElement('button');retry.textContent='Submit a new attempt';retry.onclick=()=>{keys.set(encoded,crypto.randomUUID());submit(action);};$('promotion-feedback').append(retry);}
  }catch(e){$('promotion-feedback').textContent=e.message;}
  finally{sending=false;render();}
 }
 $('promotion-stage').onchange=render;$('approved-proposal').onchange=render;$('deploy-proposal').onclick=()=>submit('deploy');
 function invalidate(){options=null;epoch++;$('promotion-panel').hidden=true;$('deploy-proposal').disabled=true;}
 window.releaseControls={load,invalidate};
})();
