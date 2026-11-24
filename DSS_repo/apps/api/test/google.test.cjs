const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {createServer} = require('node:http');
const {mkdtempSync, writeFileSync} = require('node:fs');
const {tmpdir} = require('node:os');
const {join} = require('node:path');

// Stand-in for places.googleapis.com: records every request, never sees a real key.
const google = {requests: [], status: 200, photos: true};
const server = createServer((req, res) => {
  google.requests.push({url: req.url, key: req.headers['x-goog-api-key'], mask: req.headers['x-goog-fieldmask']});
  res.setHeader('Content-Type', 'application/json');
  res.statusCode = google.status;
  if (google.status !== 200) return res.end('{}');
  if (req.url.includes('/media')) return res.end(JSON.stringify({photoUri: 'https://lh3.googleusercontent.com/photo-a'}));
  res.end(JSON.stringify({rating: 4.3, userRatingCount: 1234, googleMapsUri: 'https://maps.google.com/?cid=1',
    photos: google.photos ? [{name: 'places/PLACE_A/photos/PHOTO_1', authorAttributions: [{displayName: 'Lan', uri: '//maps.google.com/maps/contrib/1'}]}] : []}));
});

let t;
before(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const file = join(mkdtempSync(join(tmpdir(), 'dss-google-')), 'ids.csv');
  writeFileSync(file, '﻿l,place_id,google_name,distance_m,similarity\n0,PLACE_A,Cà phê A,12,0.9\n1,,,,\n3,PLACE_C,Quán ăn,20,0.8\n4,PLACE_D,Nhà hàng,20,0.8\n');
  Object.assign(process.env, {GOOGLE_PLACE_IDS_FILE: file, GOOGLE_PLACES_API_KEY: 'test-key', GOOGLE_PLACES_URL: `http://127.0.0.1:${server.address().port}`, GOOGLE_PLACES_DAILY_LIMIT: '3'});
  t = await require('./helpers.cjs').startApp();
});
after(async () => { await t.close(); await new Promise(resolve => server.close(resolve)); });
const get = id => t.call('GET', `/api/pois/${id}/google`);

test('a matched place returns Google rating, photo and attribution without leaking the key', async () => {
  const res = await get(0);
  assert.equal(res.statusCode, 200, res.body);
  assert.deepEqual(res.json(), {available: true, rating: 4.3, ratingCount: 1234, mapsUrl: 'https://maps.google.com/?cid=1',
    photoUrl: 'https://lh3.googleusercontent.com/photo-a', photoAuthors: [{name: 'Lan', url: 'https://maps.google.com/maps/contrib/1'}]});
  assert.ok(!res.body.includes('test-key'));
  assert.equal(google.requests.length, 2);
  assert.equal(google.requests[0].key, 'test-key');
  assert.equal(google.requests[0].mask, 'rating,userRatingCount,googleMapsUri,photos');
  assert.match(google.requests[1].url, /^\/places\/PLACE_A\/photos\/PHOTO_1\/media\?maxWidthPx=480&skipHttpRedirect=true$/);
  assert.ok(!google.requests.some(r => r.url.includes('test-key')));
});

test('repeat views are served from memory, and unmatched places never call Google', async () => {
  const before = google.requests.length;
  await Promise.all([get(0), get(0), get(0)]);
  assert.deepEqual((await get(1)).json(), {available: false, reason: 'unmatched'});
  assert.deepEqual((await get(999)).json(), {available: false, reason: 'unmatched'});
  assert.equal(google.requests.length, before);
  assert.equal((await t.call('GET', '/api/pois/abc/google')).statusCode, 400);
});

test('a Google failure degrades to "no photo" instead of an error, and a place without photos still has a rating', async () => {
  google.status = 403;
  assert.deepEqual((await get(3)).json(), {available: false, reason: 'error'});
  google.status = 200; google.photos = false;
  const body = (await get(4)).json();
  assert.equal(body.rating, 4.3);
  assert.equal(body.photoUrl, null);
  assert.deepEqual(body.photoAuthors, []);
});

test('the daily ceiling stops further billable lookups, and the status endpoint reports the feature', async () => {
  const {GoogleService} = require('../dist/google/google.service');
  const service = t.app.get(GoogleService);
  service.cache.clear();
  const before = google.requests.length;
  assert.deepEqual((await get(0)).json(), {available: false, reason: 'limit'});
  assert.equal(google.requests.length, before);
  assert.equal((await t.call('GET', '/api/system')).json().places, true);
  delete process.env.GOOGLE_PLACES_API_KEY;
  assert.deepEqual((await get(0)).json(), {available: false, reason: 'disabled'});
  assert.equal((await t.call('GET', '/api/system')).json().places, false);
});
