require('reflect-metadata');
const {createServer} = require('node:http');
const {NestFactory} = require('@nestjs/core');
const {Module, ValidationPipe} = require('@nestjs/common');
const {FastifyAdapter} = require('@nestjs/platform-fastify');
const {controllers, services} = require('../dist/app.module');
const {Store} = require('../dist/store');
const {NEO4J_DRIVER} = require('../dist/kg/kg.service');

process.env.AUTH_SECRET = 'test-secret-test-secret-test-secret-0123';

const catalog = () => [
  {id:0,name:'Cà phê A',category:'cafe',district:'Hải Châu',latitude:16.06,longitude:108.22,rating:4.5,price_avg:30000,popularity:80,hidden:false},
  {id:1,name:'Cà phê B',category:'cafe',district:'Sơn Trà',latitude:16.07,longitude:108.23,rating:4,price_avg:60000,popularity:60,hidden:false},
  {id:2,name:'Khách sạn',category:'hotel',district:'Sơn Trà',latitude:16.07,longitude:108.24,rating:4,price_avg:900000,popularity:60,hidden:false},
  {id:3,name:'Quán ăn',category:'restaurant',district:'Hải Châu',latitude:16.065,longitude:108.221,rating:4.2,price_avg:50000,popularity:70,hidden:false},
  {id:4,name:'Nhà hàng',category:'restaurant',district:'Ngũ Hành Sơn',latitude:16.03,longitude:108.25,rating:4.6,price_avg:250000,popularity:75,hidden:false},
  {id:5,name:'End of the Road?',category:'tourist_spot',district:'Sơn Trà',latitude:16.1,longitude:108.27,rating:4.1,price_avg:0,popularity:20,hidden:true},
  {id:6,name:'Chùa Linh Ứng',category:'tourist_spot',district:'Sơn Trà',latitude:16.1,longitude:108.277,rating:4.8,price_avg:0,popularity:95,hidden:false},
];

/** In-memory stand-in for Store: same methods, no SQL. */
function fakeStore() {
  const state = {pois:catalog(), accounts:[], settings:new Map(), feedback:[], sha:'abc', datasetVisits:{12:[0]}};
  return {state,
    async ping() {},
    async pois() { return state.pois; },
    async stats() { return {pois:state.pois.length,users:1500,checkins:36210,accounts:state.accounts.length}; },
    async datasetSha() { return state.sha; },
    async hourlyCounts() { return new Map([[0,4],[1,2],[2,1],[3,3]]); },
    async visitedByDatasetUser(id) { return state.datasetVisits[id] || []; },
    async accountByUsername(username) { return state.accounts.find(a=>a.username===username) || null; },
    async accountById(id) { return state.accounts.find(a=>a.id===id) || null; },
    async createAccount(input) {
      if (state.accounts.some(a=>a.username===input.username)) return null;
      const account = {id:state.accounts.length+1, datasetUserId:input.datasetUserId ?? null, ...input};
      state.accounts.push(account);
      return account;
    },
    async demoAccounts() { return state.accounts.filter(a=>a.datasetUserId!==null).map(a=>({username:a.username,displayName:a.displayName})); },
    async settings(id) { return state.settings.get(id) || null; },
    async saveSettings(id, value) { state.settings.set(id, value); },
    async deleteSettings(id) { state.settings.delete(id); },
    async feedback(id) { return state.feedback.filter(f=>f.accountId===id).map(({poiId,action})=>({poiId,action})); },
    async addFeedback(accountId, poiId, action) {
      if (!state.feedback.some(f=>f.accountId===accountId&&f.poiId===poiId&&f.action===action)) state.feedback.push({accountId,poiId,action});
    },
    async removeFeedback(accountId, poiId, action) {
      state.feedback = state.feedback.filter(f=>!(f.accountId===accountId&&f.poiId===poiId&&f.action===action));
    },
  };
}

/** Neo4j driver double: `handler(query, params)` returns plain rows or throws. */
function fakeDriver(handler) {
  return {
    session: () => ({
      async run(query, params) { return {records:(await handler(query, params)).map(row=>({toObject:()=>row}))}; },
      async close() {},
    }),
    async close() {},
  };
}

/** Starts the API against fakes plus a stub AI server. `ai.mode`: ok | down | mismatch; `ai.requests` records bodies. */
async function startApp({graph} = {}) {
  const store = fakeStore();
  const ai = {mode:'ok', requests:[], source:null};
  const server = createServer((req, res) => {
    let raw = '';
    req.on('data', chunk => raw += chunk);
    req.on('end', () => {
      const body = raw ? JSON.parse(raw) : {};
      if (req.url === '/score') ai.requests.push(body);
      res.setHeader('Content-Type', 'application/json');
      res.statusCode = ai.mode === 'down' ? 503 : 200;
      if (req.url === '/health') return res.end(JSON.stringify({ready:true,models:['tas_gnn','lightgcn'],origin:'repo_checkpoint'}));
      const source = ai.source || (body.userId !== undefined ? body.model : body.historyPoiIds ? `${body.model}_foldin` : 'hourly_popularity');
      res.end(JSON.stringify({source, models:['tas_gnn','lightgcn'], datasetSha256:ai.mode==='mismatch'?'wrong':'lf_hash', datasetSha256Aliases:ai.mode==='mismatch'?[]:['abc'],
        scores:store.state.pois.map(p=>({poiId:p.id,score:(p.id+1)/10}))}));
    });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  process.env.AI_URL = `http://127.0.0.1:${server.address().port}`;
  class TestModule {}
  Module({controllers, providers:[...services, {provide:Store,useValue:store},
    {provide:NEO4J_DRIVER,useValue:fakeDriver(graph || (async()=>{ throw new Error('connect ECONNREFUSED'); }))}]})(TestModule);
  const app = await NestFactory.create(TestModule, new FastifyAdapter(), {logger:false});
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  await app.init();
  await app.getHttpAdapter().getInstance().ready();
  const call = (method, url, payload, cookie) => app.inject({method, url, payload, headers:cookie?{cookie}:{}});
  const cookieOf = response => String(response.headers['set-cookie']).split(';')[0];
  const register = async (username, extra = {}) => {
    const response = await call('POST', '/api/auth/register', {username, displayName:'Người thử', password:'matkhau123', interests:['ca-phe'], ...extra});
    return {response, cookie:cookieOf(response)};
  };
  return {app, store, ai, call, cookieOf, register,
    async close() { await app.close(); await new Promise(resolve => server.close(resolve)); }};
}

module.exports = {startApp, fakeDriver};
