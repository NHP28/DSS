import { Inject, Injectable, OnModuleDestroy, ServiceUnavailableException } from '@nestjs/common';
import neo4j, { Driver } from 'neo4j-driver';

export const NEO4J_DRIVER = 'NEO4J_DRIVER';
export const createDriver = (): Driver => neo4j.driver(
  process.env.NEO4J_URI || 'bolt://127.0.0.1:7687',
  neo4j.auth.basic(process.env.NEO4J_USER || 'neo4j', process.env.NEO4J_PASSWORD || 'neo4j_local_password'),
  { disableLosslessIntegers: true, connectionTimeout: 3000, connectionAcquisitionTimeout: 3000, maxTransactionRetryTime: 0 });

export const TIME_SLOTS = [
  { key: 'morning', label: 'Buổi sáng (5–10h)' }, { key: 'noon', label: 'Buổi trưa (11–13h)' },
  { key: 'afternoon', label: 'Buổi chiều (14–17h)' }, { key: 'evening', label: 'Buổi tối (18–22h)' },
  { key: 'night', label: 'Đêm khuya (23–4h)' },
];
export const timeSlot = (hour: number) => hour >= 5 && hour <= 10 ? 'morning' : hour <= 13 && hour >= 11 ? 'noon'
  : hour >= 14 && hour <= 17 ? 'afternoon' : hour >= 18 && hour <= 22 ? 'evening' : 'night';

type Row = Record<string, any>;
export interface GraphNode { id: string; label: string; type: string; weight?: number }
export interface GraphLink { source: string; target: string; type: string; value?: number }

const NEIGHBOURHOOD = `MATCH (p:POI {id: $id})
OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)
OPTIONAL MATCH (p)-[b:BUSY_AT]->(t:TimeSlot)
OPTIONAL MATCH (p)-[n:NEAR]->(q:POI)
RETURN p, c, d, collect(DISTINCT {slot: t.key, label: t.label, count: b.count}) AS busy,
       collect(DISTINCT {id: q.id, name: q.name, km: n.km}) AS near`;
const SIMILAR = `MATCH (p:POI {id: $id})<-[:VISITED]-(u:User)-[:VISITED]->(q:POI)
WHERE q <> p
RETURN q.id AS id, q.name AS name, q.category AS category, count(DISTINCT u) AS sharedVisitors
ORDER BY sharedVisitors DESC, id LIMIT toInteger($limit)`;

@Injectable()
export class KgService implements OnModuleDestroy {
  constructor(@Inject(NEO4J_DRIVER) private readonly driver: Driver) {}
  async onModuleDestroy() { await this.driver.close?.(); }

  private async read(query: string, params: Row = {}): Promise<Row[]> {
    const session = this.driver.session({ defaultAccessMode: 'READ' });
    try {
      const result = await session.run(query, params, { timeout: 3000 });
      return result.records.map(record => record.toObject());
    } catch (error) {
      throw new ServiceUnavailableException(`Neo4j chưa sẵn sàng: ${(error as Error).message}. Bật Docker và chạy python tools/build_kg.py.`);
    } finally { await session.close(); }
  }

  async available(): Promise<boolean> {
    try { await this.read('RETURN 1 AS ok'); return true; } catch { return false; }
  }

  async stats() {
    const nodes = await this.read('MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count');
    const relationships = await this.read('MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count');
    return { nodes: Object.fromEntries(nodes.map(row => [row.label, row.count])),
      relationships: Object.fromEntries(relationships.map(row => [row.type, row.count])) };
  }

  similar(id: number, limit = 8) { return this.read(SIMILAR, { id, limit }); }

