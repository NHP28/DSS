const {test} = require('node:test');
const assert = require('node:assert/strict');
const {ahp,haversine,topsis} = require('../dist/dss');

test('AHP recovers known priorities and rejects inconsistent/invalid matrices',()=>{
  const expected=[.25,.2,.15,.3,.1];
  const result=ahp(expected.map(a=>expected.map(b=>a/b)));
  expected.forEach((x,i)=>assert.ok(Math.abs(x-result.weights[i])<1e-9));
  assert.ok(result.consistencyRatio<1e-9);
  assert.throws(()=>ahp([[1]]));
  const bad=Array.from({length:5},()=>Array(5).fill(1));
  bad[0][1]=9;bad[1][0]=1/9;bad[1][2]=9;bad[2][1]=1/9;bad[2][0]=9;bad[0][2]=1/9;
  assert.throws(()=>ahp(bad),/nhất quán/);
  bad[0][0]=NaN;assert.throws(()=>ahp(bad));
});
test('TOPSIS respects both cost criteria, keeps neutral ties finite and orders deterministically',()=>{
  const base={id:0,name:'a',category:'cafe',district:'A',latitude:16,longitude:108,rating:5,price_avg:20000,popularity:80,distanceKm:1,preference:.8};
  const lower={...base,id:1,price_avg:60000,distanceKm:3,rating:3,preference:.1,popularity:20};
  const ranked=topsis([lower,base],[.2,.2,.2,.2,.2]);
  assert.equal(ranked[0].id,0);assert.equal(ranked[0].topsisScore,1);assert.equal(ranked[1].topsisScore,0);
  assert.equal(topsis([base],[1,0,0,0,0])[0].topsisScore,.5);
  assert.deepEqual(topsis([base,{...base,id:1}],[0,1,0,0,0]).map(p=>p.id),[0,1]);
  assert.throws(()=>topsis([base],[0,0,0,0,0]));
  assert.equal(haversine(16,108,16,108),0);
  assert.ok(haversine(0,0,0,1)>111&&haversine(0,0,0,1)<112);
});
