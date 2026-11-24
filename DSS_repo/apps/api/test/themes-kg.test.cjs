const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {startApp} = require('./helpers.cjs');
const {isJunkPoiName, normalizeDistrict} = require('../dist/database/display');
const {timeSlot} = require('../dist/kg/kg.service');

test('junk tourist-spot names are detected without touching real places', () => {
  for (const name of ['End of the Road?', 'This is a dead end! Jungle trekking from here!', 'Great Valley View', 'Valley and Quarry Viewpoint', 'fishing boats', 'Upper Path Ends Here'])
    assert.equal(isJunkPoiName(name, 'tourist_spot'), true, name);
  for (const name of ['Chùa Nam Sơn', 'Non Nuoc Beach', 'Đèo Hải Vân', 'Chợ đêm Helio', 'Ban Co Peak'])
    assert.equal(isJunkPoiName(name, 'tourist_spot'), false, name);
  assert.equal(isJunkPoiName('Sea View Coffee', 'cafe'), false);
});

test('district spellings collapse to the seven districts', () => {
  assert.equal(normalizeDistrict('Quận Sơn Trà'), 'Sơn Trà');
  assert.equal(normalizeDistrict('Hai Chau'), 'Hải Châu');
  assert.equal(normalizeDistrict('Ngu Hanh Son'), 'Ngũ Hành Sơn');
  assert.equal(normalizeDistrict('quận Liên Chiểu'), 'Liên Chiểu');
  assert.equal(normalizeDistrict('Danang'), 'Hải Châu');
  assert.equal(normalizeDistrict('Cẩm Lệ'), 'Cẩm Lệ');
});

test('time slots cover the day without gaps', () => {
  assert.deepEqual([5,10,11,13,14,17,18,22,23,0,4].map(timeSlot),
    ['morning','morning','noon','noon','afternoon','afternoon','evening','evening','night','night','night']);
});

test('themes list counts visible places and theme recommendations apply the theme filter', async () => {
  const t = await startApp();
  try {
    const themes = (await t.call('GET', '/api/themes')).json();
    assert.equal(themes.length, 8);
    assert.equal(themes.find(x=>x.slug==='ca-phe').count, 2);
    assert.equal(themes.find(x=>x.slug==='tham-quan-giai-tri').count, 1); // hidden POI not counted
    const breakfast = (await t.call('POST', '/api/themes/bua-sang/recommendations', {})).json();
    const items = breakfast.groups.flatMap(g=>g.items);
    assert.ok(items.length > 0);
    assert.ok(items.every(p=>['cafe','restaurant'].includes(p.category) && p.price_avg <= 60000));
    assert.equal(breakfast.query.hour, 7);
    assert.equal(breakfast.theme.slug, 'bua-sang');
    const coast = (await t.call('POST', '/api/themes/ven-bien/recommendations', {hour:9})).json();
    assert.ok(coast.groups.flatMap(g=>g.items).every(p=>['Sơn Trà','Ngũ Hành Sơn'].includes(p.district)));
    assert.equal(coast.query.hour, 9);
    const cheap = (await t.call('POST', '/api/themes/tiet-kiem/recommendations', {})).json();
    assert.deepEqual(cheap.groups.find(g=>g.category==='cafe').items.map(p=>p.id), [0]); // cheapest 35% of 2 cafes
    const far = await t.call('POST', '/api/themes/ca-phe/recommendations', {latitude:0, longitude:0, radiusKm:1});
    assert.equal(far.statusCode, 200);
    assert.deepEqual(far.json().groups, []);
    assert.equal((await t.call('POST', '/api/themes/khong-co/recommendations', {})).statusCode, 404);
  } finally { await t.close(); }
});

test('graph endpoints answer 503 with a hint when Neo4j is down, and recommendations still work', async () => {
  const t = await startApp();
  try {
    for (const url of ['/api/kg/stats', '/api/kg/poi/1', '/api/kg/poi/1/similar', '/api/kg/explain?poiId=1']) {
      const res = await t.call('GET', url);
      assert.equal(res.statusCode, 503, url);
      assert.match(res.json().message, /Neo4j/);
    }
    assert.equal((await t.call('GET', '/api/kg/poi/abc')).statusCode, 400);
    assert.equal((await t.call('POST', '/api/recommendations', {})).statusCode, 200);
  } finally { await t.close(); }
});

test('graph endpoints shape Neo4j rows for the viewer', async () => {
  const graph = async (query, params) => {
    if (query.startsWith('RETURN 1')) return [{ok:1}];
    if (query.includes('labels(n)')) return [{label:'POI',count:996},{label:'User',count:1500}];
    if (query.includes('type(r)')) return [{type:'VISITED',count:30000}];
    if (query.includes('collect(DISTINCT')) return params.id === 1 ? [{p:{properties:{name:'Cà phê B',rating:4,price_avg:60000}},
      c:{properties:{key:'cafe',label:'Cà phê'}}, d:{properties:{name:'Sơn Trà'}},
      busy:[{slot:'morning',label:'Buổi sáng (5–10h)',count:9},{slot:null,label:null,count:null}], near:[{id:0,name:'Cà phê A',km:1.234}]}] : [{p:null}];
    if (query.includes('sharedVisitors')) return [{id:0,name:'Cà phê A',category:'cafe',sharedVisitors:5},{id:3,name:'Quán ăn',category:'restaurant',sharedVisitors:2}];
    if (query.includes('p.name AS name')) return [{name:'Cà phê B',district:'Sơn Trà',share:0.4,slotLabel:'Buổi sáng (5–10h)',visitors:12}];
    if (query.includes('n.km AS km')) return params.anchors.includes(0) ? [{name:'Cà phê A',km:1.234}] : [];
    if (query.includes('AS users')) return [{users:3}];
    return [];
  };
  const t = await startApp({graph});
  try {
    assert.deepEqual((await t.call('GET', '/api/kg/stats')).json(), {nodes:{POI:996,User:1500}, relationships:{VISITED:30000}});
    const poi = (await t.call('GET', '/api/kg/poi/1')).json();
    assert.deepEqual(poi.nodes.map(n=>n.id), ['poi:1','cat:cafe','dist:Sơn Trà','slot:morning','poi:0','poi:3']);
    assert.deepEqual(poi.links.map(l=>l.type), ['IN_CATEGORY','LOCATED_IN','BUSY_AT','NEAR','CO_VISITED','CO_VISITED']);
    assert.match(poi.cypher, /MATCH \(p:POI \{id: 1\}\)/);
    assert.equal((await t.call('GET', '/api/kg/poi/999')).statusCode, 404);
    assert.equal((await t.call('GET', '/api/system')).json().graph, true);
    const guest = (await t.call('GET', '/api/kg/explain?poiId=1&hour=8')).json();
    assert.deepEqual(guest.reasons.map(r=>r.kind), ['busy_slot','visitors','district']);
    const {cookie} = await t.register('thich_ca_phe');
    await t.call('POST', '/api/feedback', {poiId:0, action:'like'}, cookie);
    const mine = (await t.call('GET', '/api/kg/explain?poiId=1&hour=8', undefined, cookie)).json();
    assert.deepEqual(mine.reasons.map(r=>r.kind), ['near_liked','co_visited','busy_slot','visitors','district']);
    assert.match(mine.reasons[0].text, /Cà phê A/);
  } finally { await t.close(); }
});
