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
 function comparison(value,parent,action){
  const add=(tag,label,to=parent)=>{const node=document.createElement(tag);node.textContent=label;to.append(node);return node;};
  add('h3',value?.preparation_only?'Candidate preparation':'Planned comparison');
  if(value?.preparation_only)add('p','Preparation reuses verified staging. These variants are compared with active production in the later release check.').className='notice';
  const baseline=value?.baseline||{},candidate=value?.candidate||{build_run:data.selected.run,selection:data.variant_selection};
  const wrapper=add('div','');wrapper.className='table-wrap';const table=add('table','',wrapper),head=add('tr','',add('thead','',table));
  for(const label of ['Role','Build','Variant / configuration','Change intent'])add('th',label,head).scope='col';
  const body=add('tbody','',table);
  const row=(role,item,variant,intent,config)=>{const r=add('tr','',body);add('td',role,r);add('td',item.build_run==null?'Not available':String(item.build_run)+' · '+(item.version||'Version not recorded')+' · '+(item.source_sha?item.source_sha.slice(0,12):'Commit not recorded'),r);const cell=add('td',variant||'Not available',r);if(config){const code=add('code',config.slice(0,12),add('div','',cell));code.title=config;}add('td',intent,r);};
  const targetName=({'integration':'Integration','staging':'Staging','production-blue':'Active production · blue','production-green':'Active production · green'}[baseline.target]||baseline.target);
  row('Baseline'+(targetName?' · '+targetName:''),baseline,baseline.variant,'Reference',baseline.configuration_sha256);
  if(baseline.state!=='ready')add('p','The current target baseline is unavailable. Its identity will not be assumed.').className='notice';
  const plan=options?.check_plans?.[action];
  if(plan?.state==='recorded')add('p','The recorded release check plan supplies the intents below. Candidate configurations remain pinned by the source commit.');
  for(const variant of candidate.selection?.variants||[])row('Candidate',candidate,variant.variant+(variant.default?' · default':''),({'ranking-change':'Intentional ranking change','preserve-results':'Preserve search results'}[(plan?.state==='recorded'?plan.reviewed_variants?.find(v=>v.variant===variant.variant)?.intent:null)||variant.intent]||variant.intent),variant.configuration_sha256);
  if(candidate.selection?.state!=='ready')add('p','Candidate variants and intents are unavailable. Refresh to retry.').className='notice';
  if(candidate.selection?.source_sha)link('https://gitea.localhost:34443/elastic-agent/delivery-source/src/commit/'+encodeURIComponent(candidate.selection.source_sha)+'/gate/selection.json','Open source variant declaration',add('p',''));
 }
 const planEdits=new Map();
 function checkPlan(action,parent){
  const value=options.check_plans?.[action];if(!value)return;
  const add=(tag,text,to=parent)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;to.append(n);return n;};
  add('h3','Release check plan');
  if(value.state==='current'){add('p','This release is already verified in this environment. Review a plan at its next destination.');return;}
  const stateNames={needed:'A reviewed plan is required',suggested:'Suggested checks — review required',working:'Preparing the plan',recorded:'Approved plan recorded',approved:'Approved plan — ready to record',unavailable:'Plan unavailable','awaiting review':'Awaiting exact-head approval in Gitea'};
  add('p',stateNames[value.state]||value.state).className='notice';
  if(value.error)add('p',value.error);
  if(value.url)link(value.url,'Open plan PR #'+value.pr,add('p',''));
  if(value.operation_url)link(value.operation_url,'Follow plan operation',add('p',''));
  const button=(text,callback)=>{const b=add('button',text);b.type='button';b.disabled=sending||!options.plan_editor||['working','unavailable'].includes(value.state);b.onclick=callback;return b;};
  button(value.suggestion?'Suggest again from current releases':'Suggest checks from accumulated changes',()=>{const fields={run:value.run,target:value.target};if(value.target==='integration')for(const [key,field] of [['dataset','dataset_release'],['recipe','index_recipe_sha256'],['query_manifest','query_manifest_sha256'],['judgement_manifest','judgement_manifest_sha256']])if(data.release?.[field])fields[key]=data.release[field];submitPlan('suggest-release-plan',fields);});
  if(value.state==='approved')button('Record approved plan',()=>submitPlan('accept-release-plan',{pr:value.pr}));
  const suggestion=value.suggestion;if(!suggestion)return;
  const details=add('details','');details.open=value.state==='suggested';add('summary','Review or revise suggested checks',details);
  const box=add('div','',details);box.className='panel-body';
  const pin=suggestion.binding;
  add('p','Baseline build '+pin.baseline.build_run+' → candidate build '+pin.candidate.build_run+' · '+value.target,box);
  add('h4','Mandatory checks',box);
  add('p','Every standard query set remains required. This plan cannot remove or weaken them.',box);
  const mandatory=add('ul','',box);for(const item of pin.primary_query_sets)add('li',item.name||item.query_manifest_sha256,mandatory);
  add('h4','Accumulated changes',box);
  if(suggestion.ancestry.diverged)add('p','The source histories diverge. Review both sides of the change before confirming this plan.',box).className='notice';
  if(suggestion.ancestry.missing_declarations.length)add('p',suggestion.ancestry.missing_declarations.length+' historical commits have no query-set declaration. Explain how the selected checks cover this gap in the review reason.',box).className='notice';
  const changes=add('ul','',box);for(const c of suggestion.changes)link('https://gitea.localhost:34443/elastic-agent/delivery-source/commit/'+c.source_sha,(c.side==='baseline-only'?'Removed from baseline · ':'')+c.source_sha.slice(0,12)+' · '+c.title,add('li','',changes));
  if(!suggestion.changes.length)add('li','No source commits differ; review configuration and data changes.',changes);
  if(!planEdits.has(value.suggestion_id))planEdits.set(value.suggestion_id,value.reviewed_edits?structuredClone(value.reviewed_edits):{variants:suggestion.variants.map(v=>({...v})),suites:suggestion.suites.map(s=>({id:s.id,disposition:s.required?'required':'report_only',reason:''})),additional_query_sets:[],reason:''});
  const edits=planEdits.get(value.suggestion_id);
  const select=(values,current,onchange,to)=>{const select=add('select','',to);for(const [key,label] of values){const o=document.createElement('option');o.value=key;o.textContent=label;select.append(o);}select.value=current;select.disabled=!options.plan_editor;select.onchange=()=>onchange(select.value);return select;};
  const input=(label,current,onchange,to=box,tag='input')=>{const l=add('label',label+' ',to),n=add(tag,null,l);n.value=current||'';n.disabled=!options.plan_editor;n.oninput=()=>onchange(n.value);return n;};
  add('h4','Release intent for each candidate variant',box);
  for(const variant of edits.variants){const l=add('label',variant.variant+' ',box);select([['preserve-results','Preserve current results'],['ranking-change','Intentional ranking change']],variant.intent,v=>variant.intent=v,l);}
  add('h4','Inherited and current query sets',box);
  for(const item of suggestion.suites){
   const decision=edits.suites.find(s=>s.id===item.id),group=add('fieldset','',box);add('legend',item.name+' · '+item.query_sha256.slice(0,8),group);
   add('p',(item.required?'Inherited requirement':'Report only by default')+' · '+item.origins.length+' source declarations',group);
   link('https://gitea.localhost:34443/elastic-agent/delivery-source/src/commit/'+item.source_sha+'/'+item.path,'Open pinned queries',add('p','',group));
   const l=add('label','Use in this release ',group);select([['required','Required'],['report_only','Report only'],['retired','Retire / supersede']],decision.disposition,v=>decision.disposition=v,l);
   input('Reason for retirement or reduced requirement',decision.reason,v=>decision.reason=v,group,'textarea');
  }
  add('h4','Other query sets from the candidate commit',box);
  add('p','Choose existing evaluation JSONL files at this build’s source commit. Required sets need a matching reviewed judgement file.',box);
  for(const [index,item] of edits.additional_query_sets.entries()){
   const group=add('fieldset','',box);add('legend','Additional set '+(index+1),group);
   for(const [key,label] of [['name','Name'],['path','Query file'],['judgements','Judgement file (required for a required set)']])input(label,item[key],v=>{if(v)item[key]=v;else delete item[key];},group);
   const l=add('label','Requirement ',group);select([['report_only','Report only'],['required','Required']],item.required?'required':'report_only',v=>item.required=v==='required',l);
   const remove=add('button','Remove set',group);remove.type='button';remove.disabled=!options.plan_editor;remove.onclick=()=>{edits.additional_query_sets.splice(index,1);render();};
  }
  const extra=add('button','Add query set',box);extra.type='button';extra.disabled=!options.plan_editor;extra.onclick=()=>{edits.additional_query_sets.push({name:'',path:'',required:false});render();};
  input('Review reason: why these checks cover the combined release',edits.reason,v=>edits.reason=v,box,'textarea');
  const propose=add('button','Create plan PR for review',box);propose.type='button';propose.disabled=sending||!options.plan_editor||value.state==='working';propose.onclick=()=>submitPlan('propose-release-plan',{suggestion:value.suggestion_id,edits});
 }
 async function submitPlan(kind,fields){
  if(sending)return;sending=true;render();$('promotion-feedback').textContent='Submitting release check plan…';
  try{const row=await request('/api/delivery/operations',{kind,...fields},'plan-'+crypto.randomUUID());const feedback=$('promotion-feedback');feedback.replaceChildren();link('/api/delivery/operations/'+row.id,'Follow plan operation',feedback);await load(data);}
  catch(error){$('promotion-feedback').textContent=error.message;}
  finally{sending=false;render();}
 }
 function render(){
  if(!options)return;
  $('promotion-actions').replaceChildren();
  for(const name of byStage[$('promotion-stage').value]){
   const a=options.actions.find(x=>x.name===name),group=document.createElement('div'),button=document.createElement('button');
   group.className='promotion-check';
   comparison(options.comparisons?.[name],group,name);
   checkPlan(name,group);
   button.textContent=a.label;button.disabled=!a.enabled||sending;button.onclick=()=>{
    if(a.mode==='progress'||a.mode==='review'){const u=new URL(a.href,location.origin);if(['http:','https:'].includes(u.protocol)){if(u.hostname==='gitea-internal.lab-ingress.svc.cluster.local'){u.hostname='gitea.localhost';u.port='34443';u.protocol='https:'}location.assign(u.href);}return;}
    submit(name);
   };group.append(button);
   if(a.attempt){const previous=document.createElement('p');previous.className='action-help';previous.append(document.createTextNode('Latest attempt: '+a.attempt.state+(a.attempt.created_at?' · '+new Date(a.attempt.created_at).toLocaleString():'')+'. '));link('/api/delivery/operations/'+encodeURIComponent(a.attempt.id),'View attempt',previous);if(a.attempt.error)previous.append(document.createTextNode(' — '+a.attempt.error));group.append(previous);}
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
  const body={run:data.selected.run,action,context:options.context};
  if(action==='deploy')body.pr=Number($('approved-proposal').value);
  sending=true;render();
  const actionOptions=options.actions.find(a=>a.name===action);
  const encoded=JSON.stringify({...body,...(actionOptions?.retry_of?{after_attempt:actionOptions.retry_of}:{})});if(!keys.has(encoded)){
   // Stable across reloads and network retries for the exact semantic request.
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(encoded));keys.set(encoded,'release-'+[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join(''));
  }
  $('promotion-feedback').textContent='Submitting '+action+' for build '+body.run+'…';
  try{const row=await request('/api/delivery/dashboard/actions',body,keys.get(encoded));const feedback=$('promotion-feedback');feedback.replaceChildren();
   const reused=row.submission_reused===true,finished=['failed','interrupted','complete'].includes(row.state);
   const title=document.createElement('h3');title.textContent=reused?'Existing attempt — '+row.state:row.submission_reused===false?'New attempt — '+row.state:'Attempt — '+row.state;feedback.append(title);
   const text=document.createElement('p');text.textContent=reused?'No new checks were started. This is the previously submitted attempt.':'Your request has been accepted. Follow its progress below.';feedback.append(text);
   if(row.created_at){const when=document.createElement('p');when.textContent='Originally submitted: '+new Date(row.created_at).toLocaleString();feedback.append(when);}
   if(row.error){const error=document.createElement('p');error.textContent='Recorded outcome: '+row.error;feedback.append(error);}
   link('/api/delivery/operations/'+encodeURIComponent(row.id),reused?(finished?'Review previous attempt':'Follow existing attempt'):'Open progress and review links',feedback);
   if(actionOptions&&action!=='deploy'){
    actionOptions.attempt={id:row.id,state:row.state,created_at:row.created_at,error:row.error};
    if(['failed','interrupted'].includes(row.state))Object.assign(actionOptions,{mode:'submit',label:'Run checks again',retry_of:row.id,reason:'Starts a fresh attempt with current settings. The previous result is retained.'});
    else if(row.result?.url)Object.assign(actionOptions,{mode:'review',label:'Review proposal',href:row.result.url,reason:'Review the existing proposal before deployment.'});
    else Object.assign(actionOptions,{mode:'progress',label:'View progress',href:'/api/delivery/operations/'+encodeURIComponent(row.id),reason:'Open the submitted attempt. No new checks will be started.'});
   }
  }catch(e){$('promotion-feedback').textContent=e.message;}
  finally{sending=false;render();}
 }
 $('promotion-stage').onchange=render;$('approved-proposal').onchange=render;$('deploy-proposal').onclick=()=>submit('deploy');
 function invalidate(){options=null;epoch++;$('promotion-panel').hidden=true;$('deploy-proposal').disabled=true;}
 window.releaseControls={load,invalidate};
})();
