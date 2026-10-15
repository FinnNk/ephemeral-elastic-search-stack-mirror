/* Read-only browser views of the existing operation and report JSON. */
'use strict';
const $=id=>document.getElementById(id), path=location.pathname;
const operationPage=/^\/api\/delivery\/operations\/[0-9a-f]{32}$/.test(path);
let timer=null, loading=false, logsPaused=false, logsLoading=false, logCursor=0, latestGatling=null, latestEvaluation=null, operationActive=false, operationUpdatedMs=0;
$("pause-logs").onclick=()=>{logsPaused=!logsPaused;$("pause-logs").textContent=logsPaused?"Resume":"Pause";if(!logsPaused&&operationPage)updateLogs({});};
const stateNames={accepted:'Waiting for the source build',queued:'Queued',running:'In progress',complete:'Complete',failed:'Failed',interrupted:'Interrupted',pass:'Passed',approved_exception:'Accepted with a recorded exception',decision_required:'Decision required',blocked:'Blocked',invalid:'Invalid evidence',verified:'Deployment verified'};
const operationTitles={'prepare-production':'Prepare production candidate','release-production':'Production release checks',preview:'Prepare a preview',compare:'Search comparison',promotion:'Release promotion',rollback:'Release rollback',verify:'Deployment verification','merge-reviewed':'Deploy the reviewed release','gate-check':'Recheck the merge decision','request-exception':'Request a relevance decision','merge-exception':'Record the relevance decision'};
const names={ndcg_at_10:'nDCG@10',ndcg_at_20:'nDCG@20',precision_at_10:'Precision@10',recall_at_10:'Recall@10',rbo_at_10_p_0_9:'RBO@10',jaccard_at_10:'Jaccard@10'};
const intentNames={'ranking-change':'Intentional ranking change','preserve-results':'Preserve current results'};
const label=value=>names[value]||String(value).replaceAll('_',' ');
const fmt=value=>typeof value==='number'?value.toLocaleString(undefined,{maximumFractionDigits:4}):value==null?'Not available':String(value);
const probability=value=>typeof value==='number'&&value>0&&value<.0001?'<0.0001':fmt(value);
const pct=value=>typeof value==='number'?(100*value).toFixed(1)+'%':'Not available';
const releaseVersion=(version,sha)=>(version||'Version not recorded')+' · '+(sha?String(sha).slice(0,12):'Commit not recorded');
function node(tag,text,parent){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(parent)parent.append(n);return n}
function link(id,value){const n=$(id);n.hidden=true;if(!value)return;const u=new URL(value,location.origin);if(!['http:','https:'].includes(u.protocol))return;if(u.hostname==='gitea-internal.lab-ingress.svc.cluster.local'){u.hostname='gitea.localhost';u.port='34443';u.protocol='https:'}n.href=u.href;n.hidden=false}
function section(title,description){const s=node('section',null,$('content'));node('h2',title,s);if(description)node('p',description,s);return s}
function table(parent,headers,rows){const wrap=node('div',null,parent);wrap.className='table-wrap';const t=node('table',null,wrap),head=node('tr',null,node('thead',null,t));for(const text of headers)node('th',text,head).scope='col';const body=node('tbody',null,t);for(const cells of rows){const row=node('tr',null,body);for(const value of cells){const cell=node('td',null,row);if(value instanceof Node)cell.append(value);else cell.textContent=value==null?'':String(value)}}}
function identity(values){$('identity').replaceChildren();for(const [key,value] of Object.entries(values)){if(value==null||typeof value==='object')continue;node('dt',label(key),$('identity'));node('dd',String(value),$('identity'))}}
function summary(report,title,required,baseline=report.baseline_variant){
 const s=section(title,(report.query_count==null?'':fmt(report.query_count)+' queries. ')+(required==null?'':required?'Required by the gate.':'Report only.'));
 if(report.relevance_query_count!=null)node('p','Relevance scores cover '+fmt(report.relevance_query_count)+' queries; '+fmt(report.unlabelled_query_count)+' queries are excluded from quality scores.',s);
 const metrics=report.metrics||{}, keys=[...new Set(Object.values(metrics).flatMap(m=>Object.keys(m||{}).filter(k=>typeof m[k]==='number'&&k!=='Judged@10')))];
 const variants=Object.keys(report.variants||metrics||{}), similarity=report.result_similarity||{};
 if(report.metrics===null&&!report.relevance_unavailable_reason)node('p','Relevance scores are unavailable: this frozen report has no usable judgement snapshot.',s);
 if(!keys.length)keys.push('nDCG@5','nDCG@10');
 table(s,['Variant',...keys.map(label)],variants.map(v=>[v,...keys.map(k=>metrics[v]?.[k]==null?'Not calculable':fmt(metrics[v][k]))]));
 const deltas=report.delta_from_baseline||{};
 if(Object.keys(deltas).length)table(s,['Variant vs baseline','nDCG@5 change','nDCG@10 change'],Object.entries(deltas).map(([v,m])=>[v+' vs '+baseline,m['nDCG@5']==null?'Not calculable':fmt(m['nDCG@5']),m['nDCG@10']==null?'Not calculable':fmt(m['nDCG@10'])]));
 if(report.ndcg_significance){const stats=report.ndcg_significance;const t=section(title+' — nDCG significance','Informational only; gates are unchanged. Tests use paired queries with positive reference gain. Repeated and case-varied requests are grouped together.');
 const tests=Object.entries(stats.comparisons).flatMap(([variant,metrics])=>Object.entries(metrics).map(([metric,x])=>({comparison:variant+' vs '+baseline,metric,...x})));
 table(t,['Comparison','Metric','Mean change','95% interval','Raw p','Adjusted p','Significant at 5%?'],tests.map(x=>[x.comparison,x.metric,fmt(x.mean_difference),x.confidence_interval_95?x.confidence_interval_95.map(fmt).join(' to '):'Not available',probability(x.p_value),probability(x.adjusted_p_value),x.significant==null?'Insufficient data':x.significant?'Yes':'No']));
 table(t,['Comparison','Metric','Queries scored','Request groups','Excluded queries'],tests.map(x=>[x.comparison,x.metric,fmt(x.paired_queries),fmt(x.request_groups),fmt(x.excluded_queries)]));
 node('p','Two-sided paired permutation test; 95% request-group bootstrap interval. P-values use Holm adjustment across variants and nDCG cut-offs within this view. The interval is not adjusted for multiple comparisons. A non-significant result does not establish equivalence. Tested means can differ from quality averages when queries are excluded.',t);
 for(const [variant,metrics] of Object.entries(stats.comparisons))for(const [metric,x] of Object.entries(metrics))if(x.unavailable_reason)node('p',variant+' — '+metric+': '+x.unavailable_reason,t);
 }
 if(report.relevance_unavailable_reason)node('p','Not calculable: '+report.relevance_unavailable_reason,s);
 if(report.judgement_resolution){const r=report.judgement_resolution,e=r.execution||{},c=r.counts.pool;const j=section(title+' — judgement resolution');table(j,['Measure','Count'],[['Pairs in the result union',fmt(c.required)],['Supplied labels reused',fmt(c.stored)],['Stored API labels reused',fmt(e.stored_pairs)],['Cached outcomes reused',fmt(e.cache_hits)],['Pairs sent to the model',fmt(e.inferred_pairs)],['Resolved labels',fmt(c.newly_labelled)],['Abstentions or ineligible predictions',fmt(c.abstained)],['Errors',fmt(c.failed)],['API requests without a response',fmt(e.response_errors||0)]]);node('p','One frozen judgement snapshot scores every variant.',j);}
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
 operationActive=['accepted','queued','running'].includes(row.state);operationUpdatedMs=Date.parse(row.updated_at)||0;
 $('title').textContent=operationTitles[request.kind]||'Lab delivery';
 $('state').textContent=stateNames[row.state]||label(row.state);$('stage').textContent=row.progress||'';
 if(latestGatling)showGatling(latestGatling);
 if(latestEvaluation)showEvaluation(latestEvaluation);
 updateLogs(row);
 $('queue-panel').hidden=!row.queue;
 if(row.queue){$('queue-detail').replaceChildren();node('span','Position '+row.queue.position+'. ', $('queue-detail'));if(row.queue.blocker?.id){const a=node('a','Waiting for: '+row.queue.blocker.progress,$('queue-detail'));a.href='/api/delivery/operations/'+row.queue.blocker.id;}else node('span','Waiting for the coordinator to take this request.', $('queue-detail'));}
 $('updated').textContent='Last updated: '+new Date(row.updated_at).toLocaleString();
 $('explanation').textContent=row.state==='complete'?'The operation finished. Review its outcome and evidence below.':['failed','interrupted'].includes(row.state)?'The operation did not finish successfully. Review the error before starting another operation.':'This page refreshes every five seconds. You can leave it and return using the same link.';
 if(row.error)node('p','Error: '+row.error,section('What happened'));
 gate(result.gate);
 if(row.state==='complete'&&['promotion','rollback','prepare-production','release-production'].includes(request.kind)&&result.validation){$('state').textContent=result.validation.passed?'Ready for review':'Proposal validation failed';}
 if(result.state)node('p',stateNames[result.state]||label(result.state),section('Deployment outcome'));
 if(result.validation)node('p',result.validation.detail||'Review the recorded validation result.',section('Proposal validation'));
 link('report',row.report_url);$('report').textContent=['promotion','rollback','prepare-production','release-production'].includes(request.kind)?'Review promotion checks':['verify','merge-reviewed'].includes(request.kind)?'Open deployment verification':'Open comparison report';link('baseline',result.baseline_url);link('candidate',result.candidate_url);link('preview',result.browser_url);link('proposal',result.url);link('decision',row.decision_url);
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
 if(executions.length){const s=section('Search capture requests','These are functional evaluation requests, not a load test. Successes count requests that returned valid JSON, including those recovered by retrying. Pacing wait is summed across workers and can exceed elapsed time.');
 table(s,['Query set','API environment','Attempts','Successes','Retries','Transient failures','Terminal failures','Pacing wait (s)'],executions.flatMap(([name,suite])=>Object.entries(suite.execution.pacing).map(([environment,p])=>[name,environment,fmt(p.attempts),fmt(p.successes),fmt(p.retries),fmt(p.transient_failures),fmt(p.terminal_failures),fmt(p.wait_seconds)])));
 }
}
function buildLink(run){const a=document.createElement('a');a.textContent=run?'Build '+run:'Build not recorded';if(run)a.href='https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/'+encodeURIComponent(run);return a;}
function settingsText(settings){const boosts=settings?.field_boosts;return boosts?'Search field weights: '+Object.entries(boosts).map(([k,v])=>k+' '+v).join(', '):'Configuration details not recorded';}
async function promotionReview(value,row){
 const proposal=row?.result?.proposal||{},deployment=proposal.deployment||{},fields=deployment.fields||{},target=proposal.target||row?.request?.target||'target';
 const overview=section('Promotion for review','Compare the currently deployed '+target+' baseline with this candidate. Approval records your decision; deployment is a separate action.');
 overview.classList.add('promotion-review');
 if(row?.result?.url){const u=new URL(row.result.url,location.origin);if(['http:','https:'].includes(u.protocol)){if(u.hostname==='gitea-internal.lab-ingress.svc.cluster.local'){u.hostname='gitea.localhost';u.port='34443';u.protocol='https:'}const a=node('a','Review proposal in Gitea',overview);a.href=u.href;}}
 const records=await Promise.all((value.checks||[]).map(async check=>{
  const reports={};if(check.evidence)await Promise.all(['relevance','result-regression','performance',...(check.query_sets_report?['query-sets']:[])].map(async mode=>{
   try{const r=await fetch(path+'/variant/'+encodeURIComponent(check.variant)+'/'+mode,{headers:{Accept:'application/json'}});if(!r.ok)throw new Error();reports[mode]=await r.json();}catch{reports[mode]=null;}
  }));return{check,reports};
 }));
 const frozenBaseline=records.find(r=>r.reports.relevance)?.reports.relevance.baseline||{};
 table(overview,['Role','Release','Version','Behaviour'],[
  ['Current '+target+' baseline',buildLink(value.baseline_build_run),releaseVersion(frozenBaseline.software_version||frozenBaseline.fields?.software_version,frozenBaseline.source_sha||frozenBaseline.fields?.source_sha),value.baseline_variant||'Not recorded'],
  ['Candidate',buildLink(value.candidate_build_run),releaseVersion(fields.software_version,fields.source_sha||value.source_sha),(value.checks||[]).map(c=>c.variant).join(', ')]]);
 const first=records.find(r=>r.reports.relevance)?.reports.relevance;
 node('p','Catalogue: '+(fields.dataset_release||first?.candidate?.dataset_release||'Not recorded')+'. Checked '+new Date(value.completed_at).toLocaleString()+'.',overview);
 const config=section('Compared search configurations','Names identify the behaviour being reviewed; exact hashes remain under Evidence details.');
 node('p','Baseline '+(value.baseline_variant||'default')+' — '+settingsText(value.baseline_pin?.settings),config);
 let candidateSettings={};try{candidateSettings=JSON.parse(fields.variant_config_json||'{}')}catch{}
 for(const {check,reports} of records){
  node('p','Candidate '+check.variant+' — '+(intentNames[check.intent]||label(check.intent))+' — '+settingsText(candidateSettings.variants?.[check.variant]),config);
  const s=section(check.variant+' — review summary',(intentNames[check.intent]||label(check.intent))+'. Gate: '+(stateNames[check.state]||label(check.state))+'.');
  s.classList.add('promotion-review');
  if(check.error)node('p',check.error,s);
  const relevance=reports.relevance,results=reports['result-regression'],performance=reports.performance;
  node('h3','Standard query sets — required',s);
  if(relevance){const b=relevance.metrics?.baseline||{},c=relevance.metrics?.candidate||{};
   const coverage=relevance.judgement_coverage||{};
   table(s,['Metric','Baseline','Candidate','Change'],[
    ['nDCG@10 (search quality)',fmt(b['nDCG@10']),fmt(c['nDCG@10']),typeof b['nDCG@10']==='number'&&typeof c['nDCG@10']==='number'?fmt(c['nDCG@10']-b['nDCG@10']):'Not calculable'],
    ['Labelled results (judgement coverage)',pct(coverage.baseline?.fraction),pct(coverage.candidate?.fraction),typeof coverage.baseline?.fraction==='number'&&typeof coverage.candidate?.fraction==='number'?fmt(100*(coverage.candidate.fraction-coverage.baseline.fraction))+' percentage points':'Not calculable']]);
   node('p',fmt(relevance.completed_query_count)+' of '+fmt(relevance.query_count)+' queries completed.',s);
  }else node('p','Relevance summary unavailable. Open the detailed report before approving.',s);
  if(results){table(s,['Result changes','Value'],[['Changed queries',fmt(results.changed_query_ids?.length)],['RBO@10 (p = 0.9)',fmt(results.result_similarity?.rbo_at_10_p_0_9)],['Jaccard@10',fmt(results.result_similarity?.jaccard_at_10)]]);}
  else node('p','Result-change summary unavailable. Open the detailed report before approving.',s);
  if(performance){const profile={probe:'Short regression probe',smoke:'Smoke test','production-load':'Production load test'}[performance.profile]||performance.profile;node('p','Performance profile: '+profile+'; '+(performance.verdict==='within-budget'?'Within budget':label(performance.verdict))+'. '+(performance.profile==='probe'?'This short regression probe is not a production load test.':''),s);
   table(s,['Phase','Baseline p95 (ms)','Candidate p95 (ms)','p95 budget (ms)','Baseline failures','Candidate failures'],Object.entries(performance.measured_phases||{}).map(([phase,x])=>[label(phase),fmt(x.baseline?.p95_ms),fmt(x.candidate?.p95_ms),fmt(x.budget?.p95_ms),fmt(x.baseline?.failed_percent)+'%',fmt(x.candidate?.failed_percent)+'%']));
  }else node('p','Performance summary unavailable. Open the detailed report before approving.',s);
  if(check.query_sets_report){
   if(reports['query-sets'])suiteViews(reports['query-sets'],check.variant+' — ');
   else node('p','Additional query-set report unavailable. Open its detailed report before approving.',s);
  }
 }
 const evidence=$('identity');for(const [k,v] of Object.entries({baseline_deployment:value.baseline,candidate_deployment:value.candidate,baseline_configuration:value.baseline_pin?.configuration_sha256,candidate_configuration:value.candidate_configuration_sha256,source_commit:value.source_sha})){node('dt',label(k),evidence);node('dd',fmt(v),evidence);}
}
function suiteViews(value,prefix=''){
 if(value.gate_outcomes){
  table(section(prefix+'Query-set outcomes','Every required set must pass independently. Report-only sets and combined averages do not decide promotion.'),['Group','Query set','Requirement','Outcome','Reason'],Object.entries(value.gate_outcomes).map(([name,g])=>[(value.query_set_metadata?.[name]?.group==='mandatory'||name==='standard')?'Standard query sets':'Additional query sets',name,g.required?'Required':'Report only',g.state==='report_only'?(g.available?'Informational':'Informational — unavailable'):(stateNames[g.state]||label(g.state)),g.reason||'']));
 }
 for(const group of ['mandatory','change-specific']){
  const entries=Object.entries(value.query_sets).filter(([name])=>(value.query_set_metadata?.[name]?.group||(name==='standard'?'mandatory':'change-specific'))===group);
  if(entries.length)section(prefix+(group==='mandatory'?'Standard query sets':'Additional query sets'),group==='mandatory'?'Every suite in this group is required.':'Each set states whether it is required or report only.');
  for(const [name,suite] of entries)summary(suite,prefix+(name==='standard'?'Standard suite':name),value.query_set_metadata?.[name]?.required);
 }
 if(value.combined){
  if(value.combined.available===false)node('p',value.combined.unavailable_reason,section(prefix+'Combined view — informational'));
  else {
   summary(value.combined,prefix+'Combined view — informational',false,value.baseline_variant||'baseline');
   if(value.combined.weighting)node('p',value.combined.weighting+'. Repeated requests: '+fmt(value.combined.repeated_request_count)+'.',section(prefix+'Combined weighting'));
  }
 }
}
async function report(value,operationRecord){
 $('title').textContent=value.state==='verified'?'Deployment verification':value.kind==='paired-api-performance'?'Performance comparison':value.kind==='delivery-variant-evidence'?'Per-variant delivery checks':value.reports?'Delivery checks':'Search comparison report';$('state').textContent=value.state==='pass'?'All variants passed':value.state==='failed'?'Variant gate failed':value.valid===false?'Invalid evidence':value.complete===false?'Incomplete evidence':'Report ready';$('stage').textContent='Review search quality, result changes and label coverage separately.';
 $('explanation').textContent='All variants in a relevance comparison use the same frozen judgement set. The report records measurements; the operation page records the gate or deployment decision.';
 const decision=operationRecord?.result?.gate;
 if(decision){
  $('state').textContent='Merge gate: '+(stateNames[decision.state]||label(decision.state));
  $('stage').textContent=decision.state==='pass'?'All selected variants passed. No relevance decision is needed.':decision.state==='approved_exception'?'A bounded regression was accepted and recorded.':decision.state==='decision_required'?'Review the required relevance decision before merging.':'The change cannot merge with this evidence.';
  gate(decision);link('decision',operationRecord.decision_url);
 }else if(operationRecord?.request?.pr){$('state').textContent='Merge gate: not available';$('stage').textContent='No merge decision is recorded for this operation.';}
 else if(value.verdict){$('state').textContent='Check outcome: '+label(value.verdict);}
 else if(value.state==='verified'){$('state').textContent='Deployment verified';$('stage').textContent='Argo CD and the public API verified the declared release.';}
 if(value.kind==='delivery-variant-evidence'){identity({report_kind:value.kind,evidence_sha256:operationRecord?.result?.report?.sha256,evaluated_at:value.completed_at});await promotionReview(value,operationRecord);}
 timings(value,operationRecord);
 if(value.production_slots_sha256){node('p',value.recent_query_source,section('Final production release',value.release_review));}

 if(value.kind==='variant-evaluation-report'||value.kind==='controlled-api-comparison')section('Read the results','RBO describes order similarity; Jaccard describes product-set overlap. A value of 1 means identical at the captured depth. Coverage shows how many results have relevance labels; added labels do not establish better search.');
 if(value.query_sets)suiteViews(value);
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
  table(s,['Field','Value'],[['Environment',fmt(value.environment)],['Version',releaseVersion(fields.software_version,fields.source_sha)],['Build run',fmt(deployment.build_run)],['Image',fmt(fields.image)],['Index',fmt(fields.index)],['Source commit',fmt(fields.source_sha)],['Verified at',fmt(value.verified_at)],['Verification duration',fmt(value.seconds)+' s'],...(value.merge_to_verified_seconds==null?[]:[['Merge to verified',fmt(value.merge_to_verified_seconds)+' s']]),['Products checked',fmt(value.sample_ids?.length)]]);
  $('explanation').textContent='This records deployment verification, not a new relevance or load test.';
 }
 else if(value.kind==='delivery-variant-evidence'){
  $('stage').textContent='One active-target baseline was used for every selected candidate variant.';
  const c=section('Selected variant checks','Each variant uses its intent from the exact merged source commit. Every check is compared with the same baseline build and configuration.');
  table(c,['Variant','Intent','Outcome','Reports'],(value.checks||[]).map(row=>{
   const cell=document.createElement('span');
   if(row.evidence)for(const [mode,labelText] of [['result-regression','Results'],['relevance','Relevance'],['performance','Performance'],...(row.query_sets_report?[['query-sets','Query sets']]:[])]){
    const a=document.createElement('a');a.href=path+'/variant/'+encodeURIComponent(row.variant)+'/'+mode;a.textContent=labelText;cell.append(a,document.createTextNode(' '));
   }else cell.textContent='No complete report';
   return[row.variant,intentNames[row.intent]||label(row.intent),stateNames[row.state]||label(row.state),cell];
  }));
 }
 else if(value.reports){
 if(value.production_final){const s=section('Final production comparison','Active production and the prepared candidate use the same frozen catalogue. Review relevance and coverage before approving the route switch.');const a=node('a','Open final production comparison',s);a.href=path+'/production-final';}
const s=section('Delivery checks','Open each retained check. The operation records the promotion decision.');for(const name of ['result-regression','relevance','performance'])if(value.reports[name]){const p=node('p',null,s),a=node('a','Open '+label(name)+' report',p);a.href=path+'/'+name;}}
 else{const s=section('Delivery evidence','This record combines the retained checks for a delivery operation. Open its operation page to review the decision, or view JSON for the complete evidence.');const values=Object.entries(value).filter(([k,v])=>v!=null&&typeof v!=='object');if(values.length)table(s,['Field','Value'],values.map(([k,v])=>[label(k),fmt(v)]));}
 if(path.startsWith('/api/delivery/operations/'))link('proposal',path.split('/report')[0]);$('proposal').textContent='Open operation progress';
 if(value.kind!=='delivery-variant-evidence')identity({report_kind:value.kind,source_commit:value.source_context?.source_sha,baseline:value.baseline_variant,default:value.default_variant,judgement_sha256:value.judgement_sha256,query_suite_sha256:value.query_suite_sha256,workload_sha256:value.workload_sha256,observation_sha256:value.observation_sha256,evaluated_at:value.evaluated_at});
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
 const active=operationPage?operation(value):(await report(value,record),false);if(active)timer=setTimeout(load,5000);
 }catch(error){$('state').textContent='Unable to load';$('stage').textContent=error.message;$('explanation').textContent='Refresh to try again. This does not restart the operation.';if(error.status===401)link('signin','/oauth2/start?rd='+encodeURIComponent(location.pathname+location.search));}finally{loading=false}}
