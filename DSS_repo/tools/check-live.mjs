// Real HTTP + MySQL checks. Requires the local API, inference service and seeded DB.
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import {writeFileSync,mkdirSync} from 'node:fs';
import dotenv from 'dotenv';
import mysql from 'mysql2/promise';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
dotenv.config({path:resolve(root,'apps/api/.env'),quiet:true});
const base=process.env.TEST_API_URL||'http://127.0.0.1:4000/api';
const call=async(path,body)=>{
 const res=await fetch(`${base}/${path}`,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 const json=await res.json();assert.ok(res.ok,JSON.stringify(json));return json;
};
const checks=[];
const health=await call('health');assert.equal(health.database,'connected');assert.equal(health.ai.ready,true);checks.push('MySQL + Python inference ready');
const stats=await call('stats');assert.equal(Number(stats.pois),996);assert.equal(Number(stats.users),1500);assert.equal(Number(stats.checkins),36210);checks.push('Seed counts: 996 POIs / 1500 users / 36210 events');
const guest=await call('recommendations',{category:'cafe',radiusKm:10});assert.equal(guest.source,'hourly_popularity');assert.equal(guest.warning,null);assert.ok(guest.groups[0].items.length);checks.push('Cold start uses hourly fallback, with no random model');
const known=await call('recommendations',{userId:12,category:'cafe',radiusKm:10,maxPrice:100000});assert.equal(known.source,'tas_gnn');assert.equal(known.warning,null);assert.ok(known.groups[0].items.length);assert.ok(known.groups[0].items.every(p=>p.distanceKm<=10&&p.price_avg<=100000));checks.push('Trained TAS-GNN → NestJS → TOPSIS, budget and radius');
const priors=[.25,.2,.15,.3,.1];
const custom=await call('recommendations',{matrix:priors.map(a=>priors.map(b=>a/b)),category:'cafe'});assert.ok(custom.consistencyRatio<.1);checks.push('Custom AHP matrix validates through real HTTP');
const invalid=await fetch(`${base}/recommendations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hour:24})});assert.equal(invalid.status,400);checks.push('DTO validation through real HTTP');
const db=await mysql.createConnection({host:process.env.DB_HOST,port:Number(process.env.DB_PORT),user:process.env.DB_USER,password:process.env.DB_PASSWORD,database:process.env.DB_NAME});
try{
 const poi=known.groups[0].items[0];
 const [before]=await db.execute('SELECT COUNT(*) AS count FROM feedback WHERE user_id=? AND poi_id=? AND action=?',[12,poi.id,'like']);
 await call('feedback',{userId:12,poiId:poi.id,action:'like'});
 const [after]=await db.execute('SELECT COUNT(*) AS count FROM feedback WHERE user_id=? AND poi_id=? AND action=?',[12,poi.id,'like']);
 assert.equal(Number(after[0].count),Number(before[0].count)+1);checks.push('Feedback persisted and read back from real MySQL');
}finally{await db.end();}
const web=await fetch('http://127.0.0.1:3000');assert.equal(web.status,200);assert.match(await web.text(),/Hôm nay/);checks.push('Next.js production HTTP render');
const proxy=await fetch('http://127.0.0.1:3000/api/stats');assert.equal(proxy.status,200);assert.equal(Number((await proxy.json()).pois),996);checks.push('Next.js /api rewrite to NestJS');
mkdirSync(resolve(root,'outputs/qa'),{recursive:true});
writeFileSync(resolve(root,'outputs/qa/live-checks.json'),JSON.stringify({checks,stats,knownUserSource:known.source},null,2));
console.log(checks.map(x=>`PASS ${x}`).join('\n'));
