/* Read-only browser views of the existing operation and report JSON. */
'use strict';
const $=id=>document.getElementById(id), path=location.pathname;
const operationPage=/^\/api\/delivery\/operations\/[0-9a-f]{32}$/.test(path);
let timer=null, loading=false;
const stateNames={accepted:'Waiting for the source build',queued:'Queued',running:'In progress',complete:'Complete',failed:'Failed',interrupted:'Interrupted',pass:'Passed',approved_exception:'Accepted with a recorded exception',decision_required:'Decision required',blocked:'Blocked',invalid:'Invalid evidence',verified:'Deployment verified'};
const operationTitles={preview:'Prepare a preview',compare:'Search comparison',promotion:'Release promotion',rollback:'Release rollback',verify:'Deployment verification','merge-reviewed':'Deploy the reviewed release','gate-check':'Recheck the merge decision','request-exception':'Request a relevance decision','merge-exception':'Record the relevance decision'};
const names={ndcg_at_10:'nDCG@10',ndcg_at_20:'nDCG@20',precision_at_10:'Precision@10',recall_at_10:'Recall@10',rbo_at_10_p_0_9:'RBO@10',jaccard_at_10:'Jaccard@10'};
const label=value=>names[value]||String(value).replaceAll('_',' ');
const fmt=value=>typeof value==='number'?value.toLocaleString(undefined,{maximumFractionDigits:4}):value==null?'Not available':String(value);
const pct=value=>typeof value==='number'?(100*value).toFixed(1)+'%':'Not available';
function node(tag,text,parent){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(parent)parent.append(n);return n}
function link(id,value){const n=$(id);n.hidden=true;if(!value)return;const u=new URL(value,location.origin);if(!['http:','https:'].includes(u.protocol))return;if(u.hostname==='gitea-internal.lab-ingress.svc.cluster.local'){u.hostname='gitea.localhost';u.port='34443';u.protocol='https:'}n.href=u.href;n.hidden=false}
function section(title,description){const s=node('section',null,$('content'));node('h2',title,s);if(description)node('p',description,s);return s}
function table(parent,headers,rows){const wrap=node('div',null,parent);wrap.className='table-wrap';const t=node('table',null,wrap),head=node('tr',null,node('thead',null,t));for(const text of headers)node('th',text,head).scope='col';const body=node('tbody',null,t);for(const cells of rows){const row=node('tr',null,body);for(const value of cells)node('td',value,row)}}
function identity(values){$('identity').replaceChildren();for(const [key,value] of Object.entries(values)){if(value==null||typeof value==='object')continue;node('dt',label(key),$('identity'));node('dd',String(value),$('identity'))}}
function summary(report,title,required,baseline=report.baseline_variant){
 const s=section(title,(report.query_count==null?'':fmt(report.query_count)+' queries. ')+(required==null?'':required?'Required by the gate.':'Report only.'));
 if(report.relevance_query_count!=null)node('p','Relevance scores cover '+fmt(report.relevance_query_count)+' queries; '+fmt(report.unlabelled_query_count)+' queries have no reference scores.',s);
 const metrics=report.metrics||{}, keys=[...new Set(Object.values(metrics).flatMap(m=>Object.keys(m||{}).filter(k=>typeof m[k]==='number'&&k!=='Judged@10')))];
 const variants=Object.keys(report.variants||metrics||{}), similarity=report.result_similarity||{};
 if(keys.length)table(s,['Variant',...keys.map(label)],variants.map(v=>[v,...keys.map(k=>fmt(metrics[v]?.[k]))]));
 const candidates=Object.keys(similarity).filter(v=>v!==baseline);
 if(candidates.length){
  node('h3','Results compared with '+baseline,s);
  const changes=report.result_changes!=null;
  table(s,['Comparison',...(changes?['Changed queries']:[]),'RBO@10 (p = 0.9)','Jaccard@10'],candidates.map(v=>[v+' vs '+baseline,...(changes?[fmt(report.result_changes[v]?.changed_queries)]:[]),fmt(similarity[v]?.rbo_at_10_p_0_9),fmt(similarity[v]?.jaccard_at_10)]));
 }
 if(!keys.length)node('p','Relevance scores are unavailable for this set. Result overlap can still show whether the searches changed.',s);

 const coverage=report.coverage||report.judgement_coverage;
 if(coverage){const c=section(title+' — judgement coverage');table(c,['Variant','Judged coverage','Labelled results','Returned results'],Object.entries(coverage).map(([v,x])=>[v,pct(x.fraction),fmt(x.judged),fmt(x.returned)]));}
 else if(Object.values(metrics).some(m=>m?.['Judged@10']!=null)){const c=section(title+' — judgement coverage');table(c,['Variant','Judged@10'],Object.entries(metrics).map(([v,m])=>[v,pct(m['Judged@10'])]));}
}
function gate(value){if(!value)return;const s=section('Merge gate',stateNames[value.state]||label(value.state));if(value.variants)table(s,['Variant','Intent','Outcome','Relevance delta','Judged coverage'],value.variants.map(v=>[v.variant,label(v.intent),stateNames[v.state]||label(v.state),fmt(v.delta),pct(v.judged_fraction)]));node('p','This is the recorded merge decision. A passing gate does not deploy the change.',s)}
function operation(row){
 const result=row.result||{},request=row.request||{};
 $('title').textContent=operationTitles[request.kind]||'Lab delivery';
 $('state').textContent=stateNames[row.state]||label(row.state);$('stage').textContent=row.progress||'';
 $('updated').textContent='Last updated: '+new Date(row.updated_at).toLocaleString();
 $('explanation').textContent=row.state==='complete'?'The operation finished. Review its outcome and evidence below.':['failed','interrupted'].includes(row.state)?'The operation did not finish successfully. Review the error before starting another operation.':'This page refreshes every five seconds. You can leave it and return using the same link.';
 if(row.error)node('p','Error: '+row.error,section('What happened'));
 gate(result.gate);
 if(row.state==='complete'&&['promotion','rollback'].includes(request.kind)&&result.validation){$('state').textContent=result.validation.passed?'Ready for review':'Proposal validation failed';}
 if(result.state)node('p',stateNames[result.state]||label(result.state),section('Deployment outcome'));
 if(result.validation)node('p',result.validation.detail||'Review the recorded validation result.',section('Proposal validation'));
 link('report',row.report_url);$('report').textContent=['promotion','rollback'].includes(request.kind)?'Review promotion checks':['verify','merge-reviewed'].includes(request.kind)?'Open deployment verification':'Open comparison report';link('baseline',result.baseline_url);link('candidate',result.candidate_url);link('preview',result.browser_url);link('proposal',result.url);link('decision',row.decision_url);
 identity({operation:row.id,source_commit:request.source_sha||result.source_sha,baseline_commit:request.baseline_sha||result.baseline_source_sha,build_run:request.run,target:request.target,report_sha256:result.report?.sha256,updated_at:row.updated_at});
 return ['accepted','queued','running'].includes(row.state);
}
function timings(value,record){
 const rows=[];
 if(record){
  const end=['accepted','queued','running'].includes(record.state)?Date.now():Date.parse(record.updated_at);
  const seconds=(end-Date.parse(record.created_at))/1000;
  if(Number.isFinite(seconds)&&seconds>=0)rows.push(['Operation elapsed time',fmt(seconds)+' s','Includes waiting, preparation and all checks']);
 }
 const suites=value.query_sets||{'Search capture':value};
 for(const [name,suite] of Object.entries(suites)){
  const execution=suite.execution;
  if(typeof execution?.seconds==='number')rows.push([name==='standard'?'Standard suite capture':name,fmt(execution.seconds)+' s','Capture Job, including scheduling and completion checks; '+fmt(execution.worker_count)+' workers']);
 }
 if(rows.length){const s=section('Timings');table(s,['Activity','Duration','Scope'],rows);}
 const executions=Object.entries(suites).filter(([,suite])=>suite.execution?.pacing);
 if(executions.length){const s=section('Search capture requests','These are functional evaluation requests, not a load test. Pacing wait is summed across workers and can exceed elapsed time.');
 table(s,['Query set','API environment','Attempts','Retries','Transient failures','Terminal failures','Pacing wait (s)'],executions.flatMap(([name,suite])=>Object.entries(suite.execution.pacing).map(([environment,p])=>[name,environment,fmt(p.attempts),fmt(p.retries),fmt(p.transient_failures),fmt(p.terminal_failures),fmt(p.wait_seconds)])));
 }
}
function report(value,operationRecord){
 $('title').textContent=value.state==='verified'?'Deployment verification':value.kind==='paired-api-performance'?'Performance comparison':value.reports?'Delivery checks':'Search comparison report';$('state').textContent=value.valid===false?'Invalid evidence':value.complete===false?'Incomplete evidence':'Report ready';$('stage').textContent='Review search quality, result changes and label coverage separately.';
 $('explanation').textContent='All variants in a relevance comparison use the same frozen judgement set. The report records measurements; the operation page records the gate or deployment decision.';
 const decision=operationRecord?.result?.gate;
 if(decision){
  $('state').textContent='Merge gate: '+(stateNames[decision.state]||label(decision.state));
  $('stage').textContent=decision.state==='pass'?'All selected variants passed. No relevance decision is needed.':decision.state==='approved_exception'?'A bounded regression was accepted and recorded.':decision.state==='decision_required'?'Review the required relevance decision before merging.':'The change cannot merge with this evidence.';
  gate(decision);link('decision',operationRecord.decision_url);
 }else if(operationRecord?.request?.pr){$('state').textContent='Merge gate: not available';$('stage').textContent='No merge decision is recorded for this operation.';}
 else if(value.verdict){$('state').textContent='Check outcome: '+label(value.verdict);}
 else if(value.state==='verified'){$('state').textContent='Deployment verified';$('stage').textContent='Argo CD and the public API verified the declared release.';}
 timings(value,operationRecord);
 if(value.kind==='variant-evaluation-report'||value.kind==='controlled-api-comparison')section('Read the results','RBO describes order similarity; Jaccard describes product-set overlap. A value of 1 means identical at the captured depth. Coverage shows how many results have relevance labels; added labels do not establish better search.');
 if(value.judgement_selection==='demo')node('p','Lab demo: this report includes authorised model labels whose accuracy remains unqualified.',section('Label policy'));
 if(value.query_sets){for(const [name,suite] of Object.entries(value.query_sets))summary(suite,name==='standard'?'Standard suite':name,value.query_set_metadata?.[name]?.required);if(value.combined)summary(value.combined,'Combined view',false,value.baseline_variant);}
 else if(value.kind==='variant-evaluation-report')summary(value,'Search results',null);
 else if(value.kind==='controlled-api-comparison'){summary({...value,baseline_variant:'baseline',variants:{baseline:{},candidate:{}},result_changes:{candidate:{changed_queries:value.changed_query_ids?.length}},result_similarity:{candidate:value.result_similarity||{}}},'Search results',null);}
 else if(value.kind==='paired-api-performance'){
 $('stage').textContent='Gatling performance comparison';$('explanation').textContent='Profile: '+value.profile+'. Outcome: '+label(value.verdict)+'. Review workload validity and each measured phase.';
 const durations=['baseline','candidate'].filter(side=>typeof value[side]?.duration_seconds==='number');
 if(durations.length)table(section('Gatling workload duration','Baseline and candidate run sequentially. These durations include warm-up; measured phase results follow.'),['Release','Workload duration (s)'],durations.map(side=>[side,fmt(value[side].duration_seconds)]));
 for(const [phase,measured] of Object.entries(value.measured_phases||{})){
 const b=measured.budget||{},s=section(label(phase),'Budgets: p95 ≤'+fmt(b.p95_ms)+' ms; p99 ≤'+fmt(b.p99_ms)+' ms; failed requests <'+fmt(b.failed_percent)+'%.');
 table(s,['Release','Requests','Offered requests/s','p95 (ms)','p99 (ms)','Failed requests','Budget'],['baseline','candidate'].map(side=>{const m=measured[side]||{};return[side,fmt(m.request_count),fmt(m.offered_rps),fmt(m.p95_ms),fmt(m.p99_ms),typeof m.failed_percent==='number'?fmt(m.failed_percent)+'%':'Not available',m.within_budget===true?'Met':m.within_budget===false?'Missed':'Not available']}));
 }
 }
 else if(value.state==='verified'){
  const s=section('Verified release'),deployment=value.deployment||{},fields=deployment.fields||{};
  table(s,['Field','Value'],[['Environment',fmt(value.environment)],['Build run',fmt(deployment.build_run)],['Image',fmt(fields.image)],['Index',fmt(fields.index)],['Source commit',fmt(fields.source_sha)],['Verified at',fmt(value.verified_at)],['Verification duration',fmt(value.seconds)+' s'],...(value.merge_to_verified_seconds==null?[]:[['Merge to verified',fmt(value.merge_to_verified_seconds)+' s']]),['Products checked',fmt(value.sample_ids?.length)]]);
  $('explanation').textContent='This records deployment verification, not a new relevance or load test.';
 }
 else if(value.reports){const s=section('Delivery checks','Open each retained check. The operation records the promotion decision.');for(const name of ['result-regression','relevance','performance'])if(value.reports[name]){const p=node('p',null,s),a=node('a','Open '+label(name)+' report',p);a.href=path+'/'+name;}}
 else{const s=section('Delivery evidence','This record combines the retained checks for a delivery operation. Open its operation page to review the decision, or view JSON for the complete evidence.');const values=Object.entries(value).filter(([k,v])=>v!=null&&typeof v!=='object');if(values.length)table(s,['Field','Value'],values.map(([k,v])=>[label(k),fmt(v)]));}
 if(path.startsWith('/api/delivery/operations/'))link('proposal',path.split('/report')[0]);$('proposal').textContent='Open operation progress';
 identity({report_kind:value.kind,source_commit:value.source_context?.source_sha,baseline:value.baseline_variant,default:value.default_variant,judgement_sha256:value.judgement_sha256,query_suite_sha256:value.query_suite_sha256,workload_sha256:value.workload_sha256,observation_sha256:value.observation_sha256,evaluated_at:value.evaluated_at});
}
async function load(){if(loading)return;loading=true;clearTimeout(timer);try{
 const response=await fetch(path,{headers:{Accept:'application/json'}}),value=await response.json();
 if(!response.ok){const error=new Error(value.error||'Unable to load this record.');error.status=response.status;throw error}
 $('content').replaceChildren();$('signin').hidden=true;for(const id of ['report','baseline','candidate','preview','proposal','decision'])$(id).hidden=true;
 let record=null;
 if(!operationPage&&path.startsWith('/api/delivery/operations/')){
  const r=await fetch(path.split('/report')[0],{headers:{Accept:'application/json'}});
  if(!r.ok)throw new Error('Unable to load the recorded gate outcome.');
  record=await r.json();
 }
 const active=operationPage?operation(value):(report(value,record),false);if(active)timer=setTimeout(load,5000);
 }catch(error){$('state').textContent='Unable to load';$('stage').textContent=error.message;$('explanation').textContent='Refresh to try again. This does not restart the operation.';if(error.status===401)link('signin','/oauth2/start?rd='+encodeURIComponent(location.pathname+location.search));}finally{loading=false}}
$('json').href=path+'?format=json';$('refresh').addEventListener('click',load);load();