$('json').href=path+'?format=json';$('refresh').addEventListener('click',load);load();

async function updateLogs(row){
 $('live-logs').hidden=false;
 if(logsPaused||logsLoading)return;
 logsLoading=true;
 try{const response=await fetch(path+'/logs?after='+logCursor,{headers:{Accept:'application/json'}});
  if(!response.ok)throw new Error('Logs unavailable');
  const value=await response.json();
  for(const line of value.logs){const pre=$('log-lines');let message=line.message;try{const event=JSON.parse(message);if(event.event==='gatling.live'){latestGatling=event;showGatling(event);const m=event.metrics;message=event.side+' — '+(event.phase_label||m?.phase||'Starting driver')+' · '+fmt(event.elapsed_seconds)+' / '+fmt(event.planned_seconds)+' s'+(m?' · '+fmt(m.completed)+' completed, '+fmt(m.failed)+' failed':'');}else if(event.event==='evaluation.live'){showEvaluation(event);const m=event.metrics;message=(event.suite?event.suite+' — ':'')+event.phase+(m?' · '+fmt(m.completed)+' / '+fmt(m.total)+' '+(event.unit||'queries')+(m.failed!=null?' · '+fmt(m.failed)+' failed':''):'');}else message=event.operation+' — '+event.state+' ('+fmt(event.duration_ms)+' ms)';}catch(e){}pre.textContent+=new Date(line.at).toLocaleTimeString()+' '+message+'\n';logCursor=line.sequence;}
  const lines=$('log-lines').textContent.split('\n');if(lines.length>501)$('log-lines').textContent=lines.slice(-501).join('\n');
  $('log-lines').scrollTop=$('log-lines').scrollHeight;
  $('log-status').textContent=value.logs.length?'':'No new log entries.';
  if(value.logs.length===100&&!logsPaused)setTimeout(()=>updateLogs(row),0);
 }catch(e){$('log-status').textContent='Logs are temporarily unavailable. Status and reports remain available.';}finally{logsLoading=false;}
}

