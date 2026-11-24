import 'dotenv/config';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { parse } from 'csv-parse/sync';
import { createConnection } from 'mysql2/promise';
import { hashPassword } from '../auth/password';
import { databaseOptions } from './database.service';
import { isJunkPoiName, normalizeDistrict } from './display';

type Csv = Record<string, string>;
const DEMO = [
  { username: 'demo_cafe', displayName: 'Lan · mê cà phê', category: 'cafe', interests: ['ca-phe', 'bua-sang'] },
  { username: 'demo_amthuc', displayName: 'Minh · sành ăn', category: 'restaurant', interests: ['an-uong', 've-dem'] },
  { username: 'demo_thamquan', displayName: 'Hà · thích khám phá', category: 'tourist_spot', interests: ['tham-quan-giai-tri', 'ven-bien'] },
  { username: 'demo_dadang', displayName: 'Quân · đi đủ nơi', category: null, interests: ['an-uong', 'ca-phe', 'tham-quan-giai-tri'] },
];

/** Dataset users whose history best shows each taste, so the demo accounts visibly differ. */
export function demoUsers(pois: Csv[], events: Csv[]) {
  const category = new Map(pois.map(p => [p.l, p.category]));
  const counts = new Map<number, Record<string, number>>();
  for (const e of events) {
    const row = counts.get(Number(e.u)) || {};
    const key = category.get(e.l) || 'other';
    row[key] = (row[key] || 0) + 1;
    counts.set(Number(e.u), row);
  }
  const taken = new Set<number>();
  return DEMO.map(demo => {
    let best = -1, bestScore = -Infinity;
    for (const [user, row] of counts) {
      if (taken.has(user)) continue;
      const total = Object.values(row).reduce((s, x) => s + x, 0);
      if (total < 20) continue;
      // A focused taste: many visits concentrated in one category. The eclectic account: the most even spread.
      const own = demo.category ? row[demo.category] || 0 : 0;
      const score = demo.category ? own * own / total : -Object.values(row).reduce((s, x) => s + (x / total) ** 2, 0) + total / 10000;
      if (score > bestScore || (score === bestScore && user < best)) { best = user; bestScore = score; }
    }
    taken.add(best);
    return { ...demo, datasetUserId: best };
  });
}

async function main() {
  const db = await createConnection(databaseOptions());
  try {
    const schema = readFileSync(resolve(process.cwd(), 'src/database/schema.sql'), 'utf8');
    for (const statement of schema.split(';').filter(s => s.trim())) await db.query(statement);
    const dataDir = resolve(process.env.DATA_DIR || '../../data/danang');
    const poiBytes = readFileSync(resolve(dataDir, 'danang_pois_full.csv'));
    const eventBytes = readFileSync(resolve(dataDir, 'danang_checkins_full.csv'));
    const pois = parse(poiBytes, {columns: true, skip_empty_lines: true, bom: true}) as Csv[];
    const events = parse(eventBytes, {columns: true, skip_empty_lines: true, bom: true}) as Csv[];
    const sha = createHash('sha256').update(poiBytes).update(eventBytes).digest('hex');
    await db.beginTransaction();
    for (const user of new Set(events.map(e => Number(e.u)))) {
      await db.execute('INSERT INTO users(id,display_name) VALUES (?,?) ON DUPLICATE KEY UPDATE display_name=VALUES(display_name)', [user, `Người dùng ${user}`]);
    }
    let hidden = 0;
    for (const p of pois) {
      // District spellings are unified for display; the CSV itself is never modified.
      await db.execute(`INSERT INTO pois(id,name,category,latitude,longitude,district,rating,price_avg,popularity) VALUES (?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE name=VALUES(name),category=VALUES(category),latitude=VALUES(latitude),longitude=VALUES(longitude),district=VALUES(district),rating=VALUES(rating),price_avg=VALUES(price_avg),popularity=VALUES(popularity)`,
        [Number(p.l),p.name,p.category,Number(p.lat),Number(p.lon),normalizeDistrict(p.district),Number(p.rating),Number(p.price_avg),Number(p.popularity)]);
      const junk = isJunkPoiName(p.name, p.category);
      if (junk) hidden++;
      await db.execute('INSERT INTO poi_display(poi_id,hidden) VALUES (?,?) ON DUPLICATE KEY UPDATE hidden=VALUES(hidden)', [Number(p.l), junk ? 1 : 0]);
    }
    for (let start = 0; start < events.length; start += 1000) {
      const rows = events.slice(start, start + 1000).map(e => [Number(e.u),Number(e.l),Number(e.ts),Number(e.hour),Number(e.day_of_week)]);
      await db.query('INSERT IGNORE INTO checkins(user_id,poi_id,timestamp_sec,local_hour,local_weekday) VALUES ?', [rows]);
    }
    await db.execute('INSERT INTO dataset_meta(id,sha256) VALUES (1,?) ON DUPLICATE KEY UPDATE sha256=VALUES(sha256)', [sha]);

    const demoPassword = process.env.DEMO_PASSWORD;
    if (demoPassword && demoPassword.length >= 8) {
      for (const demo of demoUsers(pois, events)) {
        const hash = await hashPassword(demoPassword);
        await db.execute('INSERT INTO accounts(username,display_name,password_hash,dataset_user_id) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE display_name=VALUES(display_name),password_hash=VALUES(password_hash),dataset_user_id=VALUES(dataset_user_id)',
          [demo.username, demo.displayName, hash, demo.datasetUserId]);
        const [found] = await db.query('SELECT id FROM accounts WHERE username=?', [demo.username]);
        const accountId = (found as {id: number}[])[0].id;
        for (const theme of demo.interests) await db.execute('INSERT IGNORE INTO account_interests(account_id,theme) VALUES (?,?)', [accountId, theme]);
        console.log(`Demo account ${demo.username} -> dataset user ${demo.datasetUserId}`);
      }
    } else console.log('DEMO_PASSWORD chưa đặt (tối thiểu 8 ký tự): bỏ qua tài khoản demo.');
    await db.commit();
    console.log(`Imported ${pois.length} POIs (${hidden} ẩn khỏi trang chủ đề), ${events.length} events. Re-running preserves accounts and feedback.`);
  } catch (error) { await db.rollback(); throw error; }
  finally { await db.end(); }
}
if (require.main === module) main().catch(error => { console.error(error.message); process.exitCode = 1; });
