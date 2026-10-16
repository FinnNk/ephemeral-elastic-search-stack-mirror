/* A durable build request survives refreshes and ambiguous HTTP responses. */
(()=>{
 'use strict';
 const form=document.querySelector('#build-preview');if(!form)return;
 const feedback=document.querySelector('#preview-build-feedback'),button=form.querySelector('button');
 const terminal=new Set(['complete','failed','interrupted']);
 let identity=null,record=null,timer=null,storageKey=null,busy=false;
 const text=(tag,value)=>{const element=document.createElement(tag);element.textContent=value;return element;};
 const save=()=>{try{sessionStorage.setItem(storageKey,JSON.stringify(record));}catch{}};
 const controls=()=>{for(const element of form.elements)element.disabled=busy||!identity?.is_admin||identity?.is_reader||identity?.is_delivery_service||!form.elements.dataset.options.length;};
 const link=(label,url)=>{const element=text('a',label);element.href=url;if(feedback.querySelector('a'))feedback.append(text('span',' \u00b7 '));feedback.append(element);};
 async function call(path,options={}){
  const response=await fetch(path,{...options,headers:{Accept:'application/json','X-Lab-Intent':'1',...options.headers}});
  if(!(response.headers.get('Content-Type')||'').includes('application/json'))throw new Error('The service is unavailable or your sign-in expired. Reload and sign in again; the saved request can be checked safely.');
  const value=await response.json();if(!response.ok)throw new Error(value.error||'The request could not be checked.');return value;
 }
 function show(row){
  record.operation=row.id;record.state=row.state;save();
  feedback.replaceChildren(text('p',row.progress||'Preview build requested.'));
  link(terminal.has(row.state)?'View result':'Open build and preview progress',row.url);
  if(row.result?.build_url)link(row.result.build_run?'Open build '+row.result.build_run:'Open Actions',row.result.build_url);
  if(row.result?.browser_url)link('Open preview storefront',row.result.browser_url);
  const sha=row.result?.source_sha||row.request?._preview_source_sha;
  if(sha)feedback.append(text('p','Pinned commit: '+sha));
  if(row.error)feedback.append(text('p',row.error));
  busy=!terminal.has(row.state);
  button.textContent=busy?'Build and preview in progress':row.state==='complete'?'Build another preview':'Retry build and create preview';
  controls();
  if(busy)timer=setTimeout(check,5000);
 }
 async function check(){
  clearTimeout(timer);
  try{show(await call('/api/delivery/operations/'+record.operation));}
  catch(error){feedback.replaceChildren(text('p',error.message));if(record?.operation)link('Open saved operation','/api/delivery/operations/'+record.operation);busy=false;button.textContent='Check existing build request';controls();}
 }
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;clearTimeout(timer);
  if(record?.operation&&!terminal.has(record.state)){busy=true;controls();await check();return;}
  const payload={kind:'build-preview',source_ref:form.elements.source_ref.value.trim(),dataset:form.elements.dataset.value};
  if(form.elements.recipe.value.trim())payload.recipe=form.elements.recipe.value.trim();
  if(!record||terminal.has(record.state)||JSON.stringify(record.payload)!==JSON.stringify(payload))record={key:crypto.randomUUID(),payload};
  save();busy=true;controls();button.textContent='Submitting build request\u2026';feedback.replaceChildren(text('p','Resolving the commit and requesting its build\u2026'));
  try{show(await call('/api/delivery/operations',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':record.key},body:JSON.stringify(record.payload)}));}
  catch(error){feedback.replaceChildren(text('p',error.message+' Check the saved request before starting another attempt.'));busy=false;button.textContent='Check build request';controls();}
 });
 window.PreviewBuild={
  identity(value){
   identity=value;storageKey='lab.preview-build.'+value.username;
   try{record=JSON.parse(sessionStorage.getItem(storageKey)||'null');}catch{record=null;}
   if(record?.payload){form.elements.source_ref.value=record.payload.source_ref;form.elements.recipe.value=record.payload.recipe||'';}
   if(!value.is_admin||value.is_reader||value.is_delivery_service)feedback.replaceChildren(text('p','A human lab administrator can build previews from source.'));
   controls();if(record?.operation)check();else if(record)button.textContent='Check build request';
  },
  datasets(rows){const select=form.elements.dataset,current=record?.payload?.dataset||select.value;select.replaceChildren();for(const row of rows){const option=text('option',row.label||row.release);option.value=row.release;select.append(option);}if([...select.options].some(option=>option.value===current))select.value=current;controls();}
 };
 controls();
})();