function showGatling(event){
 let panel=$('gatling-live');if(!panel){panel=node('section',null,$('content'));panel.id='gatling-live';}
 panel.replaceChildren();node('h2','Live Gatling check',panel);
 node('p','Provisional driver counters; the retained Gatling report decides the gate. Job elapsed time includes driver startup.',panel);
 const m=event.metrics;
 table(panel,['Side','Phase','Job elapsed / planned traffic','Completed in phase','Failures in phase','Completion rate','Mean latency'],[[event.side,event.phase_label||m?.phase||'Starting driver',fmt(event.elapsed_seconds)+' / '+fmt(event.planned_seconds)+' s',fmt(m?.completed),fmt(m?.failed),fmt(m?.completed_rps)+' requests/s',fmt(m?.mean_latency_ms)+' ms']]);
 const a=node('a','Open observability dashboard',panel);const dashboard=new URL('https://signoz.localhost:34443/dashboard/01a0e51c-1043-79cb-94a8-9511cb0c665b');
 dashboard.searchParams.set('variables',JSON.stringify({environment:[event.environment]}));
 dashboard.searchParams.set('startTime',String(event.started_ms));dashboard.searchParams.set('endTime',String(event.observed_ms));a.href=dashboard.href;
 node('p','Environment: '+event.environment+'. The dashboard opens this environment and the sampled run interval. Operation panels remain lab-wide. Missing telemetry is not a healthy result.',panel);
}


