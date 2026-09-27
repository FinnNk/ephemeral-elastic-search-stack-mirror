// Presentation-only layout for the model exported from workspace.dsl.
// Names resolve model IDs; the script does not create architecture elements.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = path.dirname(fileURLToPath(import.meta.url));
const workspace = JSON.parse(fs.readFileSync(path.join(dir, '.structurizr/workspace.json')));
const elements = new Map();
const relationships = new Map();
function visit(value) {
  if (!value || typeof value !== 'object') return;
  if (value.id && (value.name || value.containerId)) elements.set(value.id, value);
  if (value.id && value.sourceId) relationships.set(value.id, value);
  for (const child of Object.values(value)) {
    if (Array.isArray(child)) child.forEach(visit);
    else if (child && typeof child === 'object') visit(child);
  }
}
visit(workspace.model);
const name = id => elements.get(id)?.name;
function position(view, locations) {
  delete view.automaticLayout;
  for (const el of view.elements) {
    const location = locations[name(el.id)];
    if (location) [el.x, el.y] = location;
  }
}
function route(view, source, target, points, position = 50) {
  for (const rel of view.relationships || []) {
    const model = relationships.get(rel.id);
    if (name(model.sourceId) === source && name(model.destinationId) === target) {
      rel.vertices = points.map(([x,y]) => ({x,y}));
      rel.position = position;
      rel.routing = 'Direct';
    }
  }
}
const styles = workspace.views.configuration.styles.elements;
Object.assign(styles.find(s => s.tag === 'Element'), {width:420,height:260,fontSize:24});
Object.assign(styles.find(s => s.tag === 'Person'), {height:380});
// Deployment boundaries use the correct built-in tag and remain visually quiet.
Object.assign(styles.find(s => s.tag === 'Deployment Node'), {background:'#f4f7fa',color:'#25364b'});

const context = workspace.views.systemContextViews[0];
position(context, {'Lab user':[100,100],'Platform engineer':[100,850],
  'Search relevance lab':[900,450],'Source and build platform':[1700,100],'Deployment platform':[1700,950]});
// The context focuses on explicit system contracts; detailed ECK control is in the model.
context.relationships = context.relationships.filter(r => {
  const m=relationships.get(r.id); return !(name(m.sourceId)==='Deployment platform' && name(m.destinationId)==='Search relevance lab');
});
route(context,'Lab user','Source and build platform',[[650,80],[1910,80]],70);
route(context,'Source and build platform','Search relevance lab',[[1630,650]],50);

const control = workspace.views.containerViews.find(v=>v.key==='02-control');
control.elements = control.elements.filter(e=>name(e.id)!=='Lab user');
const visible = new Set(control.elements.map(e=>e.id));
control.relationships = control.relationships.filter(r=>{
  const m=relationships.get(r.id);return visible.has(m.sourceId)&&visible.has(m.destinationId);
});
position(control, {'Lab web UI':[100,700],'Lab API':[900,700],'Lab metadata':[1700,700],
  'Search API':[1700,1200],'Lease cleanup job':[100,1200],'Source and build platform':[900,100],
  'Deployment platform':[900,1800]});
route(control,'Lab API','Source and build platform',[[820,500],[820,230]],55);
route(control,'Source and build platform','Lab API',[[1430,230],[1430,500]],55);

const evaluation = workspace.views.containerViews.find(v=>v.key==='03-evaluation');
position(evaluation, {'Dataset and workload generator':[100,100],'Artifact store':[900,100],'Index build job':[1700,100],
  'Evaluation job':[100,800],'Search API':[900,800],'Shared search engine':[1700,800],
  'Gatling load job':[900,1500],'Index snapshot repository':[1700,1500]});
route(evaluation,'Evaluation job','Shared search engine',[[310,1260],[1910,1260]],80);
route(evaluation,'Gatling load job','Artifact store',[[1360,1630],[1360,500],[1250,500]],35);

route(evaluation,'Gatling load job','Search API',[],75);

const create = workspace.views.dynamicViews[0];
position(create, {'Gitea':[100,100],'Build runner':[750,100],'Lab API':[1500,100],
  'Argo CD':[100,800],'Kubernetes API':[750,800],'Search API':[1500,800],'Shared search engine':[2150,800]});
route(create,'Build runner','Gitea',[[960,490],[310,490]],50);

route(create,'Lab API','Argo CD',[[1400,650],[310,650]],60);

function placeDeployment(view, groups) {
  delete view.automaticLayout;
  // Placement view only. Container views carry the directed interactions.
  view.relationships = [];
  for (const el of view.elements) {
    const model=elements.get(el.id);
    if (!model.containerId) continue;
    const parent=[...elements.values()].find(n=>n.containerInstances?.some(c=>c.id===el.id));
    const group=groups[parent?.name];
    if (!group) throw new Error(`No placement for ${parent?.name}`);
    const index=parent.containerInstances.findIndex(c=>c.id===el.id);
    el.x=group.x+(index%group.cols)*560;
    el.y=group.y+Math.floor(index/group.cols)*390;
  }
}
placeDeployment(workspace.views.deploymentViews.find(v=>v.key==='05-local'),{
  'Local control process':{x:160,y:160,cols:2},
  'Snapshot storage':{x:1480,y:160,cols:1},
  'Persistent platform namespace':{x:160,y:1100,cols:2},
  'Local control plane':{x:160,y:2050,cols:1},
  'Persistent lab services':{x:1480,y:1100,cols:2},
  'Experiment namespaces':{x:160,y:2650,cols:3},
  'Shared search namespace':{x:2080,y:2650,cols:1},
  'Comparison jobs':{x:160,y:3250,cols:2}
});
placeDeployment(workspace.views.deploymentViews.find(v=>v.key==='06-azure'),{
  'Organisation delivery services':{x:160,y:160,cols:2},
  'Azure Container Registry':{x:2080,y:160,cols:1},
  'Azure Blob Storage':{x:1280,y:160,cols:1},
  'Platform and lab services':{x:160,y:1450,cols:3},
  'Managed control plane':{x:2080,y:1450,cols:1},
  'Experiment worker nodes':{x:160,y:2500,cols:3},
  'Shared Elasticsearch nodes':{x:2080,y:2500,cols:1},
  'Comparison workers':{x:160,y:3080,cols:2}
});
const canvases = {'01-context':[2380,1500], '02-control':[2380,2250],
  '03-evaluation':[2380,2110], '04-create':[2850,1450],
  '05-local':[2800,4100], '06-azure':[2800,3860]};
for (const collection of ['systemContextViews','containerViews','dynamicViews','deploymentViews']) {
  for (const view of workspace.views[collection] || []) {
    const [width,height]=canvases[view.key];
    view.dimensions={width,height};
  }
}
fs.writeFileSync(path.join(dir,'.structurizr/workspace-layout.json'),JSON.stringify(workspace,null,2)+'\n');
console.log('Applied presentation layout to six C4 views.');
