/* Shared navigation is progressive enhancement; page forms work without it. */
(() => {
  if (document.querySelector('.layout')) return;
  const body=document.body;
  let main=body.querySelector('main');
  if(!main){main=document.createElement('main');for(const child of [...body.children])if(child.tagName!=='SCRIPT')main.append(child);body.prepend(main);}
  const header=body.querySelector(':scope > header');if(header)main.prepend(header);
  main.id ||= 'main-content';
  const skip=document.createElement('a');skip.href='#'+main.id;skip.className='skip-link';skip.textContent='Skip to content';
  const layout=document.createElement('div');layout.className='layout';
  const aside=document.createElement('aside');
  aside.innerHTML='<div class="brand"><span class="mark" aria-hidden="true">◈</span> Search lab</div><p class="subtitle">Delivery workspace</p><nav class="lab-nav" aria-label="Main navigation"></nav><footer>GitOps delivery<br>Source → reviewed state → deployment</footer>';
  const nav=aside.querySelector('nav');
  for(const [href,label] of [['/release-dashboard','Releases'],['/','Search environments'],['/production-release','Production release'],['https://gitea.localhost:34443/elastic-agent/delivery-source/actions','Workflows ↗']]){
    const a=document.createElement('a');a.href=href;a.textContent=label;if(location.pathname===href)a.setAttribute('aria-current','page');nav.append(a);
  }
  const content=document.createElement('div'),top=document.createElement('div');top.className='topbar';top.textContent='Delivery / '+(document.querySelector('h1')?.textContent||'Search lab');
  content.append(top,main);layout.append(aside,content);body.prepend(skip,layout);
})();
