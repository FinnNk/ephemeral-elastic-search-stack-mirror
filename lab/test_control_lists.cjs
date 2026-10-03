const {test}=require('node:test');
const assert=require('node:assert/strict');
const {select}=require('./control_lists.js');
const rows=Array.from({length:55},(_,i)=>({id:String(i).padStart(3,'0'),name:'lab-'+i,
  owner:i%2?'alice':'bob',state:i%5?'ready':'deleted',release_id:'esci-gb-v1',
  created_at:new Date(Date.UTC(2026,0,1,0,i)).toISOString()}));
test('combined search and status filters apply before paging',()=>{
  const result=select(rows,{search:'ALICE lab',fields:['name','owner'],filters:{state:'active'},size:12});
  assert.equal(result.total,22);assert.equal(result.rows.length,12);
  assert.ok(result.rows.every(row=>row.owner==='alice'&&row.state==='ready'));
});
test('pages have no duplicates or gaps, newest first',()=>{
  const results=[1,2,3,4,5].flatMap(page=>select(rows,{page,size:12}).rows);
  assert.equal(results.length,55);assert.equal(new Set(results.map(row=>row.id)).size,55);
  assert.equal(results[0].id,'054');assert.equal(results.at(-1).id,'000');
});
test('shrinking lists clamp the page and empty lists have usable bounds',()=>{
  assert.equal(select(rows,{page:100,size:12}).page,5);
  const result=select(rows,{search:'absent',fields:['name'],page:5});
  assert.equal(result.page,1);assert.equal(result.pages,1);assert.equal(result.first,0);assert.equal(result.last,0);
});
test('query order is preserved and source records are not mutated',()=>{
  const original=rows.map(row=>row.id);const result=select(rows,{order:'provided',page:2,size:25});
  assert.equal(result.rows[0].id,'025');assert.deepEqual(rows.map(row=>row.id),original);
});
test('ordering and tie breaks are deterministic',()=>{
  const same=[{id:'a',created_at:'same'},{id:'b',created_at:'same'}];
  assert.deepEqual(select(same).rows.map(row=>row.id),['b','a']);
  assert.deepEqual(select(same,{order:'oldest'}).rows.map(row=>row.id),['a','b']);
});
