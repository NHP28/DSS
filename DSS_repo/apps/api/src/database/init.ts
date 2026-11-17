import 'dotenv/config';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { parse } from 'csv-parse/sync';
import { createConnection } from 'mysql2/promise';
import { databaseOptions } from './database.service';

async function main() {
  const db = await createConnection(databaseOptions());
  try {
    const schema = readFileSync(resolve(process.cwd(), 'src/database/schema.sql'), 'utf8');
    for (const statement of schema.split(';').filter(s => s.trim())) await db.query(statement);
    const dataDir = resolve(process.env.DATA_DIR || '../../data/danang');
    const poiBytes = readFileSync(resolve(dataDir, 'danang_pois_full.csv'));
    const eventBytes = readFileSync(resolve(dataDir, 'danang_checkins_full.csv'));
    const pois = parse(poiBytes, {columns: true, skip_empty_lines: true, bom: true}) as Record<string,string>[];
    const events = parse(eventBytes, {columns: true, skip_empty_lines: true, bom: true}) as Record<string,string>[];
    const sha = createHash('sha256').update(poiBytes).update(eventBytes).digest('hex');
    await db.beginTransaction();
    for (const user of new Set(events.map((e: any) => Number(e.u)))) {
      await db.execute('INSERT INTO users(id,display_name) VALUES (?,?) ON DUPLICATE KEY UPDATE display_name=VALUES(display_name)', [user, `Người dùng ${user}`]);
    }
    for (const p of pois) {
      await db.execute(`INSERT INTO pois(id,name,category,latitude,longitude,district,rating,price_avg,popularity) VALUES (?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE name=VALUES(name),category=VALUES(category),latitude=VALUES(latitude),longitude=VALUES(longitude),district=VALUES(district),rating=VALUES(rating),price_avg=VALUES(price_avg),popularity=VALUES(popularity)`,
        [Number(p.l),p.name,p.category,Number(p.lat),Number(p.lon),p.district,Number(p.rating),Number(p.price_avg),Number(p.popularity)]);
    }
    for (let start = 0; start < events.length; start += 1000) {
      const rows = events.slice(start, start + 1000).map((e: any) => [Number(e.u),Number(e.l),Number(e.ts),Number(e.hour),Number(e.day_of_week)]);
      await db.query('INSERT IGNORE INTO checkins(user_id,poi_id,timestamp_sec,local_hour,local_weekday) VALUES ?', [rows]);
    }
    await db.execute('INSERT INTO dataset_meta(id,sha256) VALUES (1,?) ON DUPLICATE KEY UPDATE sha256=VALUES(sha256)', [sha]);
    await db.commit();
    console.log(`Imported ${pois.length} POIs, ${events.length} events. Re-running preserves feedback.`);
  } catch (error) { await db.rollback(); throw error; }
  finally { await db.end(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
