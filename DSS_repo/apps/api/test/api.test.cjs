const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {startApp} = require('./helpers.cjs');

let t;
before(async () => { t = await startApp(); });
after(async () => { await t.close(); });
const recommend = (payload, cookie) => t.call('POST', '/api/recommendations', payload, cookie);

test('HTTP DTO rejects invalid coordinates, time, topK and extra properties', async () => {
  for (const payload of [{hour:24},{latitude:100},{topK:0},{radiusKm:-1},{userId:12},{unknown:1},{matrix:[[null]]},{model:'xgboost'}]) {
    const res = await recommend(payload);
    assert.equal(res.statusCode, 400, res.body);
  }
});

test('guest gets cold-start ranking per category with budget and radius filters', async () => {
  t.ai.mode = 'ok';
  const res = await recommend({radiusKm:10, maxPrice:100000});
  assert.equal(res.statusCode, 200, res.body);
  const body = res.json();
  assert.equal(body.personalization, 'cold_start');
  assert.equal(body.source, 'hourly_popularity');
  assert.equal(body.warning, null);
  assert.deepEqual(body.groups.map(g=>g.category).sort(), ['cafe','restaurant','tourist_spot']);
  assert.equal(body.rankingScope, 'within_category');
  assert.ok(!('userId' in t.ai.requests.at(-1)) && !('historyPoiIds' in t.ai.requests.at(-1)));
});

test('filters that match nothing return an empty result, not an error', async () => {
  const res = await recommend({latitude:0, longitude:0, radiusKm:0.1});
  assert.equal(res.statusCode, 200);
  assert.equal(res.json().totalCandidates, 0);
  assert.deepEqual(res.json().groups, []);
});

test('falls back to hourly popularity with a warning when the model service is down or mismatched', async () => {
  for (const mode of ['down','mismatch']) {
    t.ai.mode = mode;
    const res = await recommend({category:'cafe'});
    assert.equal(res.statusCode, 200, res.body);
    const body = res.json();
    assert.equal(body.source, 'hourly_popularity');
    assert.ok(body.warning);
    assert.equal(body.groups[0].total, 2);
    assert.equal(body.personalization, 'cold_start');
  }
  t.ai.mode = 'ok';
});

test('junk-named POIs stay hidden unless asked for', async () => {
  const names = body => body.groups.flatMap(g=>g.items).map(p=>p.name);
  assert.ok(!names((await recommend({radiusKm:50})).json()).includes('End of the Road?'));
  assert.ok(names((await recommend({radiusKm:50, showHidden:true})).json()).includes('End of the Road?'));
});

test('candidate pool keeps the model\'s top N of each category before TOPSIS', async () => {
  const body = (await recommend({radiusKm:50, candidatePool:1})).json();
  assert.ok(body.groups.length >= 3);
  for (const group of body.groups) assert.equal(group.items.length, 1);
  // Stub scores grow with the id, so the higher id of each category survives.
  assert.equal(body.groups.find(g=>g.category==='cafe').items[0].id, 1);
  assert.equal(body.groups.find(g=>g.category==='cafe').total, 2);
});

test('demo account scores as its dataset user and hides that user\'s history', async () => {
  await t.store.createAccount({username:'demo_cafe', displayName:'Demo', passwordHash:'x', interests:[], datasetUserId:12});
  const cookie = `dss_session=${t.app.get(require('../dist/auth/auth.service').AuthService).token(t.store.state.accounts.at(-1).id)}`;
  const body = (await recommend({category:'cafe'}, cookie)).json();
  assert.equal(t.ai.requests.at(-1).userId, 12);
  assert.equal(body.personalization, 'trained_user');
  assert.equal(body.source, 'tas_gnn');
  assert.deepEqual(body.groups[0].items.map(p=>p.id), [1]);
  const all = (await recommend({category:'cafe', excludeVisited:false}, cookie)).json();
  assert.deepEqual(all.groups[0].items.map(p=>p.id).sort(), [0,1]);
  assert.equal(all.groups[0].items.find(p=>p.id===0).visited, true);
});

