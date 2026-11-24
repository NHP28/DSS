const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {startApp} = require('./helpers.cjs');
const {signSession} = require('../dist/auth/session');
const {hashPassword, verifyPassword} = require('../dist/auth/password');
const {parseSettings, DEFAULT_SETTINGS} = require('../dist/settings/settings');

let t;
before(async () => { t = await startApp(); });
after(async () => { await t.close(); });

test('passwords are salted scrypt hashes', async () => {
  const first = await hashPassword('matkhau123'), second = await hashPassword('matkhau123');
  assert.notEqual(first, second);
  assert.ok(first.startsWith('scrypt$'));
  assert.equal(await verifyPassword('matkhau123', first), true);
  assert.equal(await verifyPassword('matkhau124', first), false);
  assert.equal(await verifyPassword('matkhau123', 'plain-text'), false);
});

test('register sets an HttpOnly session cookie and never returns the hash', async () => {
  const {response, cookie} = await t.register('lan_anh', {interests:['ca-phe','an-uong']});
  assert.equal(response.statusCode, 201, response.body);
  const header = String(response.headers['set-cookie']);
  assert.match(header, /HttpOnly/);
  assert.match(header, /SameSite=Lax/);
  assert.ok(!response.body.includes('scrypt'));
  const me = await t.call('GET', '/api/auth/me', undefined, cookie);
  assert.equal(me.statusCode, 200);
  assert.equal(me.json().account.username, 'lan_anh');
  assert.deepEqual(me.json().account.interests, ['ca-phe','an-uong']);
  assert.ok(!('passwordHash' in me.json().account));
});

test('register validates username, password length, interests and uniqueness', async () => {
  assert.equal((await t.register('lan_anh')).response.statusCode, 409);
  assert.equal((await t.register('ngan', {password:'1234567'})).response.statusCode, 400);
  assert.equal((await t.register('Tên Có Dấu')).response.statusCode, 400);
  assert.equal((await t.register('khong_chu_de', {interests:[]})).response.statusCode, 400);
  assert.equal((await t.register('chu_de_la', {interests:['khong-co']})).response.statusCode, 400);
});

test('login accepts the right password and rejects the wrong one', async () => {
  await t.register('minh');
  const ok = await t.call('POST', '/api/auth/login', {username:'minh', password:'matkhau123'});
  assert.equal(ok.statusCode, 200, ok.body);
  assert.equal((await t.call('GET', '/api/auth/me', undefined, t.cookieOf(ok))).json().account.username, 'minh');
  assert.equal((await t.call('POST', '/api/auth/login', {username:'minh', password:'sai-mat-khau'})).statusCode, 401);
  assert.equal((await t.call('POST', '/api/auth/login', {username:'khong_ton_tai', password:'matkhau123'})).statusCode, 401);
});

test('tampered, expired and foreign-signed cookies are rejected', async () => {
  const {cookie} = await t.register('hoa');
  const flipped = cookie.slice(0, -1) + (cookie.endsWith('A') ? 'B' : 'A');
  assert.equal((await t.call('GET', '/api/auth/me', undefined, flipped)).statusCode, 401);
  const id = t.store.state.accounts.find(a=>a.username==='hoa').id;
  const expired = signSession({accountId:id, exp:Math.floor(Date.now()/1000)-10}, process.env.AUTH_SECRET);
  assert.equal((await t.call('GET', '/api/auth/me', undefined, `dss_session=${expired}`)).statusCode, 401);
  const forged = signSession({accountId:id, exp:Math.floor(Date.now()/1000)+1000}, 'another-secret-another-secret-123456');
  assert.equal((await t.call('GET', '/api/auth/me', undefined, `dss_session=${forged}`)).statusCode, 401);
  assert.equal((await t.call('GET', '/api/auth/me')).statusCode, 401);
});

test('logout clears the cookie', async () => {
  const response = await t.call('POST', '/api/auth/logout');
  assert.match(String(response.headers['set-cookie']), /Max-Age=0/);
});

test('ten wrong passwords lock the username for the window', async () => {
  await t.register('bi_khoa');
  for (let i = 0; i < 10; i++) assert.equal((await t.call('POST', '/api/auth/login', {username:'bi_khoa', password:'sai'})).statusCode, 401);
  assert.equal((await t.call('POST', '/api/auth/login', {username:'bi_khoa', password:'matkhau123'})).statusCode, 429);
});

test('settings are per account, validated, and resettable', async () => {
  const {cookie} = await t.register('cai_dat'), other = await t.register('nguoi_khac');
  assert.equal((await t.call('GET', '/api/settings')).statusCode, 401);
  assert.deepEqual((await t.call('GET', '/api/settings', undefined, cookie)).json().settings, DEFAULT_SETTINGS);
  for (const bad of [{topK:99},{model:'gpt'},{candidatePool:7},{weightLevels:[1,2,3]},{radiusKm:0},{hacker:true}])
    assert.equal((await t.call('PUT', '/api/settings', bad, cookie)).statusCode, 400, JSON.stringify(bad));
  const saved = await t.call('PUT', '/api/settings', {model:'lightgcn', topK:7}, cookie);
  assert.equal(saved.statusCode, 200, saved.body);
  assert.equal((await t.call('GET', '/api/settings', undefined, cookie)).json().settings.model, 'lightgcn');
  assert.equal((await t.call('GET', '/api/settings', undefined, cookie)).json().settings.topK, 7);
  assert.equal((await t.call('GET', '/api/settings', undefined, other.cookie)).json().settings.model, 'tas_gnn');
  assert.deepEqual((await t.call('DELETE', '/api/settings', undefined, cookie)).json().settings, DEFAULT_SETTINGS);
  assert.deepEqual(parseSettings({}), DEFAULT_SETTINGS);
});

test('review fixes: guests need no signing key, the example secret is refused, the throttle ignores case and spacing', async () => {
  const real = process.env.AUTH_SECRET;
  try {
    delete process.env.AUTH_SECRET;
    assert.equal((await t.call('POST', '/api/recommendations', {})).statusCode, 200);
    assert.equal((await t.call('GET', '/api/auth/me')).statusCode, 401);
    process.env.AUTH_SECRET = 'doi-chuoi-nay-thanh-32-ky-tu-ngau-nhien';
    assert.equal((await t.register('dung_khoa_mau')).response.statusCode, 500);
  } finally { process.env.AUTH_SECRET = real; }
  await t.register('hay_doi_kieu_go');
  for (const name of ['Hay_Doi_Kieu_Go', 'HAY_DOI_KIEU_GO', ' hay_doi_kieu_go ', 'hay_doi_kieu_go', 'Hay_doi_kieu_go', 'hay_Doi_kieu_go', 'hay_doi_Kieu_go', 'hay_doi_kieu_Go', 'HAY_doi_kieu_go', 'hay_DOI_kieu_go'])
    assert.equal((await t.call('POST', '/api/auth/login', {username: name, password: 'sai'})).statusCode, 401, name);
  assert.equal((await t.call('POST', '/api/auth/login', {username: 'hay_doi_kieu_go', password: 'matkhau123'})).statusCode, 429);
});