function showEvaluation(event){
 event.observed_ms=event.observed_ms||Date.now();
 latestEvaluation=event;
 if(operationActive&&event.observed_ms>=operationUpdatedMs&&event.observed_ms>=(latestGatling?.observed_ms||0))$('stage').textContent=(event.suite?event.suite+' — ':'')+event.phase;
 let panel=$('evaluation-live');if(!panel){panel=node('section',null,$('content'));panel.id='evaluation-live';panel.setAttribute('aria-live','polite');}
 panel.replaceChildren();node('h2','Evaluation progress',panel);
 node('p',(event.suite?event.suite+' — ':'')+event.phase,panel);
 const m=event.metrics;
 if(event.metrics_stale)node('p','Last known counters; waiting for a new worker sample.',panel);
 if(m){
  const progress=node('progress',null,panel);progress.max=m.total||1;progress.value=m.completed||0;
  progress.setAttribute('aria-label','Completed '+(event.unit||'queries'));
  table(panel,['Measure','Value'],[['Completed '+(event.unit||'queries'),fmt(m.completed)+' / '+fmt(m.total)],
   ...Object.entries(m).filter(([key])=>!['completed','total'].includes(key)).map(([key,value])=>[label(key),fmt(value)])]);
 }else node('p','Waiting for the next worker update. No completion count is available for this phase.',panel);
 node('p','Provisional progress; retained reports determine the gate.'+(event.unit==='queries'?' Each completed query has finished capture across its selected APIs or returned an error.':''),panel);
 node('p','Updated '+new Date(event.observed_ms).toLocaleTimeString()+(event.elapsed_seconds!=null?' · '+fmt(event.elapsed_seconds)+' s elapsed for this task':''),panel);
}
