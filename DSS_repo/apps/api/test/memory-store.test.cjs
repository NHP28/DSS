const {test} = require('node:test');
const assert = require('node:assert/strict');
const {resolve} = require('node:path');

test('memory store serves the CSV catalog and seeds four distinct demo accounts', async () => {
  process.env.DATA_DIR = resolve(__dirname, '../../../data/danang');
  process.env.DEMO_PASSWORD = 'matkhau-demo';
  const {MemoryStore} = require('../dist/store.memory');
  const {verifyPassword} = require('../dist/auth/password');
  const store = new MemoryStore();
  await store.ping();
  const pois = await store.pois();
  assert.equal(pois.length, 996);
  assert.deepEqual([...new Set(pois.map(p => p.district))].sort((a, b) => a.localeCompare(b, 'vi')),
    ['Cẩm Lệ', 'Hải Châu', 'Hòa Vang', 'Liên Chiểu', 'Ngũ Hành Sơn', 'Sơn Trà', 'Thanh Khê'].sort((a, b) => a.localeCompare(b, 'vi')));
  assert.ok(pois.filter(p => p.hidden).every(p => p.category === 'tourist_spot'));
  assert.ok(pois.filter(p => p.hidden).length > 20 && pois.filter(p => p.hidden).length < 80);
  assert.deepEqual(await store.stats(), {pois: 996, users: 1500, checkins: 36210, accounts: 4});
  assert.match(await store.datasetSha(), /^[0-9a-f]{64}$/);
  const demo = await store.demoAccounts();
  assert.deepEqual(demo.map(a => a.username), ['demo_cafe', 'demo_amthuc', 'demo_thamquan', 'demo_dadang']);
  const accounts = await Promise.all(demo.map(a => store.accountByUsername(a.username)));
  assert.equal(new Set(accounts.map(a => a.datasetUserId)).size, 4);
  assert.equal(await verifyPassword('matkhau-demo', accounts[0].passwordHash), true);
  assert.ok((await store.visitedByDatasetUser(accounts[0].datasetUserId)).length > 5);

  const created = await store.createAccount({username: 'moi', displayName: 'Mới', passwordHash: 'x', interests: ['ca-phe']});
  assert.equal(created.datasetUserId, null);
  assert.equal(await store.createAccount({username: 'moi', displayName: 'Trùng', passwordHash: 'x', interests: []}), null);
  await store.addFeedback(created.id, 3, 'like');
  await store.addFeedback(created.id, 3, 'like');
  assert.deepEqual(await store.feedback(created.id), [{poiId: 3, action: 'like'}]);
  await store.removeFeedback(created.id, 3, 'like');
  assert.deepEqual(await store.feedback(created.id), []);
});
