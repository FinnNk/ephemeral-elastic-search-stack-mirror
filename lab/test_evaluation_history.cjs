/* Unit tests use an in-memory DOM, with no browser or network access. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const ids=new Map();
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.text='';}
 set id(value){ids.set(value,this);this.identifier=value;}
 get id(){return this.identifier;}
 set textContent(value){this.text=String(value);this.children=[];}
 get textContent(){return this.text+this.children.map(n=>n.textContent).join('');}
 append(child){this.children.push(child);}
 replaceChildren(){this.children=[];this.text='';}
 setAttribute(key,value){this.attributes[key]=String(value);}
 addEventListener(){}
}
const document={createElement:tag=>new Element(tag),getElementById:id=>{if(id==='evaluation-live'&&!ids.has(id))return null;if(!ids.has(id)){const n=new Element('div');n.id=id;}return ids.get(id);}};
const context=vm.createContext({document,Node:Element,location:{pathname:'/api/delivery/operations/'+'a'.repeat(32)},Date,URL,console});
let source=fs.readFileSync(path.join(__dirname,'delivery_results.js'),'utf8');
source=source.replace("$('refresh').addEventListener('click',load);load();","$('refresh').addEventListener('click',load);");
vm.runInContext(source,context);
let clock=1000;
function send(phase,fields={}){context.input={phase,observed_ms:++clock,...fields};vm.runInContext('showEvaluation(input)',context);}
function groups(){return JSON.parse(vm.runInContext('JSON.stringify(groupedEvaluations())',context));}
function reset(){vm.runInContext('evaluationPhases.length=0;latestEvaluation=null',context);ids.get('content').replaceChildren();}
const suite='result-regression / standard',job='capture-one';
send('Waiting for capture worker',{suite,job});
send('Capturing query results',{suite,job,unit:'queries',metrics:{completed:841,total:1000,failed:0}});
send('Capture complete',{suite,job,unit:'queries',metrics:{completed:1000,total:1000,failed:0}});
send('Comparing result order',{suite,unit:'queries',metrics:{completed:1000,total:1000,failed:0}});
assert.equal(groups().length,1);assert.equal(groups()[0].steps.length,2);
assert.equal(groups()[0].steps[0].metrics.completed,1000);assert.equal(groups()[0].steps[0].captureComplete,true);
assert.equal(groups()[0].steps[0].events[1].metrics.completed,841);
assert.ok(ids.get('evaluation-live').textContent.includes('Final capture count'));
assert.ok(!ids.get('evaluation-live').textContent.includes('1. result-regression'));
send('Scoring frozen results',{suite:'relevance / standard',unit:'queries',metrics:{completed:1000,total:1000,failed:0}});
send('Calculating significance',{suite:'relevance / standard'});
assert.equal(groups()[1].steps.length,1);assert.equal(groups()[1].steps[0].metrics.completed,1000);
assert.ok(ids.get('evaluation-live').textContent.includes('Captured queries available for scoring'));
send('Resolving judgement gaps',{suite:'seasonal',unit:'pairs',metrics:{completed:0,total:40}});
send('Waiting for judgement batch',{suite:'seasonal',unit:'pairs',metrics:{completed:0,total:40}});
send('Judgement batch completed',{suite:'seasonal',unit:'pairs',metrics:{completed:40,total:40}});
send('Freezing judgement snapshot',{suite:'seasonal',unit:'pairs',metrics:{completed:40,total:40}});
assert.equal(groups()[2].steps.length,1);assert.equal(groups()[2].steps[0].metrics.completed,40);
const before=ids.get('evaluation-live').textContent;
ids.get('content').replaceChildren();ids.delete('evaluation-live');vm.runInContext('renderEvaluationHistory()',context);
assert.equal(ids.get('evaluation-live').textContent,before);
reset();send('Capturing query results',{suite,job,unit:'queries',metrics:{completed:841,total:1000,failed:1},metrics_stale:true});
assert.equal(groups()[0].steps[0].captureComplete,undefined);
assert.ok(ids.get('evaluation-live').textContent.includes('has not reported its final count'));
assert.ok(ids.get('evaluation-live').textContent.includes('Last known counters'));
send('Capture complete',{suite,job,unit:'queries',metrics:{completed:1000,total:1000,failed:1}});
send('Waiting for capture worker',{suite,job:'capture-two'});
assert.equal(groups().length,2);assert.equal(groups()[0].steps[0].metrics.failed,1);
assert.equal(groups()[1].steps[0].metrics,null);
reset();send('Preparing baseline preview');send('Preparing candidate preview');send('Checking public API configurations');
assert.equal(groups().length,1);assert.equal(groups()[0].title,'Prepare APIs');
assert.equal(groups()[0].steps.length,1);assert.equal(groups()[0].steps[0].events.length,3);
console.log('Grouped capture, final counts, scoring inputs, judgements, repeated Jobs, stale samples and refresh retention passed.');
