require('reflect-metadata');
const {test,before,after} = require('node:test');
const assert = require('node:assert/strict');
const {createServer} = require('node:http');
const {NestFactory} = require('@nestjs/core');
const {Module,ValidationPipe} = require('@nestjs/common');
const {FastifyAdapter} = require('@nestjs/platform-fastify');
const {AppController} = require('../dist/app.controller');
const {AppService} = require('../dist/app.service');
const {DatabaseService} = require('../dist/database/database.service');

const catalog=[
  {id:0,name:'Cà phê A',category:'cafe',district:'Hải Châu',latitude:16.06,longitude:108.22,rating:4.5,price_avg:30000,popularity:80},
  {id:1,name:'Cà phê B',category:'cafe',district:'Sơn Trà',latitude:16.07,longitude:108.23,rating:4,price_avg:60000,popularity:60},
  {id:2,name:'Khách sạn',category:'hotel',district:'Sơn Trà',latitude:16.07,longitude:108.24,rating:4,price_avg:900000,popularity:60},
];
const feedback=[];
const fakeDb={
  async query(sql,args=[]){
    if(sql.startsWith('SELECT * FROM pois')) return catalog;
    if(sql.startsWith('SELECT id FROM users'))return args[0]===12?[{id:12}]:[];
    if(sql.startsWith('SELECT id FROM pois'))return catalog.filter(p=>p.id===args[0]);
    if(sql.includes('SELECT DISTINCT poi_id'))return [{poi_id:0},...feedback.filter(x=>x[2]==='visit').map(x=>({poi_id:x[1]}))];
    if(sql.includes('GROUP BY poi_id'))return [{poi_id:0,count:4},{poi_id:1,count:2},{poi_id:2,count:1}];
    if(sql.includes('FROM dataset_meta'))return [{sha256:'abc'}];
    return [];
  },
  async execute(sql,args){feedback.push(args);}
};
let app,server,aiMode='ok';
before(async()=>{
  server=createServer((req,res)=>{
    res.setHeader('Content-Type','application/json');
    res.statusCode=aiMode==='down'?503:200;
    res.end(JSON.stringify({source:'tas_gnn',smokeRun:false,datasetSha256:aiMode==='mismatch'?'wrong':aiMode==='newline_alias'?'lf_hash':'abc',datasetSha256Aliases:aiMode==='newline_alias'?['abc']:[],scores:catalog.map(p=>({poiId:p.id,score:1-p.id*.2}))}));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  process.env.AI_URL=`http://127.0.0.1:${server.address().port}`;
  class TestModule{}
  Module({controllers:[AppController],providers:[AppService,{provide:DatabaseService,useValue:fakeDb}]})(TestModule);
  app=await NestFactory.create(TestModule,new FastifyAdapter(),{logger:false});
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  await app.init();await app.getHttpAdapter().getInstance().ready();
});
after(async()=>{await app?.close();await new Promise(resolve=>server.close(resolve));});
const post=(url,payload)=>app.inject({method:'POST',url,payload});
test('HTTP DTO rejects invalid coordinates, time, topK and extra properties',async()=>{
  for(const payload of [{hour:24},{latitude:100},{topK:0},{radiusKm:-1},{userId:'12'},{unknown:1},{matrix:[[null]]}]) {
    const res=await post('/api/recommendations',payload);assert.equal(res.statusCode,400,res.body);
  }
});
test('AI scores, per-category ranking, budget/radius filters and history masking',async()=>{
  aiMode='ok';
  const res=await post('/api/recommendations',{userId:12,radiusKm:10,maxPrice:100000});
  assert.equal(res.statusCode,201,res.body);
  const body=res.json();assert.equal(body.source,'tas_gnn');assert.equal(body.warning,null);
  assert.equal(body.groups.length,1);assert.deepEqual(body.groups[0].items.map(p=>p.id),[1]);
  assert.equal(body.rankingScope,'within_category');
  const empty=await post('/api/recommendations',{latitude:0,longitude:0,radiusKm:1});
  assert.equal(empty.json().totalCandidates,0);
});
test('cold start and explicit fallback on unavailable or mismatched artifact',async()=>{
  for(const mode of ['down','mismatch']) {
    aiMode=mode;
    const res=await post('/api/recommendations',{category:'cafe'});
    assert.equal(res.statusCode,201,res.body);const body=res.json();
    assert.equal(body.source,'hourly_popularity');assert.ok(body.warning);assert.equal(body.groups[0].total,2);
  }
  const badUser=await post('/api/recommendations',{userId:99});assert.equal(badUser.statusCode,400);
});
test('Colab LF artifact matches the same Windows CRLF dataset through verified hash aliases',async()=>{
  aiMode='newline_alias';
  const res=await post('/api/recommendations',{category:'cafe'});
  assert.equal(res.statusCode,201,res.body);
  assert.equal(res.json().source,'tas_gnn');assert.equal(res.json().warning,null);
});
test('feedback validates foreign IDs and persists valid action',async()=>{
  const saved=await post('/api/feedback',{userId:12,poiId:1,action:'visit'});
  assert.equal(saved.statusCode,201);assert.equal(saved.json().saved,true);assert.deepEqual(feedback[0],[12,1,'visit']);
  assert.equal((await post('/api/feedback',{userId:99,poiId:1,action:'like'})).statusCode,400);
});