test('a self-registered account is personalised by fold-in once it has three places', async () => {
  const {cookie} = await t.register('nguoi_moi');
  const feedback = (poiId, action) => t.call('POST', '/api/feedback', {poiId, action}, cookie);
  assert.equal((await feedback(0, 'like')).statusCode, 200);
  await feedback(3, 'like');
  let body = (await recommend({excludeVisited:false}, cookie)).json();
  assert.ok(!('historyPoiIds' in t.ai.requests.at(-1)));
  assert.equal(body.personalization, 'cold_start');
  assert.equal(body.historyCount, 2);
  await feedback(4, 'visit');
  body = (await recommend({excludeVisited:false, radiusKm:50, model:'lightgcn'}, cookie)).json();
  assert.deepEqual([...t.ai.requests.at(-1).historyPoiIds].sort(), [0,3,4]);
  assert.equal(t.ai.requests.at(-1).model, 'lightgcn');
  assert.ok(!('userId' in t.ai.requests.at(-1)));
  assert.equal(body.personalization, 'foldin');
  assert.equal(body.source, 'lightgcn_foldin');
  assert.equal(body.groups.flatMap(g=>g.items).find(p=>p.id===0).saved, true);

  const saved = (await t.call('GET', '/api/saved', undefined, cookie)).json();
  assert.deepEqual(saved.liked.map(p=>p.id).sort(), [0,3]);
  assert.deepEqual(saved.visited.map(p=>p.id), [4]);
  await feedback(0, 'unlike');
  assert.deepEqual((await t.call('GET', '/api/saved', undefined, cookie)).json().liked.map(p=>p.id), [3]);
  assert.equal((await feedback(999, 'like')).statusCode, 400);
});

test('feedback and saved places require a session', async () => {
  assert.equal((await t.call('POST', '/api/feedback', {poiId:1, action:'like'})).statusCode, 401);
  assert.equal((await t.call('GET', '/api/saved')).statusCode, 401);
});

test('saved model settings drive recommendations and request fields override them', async () => {
  const {cookie} = await t.register('thich_lightgcn');
  const put = await t.call('PUT', '/api/settings', {model:'lightgcn', useTime:false, topK:5, radiusKm:50, candidatePool:20, preset:'custom', weightLevels:[9,1,1,1,1]}, cookie);
  assert.equal(put.statusCode, 200, put.body);
  let body = (await recommend({}, cookie)).json();
  assert.equal(t.ai.requests.at(-1).model, 'lightgcn');
  assert.equal(t.ai.requests.at(-1).useTime, false);
  assert.equal(body.query.radiusKm, 50);
  assert.ok(Math.abs(body.weights[0] - 9/13) < 1e-6);
  body = (await recommend({model:'tas_gnn', preset:'balanced'}, cookie)).json();
  assert.equal(t.ai.requests.at(-1).model, 'tas_gnn');
  assert.deepEqual(body.weights, [.25,.2,.15,.3,.1]);
});

test('system status reports the model service and a missing graph', async () => {
  const body = (await t.call('GET', '/api/system')).json();
  assert.equal(body.ai.ready, true);
  assert.deepEqual(body.ai.models, ['tas_gnn','lightgcn']);
  assert.equal(body.graph, false);
});

test('an explicit "no limit" overrides a saved budget, and themes ignore the saved budget', async () => {
  const {cookie} = await t.register('ngan_sach');
  await t.call('PUT', '/api/settings', {maxPrice: 50000, radiusKm: 50}, cookie);
  const ids = body => body.groups.flatMap(g => g.items).map(p => p.id);
  assert.ok(!ids((await recommend({}, cookie)).json()).includes(2));
  const open = (await recommend({maxPrice: null}, cookie)).json();
  assert.ok(ids(open).includes(2));
  assert.equal(open.query.maxPrice, null);
  const hotels = (await t.call('POST', '/api/themes/luu-tru/recommendations', {}, cookie)).json();
  assert.deepEqual(ids(hotels), [2]);
});
