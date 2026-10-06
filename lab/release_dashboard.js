'use strict';
const $ = id => document.getElementById(id);
const escapeText = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short = value => value ? value.slice(0,12) : '—';
const date = value => value ? new Date(value).toLocaleString('en-GB') : '—';
const time = value => value == null ? '—' : value < 60 ? `${Math.round(value)}s` : `${Math.floor(value/60)}m ${Math.round(value%60)}s`;
const tone = state => ['verified','prepared','success','merged','previously verified','pass','unchanged','within-budget','approved_exception','active production','candidate ready','built'].includes(state) ? 'good' : ['failed','failure','interrupted','changes requested','fail','blocked','build failed','rollout incomplete'].includes(state) ? 'bad' : ['running','deploying','observed','measured','building','integration','staging'].includes(state) ? 'live' : ['awaiting review','approved','queued','accepted','decision_required'].includes(state) ? 'warn' : '';
const badge = state => `<span class="badge ${tone(state)}">${escapeText((state || 'unknown').replace(/[_-]/g,' '))}</span>`;
function link(url, text) {
  if (!url) return '';
  const parsed = new URL(url, location.origin);
  if (parsed.protocol !== 'https:' && parsed.origin !== location.origin) return escapeText(text);
  return `<a href="${escapeText(parsed.href)}">${escapeText(text)}</a>`;
}
const names = {'promotion':'Promotion checks','prepare-production':'Prepare candidate','release-production':'Production release checks','merge-reviewed':'Deploy approved PR','verify':'Verify deployment','rollback':'Rollback','preview':'Create preview'};
let busy = false, refreshPending = false, lastData = null, cataloguePage = 0;
function cards(data) {
  const query=$('release-search').value.toLowerCase(), state=$('release-status').value;
  const rows=data.releases.filter(r=>(!state||r.state===state)&&(!query||`${r.run} ${r.source_sha} ${r.release_id || ''}`.toLowerCase().includes(query)));
  const pages=Math.max(1,Math.ceil(rows.length/9));cataloguePage=Math.min(cataloguePage,pages-1);
  $('release-cards').innerHTML=rows.slice(cataloguePage*9,cataloguePage*9+9).map(r=>`<a class="release-card" href="/release-dashboard?run=${r.run}"><h2>Build ${r.run}</h2>${badge(r.state)}<dl><div><dt>Source revision</dt><dd><code>${escapeText(short(r.source_sha))}</code></dd></div><div><dt>Current environments</dt><dd>${escapeText(r.environments?.join(' · ') || 'Not currently deployed')}</dd></div><div><dt>Build started</dt><dd>${escapeText(date(r.created_at))}</dd></div></dl><div class="card-footer">View release tree →</div></a>`).join('') || '<p class="empty">No releases match these filters.</p>';
  $('release-pages').innerHTML=`<span>${rows.length} releases · Page ${cataloguePage+1} of ${pages}</span><button id="previous-page" ${cataloguePage===0?'disabled':''}>Previous</button><button id="next-page" ${cataloguePage+1>=pages?'disabled':''}>Next</button>`;
  $('previous-page').onclick=()=>{cataloguePage--;cards(lastData);};$('next-page').onclick=()=>{cataloguePage++;cards(lastData);};
}
for(const id of ['release-search','release-status']) $(id).addEventListener('input',()=>{cataloguePage=0;if(lastData)cards(lastData);});
function tree(data) {
  const source = data.source || {state:'unknown',message:'Merge details are unavailable.'};
  const first = {name:'source',title:'Source merged',state:source.state,message:source.number ? `PR #${source.number} · ${source.title}` : source.message};
  const gate = source.gate;
  $('pipeline').innerHTML = '<svg class="tree-edges" aria-hidden="true"><defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#8ba0bc"/></marker></defs></svg>' + [first,...data.stages].map((s,i)=>{
    let details = '';
    if (i === 0) {
      details = `<div class="tree-detail"><h3>Source gate at merge</h3>${badge(gate?.state || 'unknown')}<p>${escapeText(source.message)}</p>${link(source.gate_url,'Gate report & decision')}${gate?.variants ? gate.variants.map(v=>`<p>${escapeText(v.variant)} · ${badge(v.state)}</p>`).join('') : ''}</div><div class="tree-detail"><h3>Release build</h3>${badge(data.build?.state || 'unknown')}<p>${data.build?.duration_seconds != null ? time(data.build.duration_seconds)+' workflow duration' : 'Recent build status unavailable'}</p>${link(data.build?.url,'Build logs')}</div>`;
    } else {
      const op = s.review_operation || s.operation;
      details = `<div class="tree-detail"><h3>${s.name === 'candidate' ? 'Candidate preparation review' : s.name === 'production' ? 'Release gates & review' : 'Promotion gates & review'}</h3>${op?.pr ? badge(op.pr.state) : badge('not recorded')}${s.checks?.length ? s.checks.map(c=>`<div class="check">${link(c.url,({'relevance':'Relevance','result-regression':'Result changes','performance':'Gatling performance','production-final':'Final production comparison'}[c.name] || c.name))}<br>${badge(c.verdict)}</div>`).join('') : `<p>${s.name === 'candidate' ? 'Reuses the verified staging release.' : 'No saved check verdicts available here.'}</p>`}${op ? `<p>${escapeText(op.intent || s.check_operation?.intent || (s.name==='candidate' ? 'Preparation only' : 'Intent not recorded'))}</p>${eventLinks(op)}` : ''}</div>`;
      if(s.verification) details += `<div class="tree-detail"><h3>Deployment verification</h3>${badge('verified')}<p>${escapeText(date(s.verification.verified_at))}<br>${time(s.verification.seconds)} check · revision <code>${escapeText(short(s.verification.git_revision))}</code></p></div>`;
    }
    return `<div class="tree-column"><article class="stage tree-node ${tone(s.state)}"><div class="number">0${i+1}</div><h3>${escapeText(s.title)}</h3>${badge(s.state)}<p>${escapeText(s.message)}</p>${i === 0 ? link(source.url,'Source PR') : s.environment ? `<p>${escapeText(s.environment.slot || s.name)} · ${s.environment.ready_replicas}/${s.environment.replicas} ready</p>` : ''}</article>${details}</div>`;
  }).join('');
  if(new URL(location.href).searchParams.get('run'))window.releaseControls?.load(data);else window.releaseControls?.invalidate();
  requestAnimationFrame(drawEdges);
}
function drawEdges() {
  const container=$('pipeline'), svg=container.querySelector('svg');
  if(!svg)return;
  const box=container.getBoundingClientRect(), nodes=[...container.querySelectorAll('.tree-node')];
  svg.querySelectorAll('path.edge').forEach(p=>p.remove());
  function edge(d, detail=false) {const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','edge');p.setAttribute('d',d);p.setAttribute('stroke','#8ba0bc');p.setAttribute('stroke-width','1.5');p.setAttribute('fill','none');if(detail)p.setAttribute('stroke-dasharray','4 4');else p.setAttribute('marker-end','url(#arrow)');svg.appendChild(p);}
  nodes.forEach((n,i)=>{
    const r=n.getBoundingClientRect();
    if(i<nodes.length-1){const next=nodes[i+1].getBoundingClientRect(),x=(r.right+next.left)/2-box.left;edge(`M${r.right-box.left},${r.top-box.top+r.height/2} H${x} V${next.top-box.top+next.height/2} H${next.left-box.left-5}`);}
    const details=[...n.parentElement.querySelectorAll('.tree-detail')];let previous=r;
    for(const child of details){const cr=child.getBoundingClientRect(),x=cr.left-box.left+cr.width/2;edge(`M${x},${previous.bottom-box.top} V${cr.top-box.top}`,true);previous=cr;}
  });
}
window.addEventListener('resize',drawEdges);
function eventLinks(row) {
  return `<div class="event-links">${link(row.url,'Progress')}${link(row.report_url,'Report')}${row.pr ? link(row.pr.url,`PR #${row.pr.number}`) : ''}</div>`;
}
function render(data) {
  lastData = data;
  $('release').innerHTML = data.releases.length ? data.releases.map(r => `<option value="${r.run}" ${r.run === data.selected?.run ? 'selected' : ''}>Build ${r.run} · ${escapeText(short(r.source_sha))}</option>`).join('') : '<option>No releases recorded</option>';
  $('release').disabled = !data.releases.length;
  $('dashboard').hidden = false;
  const detail=!!new URL(location.href).searchParams.get('run');
  $('dashboard').hidden=!detail;$('catalogue').hidden=detail;$('promotion-panel').hidden=!detail;$('all-releases').hidden=!detail;
  $('release').hidden=!detail;document.querySelector('label[for="release"]').hidden=!detail;
  $('page-title').textContent=detail&&data.selected ? `Release · Build ${data.selected.run}` : 'Releases';
  $('page-description').textContent=detail ? 'Source merge, recorded gates and deployment progress.' : 'Browse releases and follow their journey to active production.';
  cards(data);
  const active = data.active_production?.definition;
  const production = data.stages.find(s=>s.name==='production');
  const candidate = data.stages.find(s=>s.name==='candidate');
  const attention = data.activity.find(a=>['failed','interrupted','running','queued'].includes(a.state));
  const summary = production?.state === 'verified' ? 'Active in production' : candidate?.state === 'prepared' ? 'Candidate ready' : attention ? names[attention.kind] || attention.kind : 'Release in progress';
  $('overview').innerHTML = `<div><div class="eyebrow">Selected release</div><div class="value">${data.selected ? `Build ${data.selected.run}` : 'No release'}</div><div class="subvalue">${link(data.build?.url,'View source build')}</div></div><div><div class="eyebrow">Source revision</div><div class="value"><code>${escapeText(short(data.selected?.source_sha))}</code></div><div class="subvalue">${link(data.selected?.source_sha ? `https://gitea.localhost:34443/elastic-agent/delivery-source/commit/${data.selected.source_sha}` : null,'Open commit')}</div></div><div><div class="eyebrow">Release status</div><div class="value" style="font-size:17px">${escapeText(summary)}</div><div class="subvalue">${data.activity.length} recorded operations</div></div><div><div class="eyebrow">Active production</div><div class="value"><code>${escapeText(short(active?.source_sha))}</code></div><div class="subvalue">${escapeText(data.active_production?.slot || 'Unknown')} slot · ${data.active_production?.ready ? 'Ready' : 'Unknown or not ready'}</div></div>`;
  tree(data);
  $('environments').innerHTML = data.environments?.length ? data.environments.map(e=>`<tr><td><strong>${escapeText(e.name.replace('production-','Production '))}</strong>${e.slot ? `<br>${e.active ? 'Active route' : 'Inactive slot'}` : ''}</td><td><code>${escapeText(short(e.definition.source_sha))}</code><br>${escapeText(short(e.definition.software_release_id))}</td><td>${badge(e.ready ? 'observed' : 'deploying')}<br>${escapeText(e.ready_replicas)}/${escapeText(e.replicas)} ready · ${escapeText(e.sync || 'Unknown')}<br>${escapeText(e.health || 'Unknown')}</td></tr>`).join('') : '<tr><td colspan="3">Current environments could not be read.</td></tr>';
  const evidence = data.activity.filter(r=>r.pr || r.report_url);
  $('evidence').innerHTML = evidence.length ? `<div class="timeline">${evidence.slice(0,5).map(r=>`<div class="event"><div class="event-head"><strong>${escapeText(names[r.kind] || r.kind)}</strong>${badge(r.pr?.state || r.state)}</div><p>${escapeText(r.target || 'Release')} · ${escapeText(r.intent || 'Intent not recorded')}${r.pr && r.pr.state === 'merged' ? '<br>PR merged; deployment status is shown separately.' : ''}</p>${eventLinks(r)}</div>`).join('')}</div>` : '<p class="empty">No review or check report recorded for this release.</p>';
  $('production').innerHTML = `<div><h3>Currently active · ${escapeText(data.active_production?.slot || 'unknown')}</h3><dl><dt>Source commit</dt><dd><code>${escapeText(active?.source_sha)}</code></dd><dt>Catalogue</dt><dd>${escapeText(active?.dataset_release)}</dd><dt>Index</dt><dd><code>${escapeText(active?.index)}</code></dd></dl></div><div><h3>Selected release</h3><dl><dt>Production status</dt><dd>${badge(production?.state)} / candidate ${badge(candidate?.state)}</dd><dt>Software release</dt><dd><code>${escapeText(data.release?.software_release_id || data.selected?.release_id)}</code></dd><dt>Next step</dt><dd>${production?.state === 'verified' ? 'This release is active.' : candidate?.state === 'prepared' ? 'Review the production checks and route-switch proposal in the existing release workflow.' : 'Continue through the existing promotion workflows. This dashboard follows their progress.'}</dd></dl></div>`;
  const fields = [['Software release','software_release_id'],['Image','image'],['Catalogue','dataset_release'],['Index','index'],['Index recipe','index_recipe_sha256'],['Catalogue manifest','catalogue_manifest_sha256'],['Query manifest','query_manifest_sha256'],['Judgement manifest','judgement_manifest_sha256'],['Variant configuration','variant_config_json']];
  $('inputs').innerHTML = data.release ? `<dl class="detail-grid">${fields.map(([label,key])=>`<div><dt>${label}</dt><dd><code>${escapeText(data.release[key])}</code></dd></div>`).join('')}</dl>` : '<p class="muted">Deployment inputs are available after a proposal or verified deployment is recorded.</p>';
  const sourceGate=data.source?.gate;
  if(sourceGate) $('inputs').innerHTML += `<h3 style="margin-top:25px">Source gate at merge</h3><dl class="detail-grid"><div><dt>Outcome</dt><dd>${badge(sourceGate.state)}</dd></div><div><dt>Policy SHA-256</dt><dd><code>${escapeText(sourceGate.policy_sha256)}</code></dd></div><div><dt>Selection SHA-256</dt><dd><code>${escapeText(sourceGate.selection_sha256)}</code></dd></div><div><dt>Judgement selection</dt><dd>${escapeText(sourceGate.judgement_selection)}</dd></div></dl>${sourceGate.demo_authorisation ? '<p class="notice">This source decision used the authorised lab demo judgement policy.</p>' : ''}`;
  $('inputs').innerHTML += '<p class="notice">Inputs and change intent belong to the recorded proposal. Gate thresholds, selected query sets, load profiles and bounded decisions remain in the linked evidence and reviewed source files.</p><p>'+link(data.selected?.source_sha ? 'https://gitea.localhost:34443/elastic-agent/delivery-source/src/commit/'+data.selected.source_sha+'/gate' : null,'Browse this release’s gate configuration')+'</p>';
  $('activity').innerHTML = data.activity.length ? `<div class="timeline">${data.activity.map(r=>`<div class="event"><div class="event-head"><strong>${escapeText(names[r.kind] || r.kind)}${r.target ? ` · ${escapeText(r.target)}` : ''}</strong>${badge(r.state)}</div><p>${escapeText(r.error || r.progress)}</p><p class="timestamp">${escapeText(date(r.updated_at))} · ${['queued','accepted'].includes(r.state) ? 'Waiting' : r.state === 'running' ? 'Elapsed' : 'Total'} ${time(r.duration_seconds)}</p>${eventLinks(r)}</div>`).join('')}</div>` : '<p class="empty">No operations recorded for this release.</p>';
  $('unbound').innerHTML = data.unbound_operations.length ? `<details><summary>Other production checks · release identity not recorded (${data.unbound_operations.length})</summary><p class="notice">These older attempts cannot be safely attributed to the selected build.</p>${data.unbound_operations.map(r=>`<p>${badge(r.state)} ${escapeText(r.error || r.progress)} · ${link(r.url,'Open operation')}</p>`).join('')}</details>` : '';
  $('updated').textContent = `Updated ${date(data.updated_at)} · Refreshes every 30 seconds. ${data.limits}`;
  $('message').innerHTML = data.notices.map(n=>`<div class="alert">${escapeText(n)}</div>`).join('');
}
async function refresh() {
  if (busy) {refreshPending=true;return;}
  busy = true; $('refresh').disabled = true;
  try {
    const run = new URL(location.href).searchParams.get('run');
    const response = await fetch('/api/delivery/dashboard'+(run ? '?run='+encodeURIComponent(run) : ''), {headers:{Accept:'application/json'}});
    if (response.status === 401) {
      window.releaseControls?.invalidate();lastData=null;$('dashboard').hidden=true;$('catalogue').hidden=true;$('promotion-panel').hidden=true;$('release').disabled=true;
      $('message').innerHTML = '<div class="alert">Sign in to view release progress. <a href="/oauth2/start?rd='+encodeURIComponent(location.pathname+location.search)+'">Sign in to the lab</a></div>';
      return;
    }
    if(response.status===403){lastData=null;$('dashboard').hidden=true;$('catalogue').hidden=true;$('promotion-panel').hidden=true;}
    if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('The dashboard service did not return release data. Retry Refresh.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Release status could not be read.');
    if(new URL(location.href).searchParams.get('run') !== run) {refreshPending=true;return;}
    render(data);
  } catch(error) {
    window.releaseControls?.invalidate();
    $('message').innerHTML = `<div class="alert error">${escapeText(error.message)}${lastData ? ' Showing the last successful snapshot below; it may be out of date.' : ''}</div>`;
  } finally {busy = false; $('refresh').disabled = false;if(refreshPending){refreshPending=false;refresh();}}
}
$('release').addEventListener('change',()=>{const url=new URL(location.href);url.searchParams.set('run',$('release').value);history.replaceState(null,'',url);refresh();});
$('refresh').addEventListener('click',refresh);
const tabs=['overview','inputs','activity'];
for (const name of tabs) {
  $('tab-'+name).tabIndex=name==='overview'?0:-1;
  $('tab-'+name).addEventListener('click',()=>{
    for(const other of tabs) {$('tab-'+other).setAttribute('aria-selected',String(other===name));$('tab-'+other).tabIndex=other===name?0:-1;$('view-'+other).hidden=other!==name;}
  });
  $('tab-'+name).addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const index=event.key==='Home'?0:event.key==='End'?2:(tabs.indexOf(name)+(event.key==='ArrowRight'?1:2))%3;
    $('tab-'+tabs[index]).click();$('tab-'+tabs[index]).focus();
  });
}
refresh(); setInterval(()=>{if(!document.hidden)refresh();},30000);