  async neighbourhood(id: number) {
    const [row] = await this.read(NEIGHBOURHOOD, { id });
    if (!row?.p) return null;
    const poi = row.p.properties, centre = `poi:${id}`;
    const nodes: GraphNode[] = [{ id: centre, label: poi.name, type: 'POI', weight: 3 }];
    const links: GraphLink[] = [];
    if (row.c) { nodes.push({ id: `cat:${row.c.properties.key}`, label: row.c.properties.label, type: 'Category' }); links.push({ source: centre, target: `cat:${row.c.properties.key}`, type: 'IN_CATEGORY' }); }
    if (row.d) { nodes.push({ id: `dist:${row.d.properties.name}`, label: row.d.properties.name, type: 'District' }); links.push({ source: centre, target: `dist:${row.d.properties.name}`, type: 'LOCATED_IN' }); }
    for (const slot of (row.busy as Row[]).filter(item => item.slot)) {
      nodes.push({ id: `slot:${slot.slot}`, label: slot.label, type: 'TimeSlot' });
      links.push({ source: centre, target: `slot:${slot.slot}`, type: 'BUSY_AT', value: slot.count });
    }
    for (const near of (row.near as Row[]).filter(item => item.id !== null && item.id !== undefined)) {
      nodes.push({ id: `poi:${near.id}`, label: near.name, type: 'POI' });
      links.push({ source: centre, target: `poi:${near.id}`, type: 'NEAR', value: Number(Number(near.km).toFixed(2)) });
    }
    const similar = await this.similar(id, 6);
    for (const item of similar) {
      if (!nodes.some(node => node.id === `poi:${item.id}`)) nodes.push({ id: `poi:${item.id}`, label: item.name, type: 'POI' });
      links.push({ source: centre, target: `poi:${item.id}`, type: 'CO_VISITED', value: item.sharedVisitors });
    }
    return { poi: { id, name: poi.name, rating: poi.rating, priceAvg: poi.price_avg }, nodes, links, cypher: NEIGHBOURHOOD.replace('$id', String(id)) };
  }

  /** Graph-path reasons for one recommendation. `anchors` are POIs the account liked or visited. */
  async explain(id: number, anchors: number[], hour: number) {
    const slot = timeSlot(hour);
    const [row] = await this.read(`MATCH (p:POI {id: $id})
OPTIONAL MATCH (p)-[:LOCATED_IN]->(d:District)
OPTIONAL MATCH (p)-[b:BUSY_AT]->(t:TimeSlot {key: $slot})
OPTIONAL MATCH (p)<-[:VISITED]-(v:User)
RETURN p.name AS name, d.name AS district, b.share AS share, t.label AS slotLabel, count(DISTINCT v) AS visitors`, { id, slot });
    if (!row?.name) return null;
    const reasons: { kind: string; text: string }[] = [];
    if (anchors.length) {
      const [near] = await this.read(`MATCH (p:POI {id: $id})-[n:NEAR]-(q:POI) WHERE q.id IN $anchors
RETURN q.name AS name, n.km AS km ORDER BY km LIMIT 1`, { id, anchors });
      if (near) reasons.push({ kind: 'near_liked', text: `Cách ${near.name} — nơi bạn đã chọn — khoảng ${Number(near.km) < 0.95 ? `${Math.max(10, Math.round(Number(near.km) * 100) * 10)} m` : `${Number(near.km).toFixed(1)} km`}.` });
      const [shared] = await this.read(`MATCH (q:POI)<-[:VISITED]-(u:User)-[:VISITED]->(p:POI {id: $id}) WHERE q.id IN $anchors AND q <> p
RETURN count(DISTINCT u) AS users`, { id, anchors });
      if (shared?.users > 0) reasons.push({ kind: 'co_visited', text: `${shared.users} người từng ghé những nơi bạn đã chọn cũng ghé nơi này.` });
    }
    if (row.share > 0) reasons.push({ kind: 'busy_slot', text: `${Math.round(row.share * 100)}% lượt ghé nơi này rơi vào ${String(row.slotLabel).toLowerCase()}.` });
    if (row.visitors > 0) reasons.push({ kind: 'visitors', text: `${row.visitors} người trong dữ liệu đã ghé nơi này.` });
    if (row.district) reasons.push({ kind: 'district', text: `Thuộc quận ${row.district}.` });
    return { poiId: id, name: row.name, slot, reasons };
  }
}
