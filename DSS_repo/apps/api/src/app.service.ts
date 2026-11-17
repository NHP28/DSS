import { BadRequestException, Injectable, Logger, ServiceUnavailableException } from '@nestjs/common';
import { RowDataPacket } from 'mysql2';
import { DatabaseService } from './database/database.service';
import { FeedbackDto, RecommendDto } from './dto';
import { ahp, Candidate, CRITERIA, haversine, PRESETS, topsis } from './dss';

@Injectable()
export class AppService {
  private readonly log = new Logger(AppService.name);
  constructor(private readonly db: DatabaseService) {}

  async health() {
    try {
      await this.db.query('SELECT 1 AS ok');
      let ai: unknown = {ready:false};
      try { const res = await fetch(`${process.env.AI_URL || 'http://127.0.0.1:8000'}/health`, {signal:AbortSignal.timeout(1500)}); if (res.ok) ai = await res.json(); } catch {}
      return {database:'connected', ai};
    } catch { throw new ServiceUnavailableException('Chưa kết nối MySQL. Kiểm tra .env và chạy npm run db:init.'); }
  }
  async catalog(category: string | undefined, limit: number) {
    return this.db.query(`SELECT * FROM pois ${category?'WHERE category = ?':''} ORDER BY id LIMIT ${limit}`, category?[category]:[]);
  }
  async users(limit: number) { return this.db.query(`SELECT id,display_name FROM users ORDER BY id LIMIT ${limit}`); }
  async stats() {
    const [rows] = await this.db.query('SELECT (SELECT COUNT(*) FROM pois) AS pois,(SELECT COUNT(*) FROM users) AS users,(SELECT COUNT(*) FROM checkins) AS checkins,(SELECT COUNT(*) FROM feedback) AS feedback');
    return {...rows, provenance:'POI từ OSM; check-in, giá, đánh giá và độ phổ biến dùng cho thực nghiệm mô phỏng.'};
  }
  async feedback(dto: FeedbackDto) {
    const users = await this.db.query('SELECT id FROM users WHERE id=?', [dto.userId]);
    const pois = await this.db.query('SELECT id FROM pois WHERE id=?', [dto.poiId]);
    if (!users.length || !pois.length) throw new BadRequestException('User hoặc POI không tồn tại');
    await this.db.execute('INSERT INTO feedback(user_id,poi_id,action) VALUES (?,?,?)', [dto.userId,dto.poiId,dto.action]);
    return {saved:true};
  }
  async recommend(dto: RecommendDto) {
    const start = performance.now();
    let weights = PRESETS[dto.preset], consistencyRatio = 0;
    if (dto.matrix) {
      try { ({weights,consistencyRatio} = ahp(dto.matrix)); }
      catch(error) { throw new BadRequestException((error as Error).message); }
    }
    const rows = await this.db.query<RowDataPacket & Candidate>('SELECT * FROM pois ORDER BY id');
    if (!rows.length) throw new ServiceUnavailableException('Chưa có dữ liệu. Chạy npm run db:init.');
    const visited = new Set<number>();
    if (dto.userId !== undefined) {
      const exists = await this.db.query('SELECT id FROM users WHERE id=?', [dto.userId]);
      if (!exists.length) throw new BadRequestException('User không tồn tại. Chọn Khách mới để dùng cold start.');
      if (dto.excludeVisited) {
        const history = await this.db.query('SELECT DISTINCT poi_id FROM checkins WHERE user_id=? UNION SELECT poi_id FROM feedback WHERE user_id=? AND action=\'visit\'', [dto.userId,dto.userId]);
        history.forEach(row=>visited.add(Number(row.poi_id)));
      }
    }
    let source = 'hourly_popularity', warning: string | null = null, smokeRun = false;
    let artifact: {runId?:string;seed?:number;selectedEpoch?:number;trainedUsers?:number;pois?:number} | null = null;
    const scores = new Map<number,number>();
    try {
      const res = await fetch(`${process.env.AI_URL || 'http://127.0.0.1:8000'}/score`, {
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({userId:dto.userId,hour:dto.hour,dayOfWeek:dto.dayOfWeek}),
        signal:AbortSignal.timeout(Number(process.env.AI_TIMEOUT_MS || 5000)),
      });
      if (!res.ok) throw new Error(`AI HTTP ${res.status}`);
      const data = await res.json() as {source:string;smokeRun?:boolean;artifact?:typeof artifact;datasetSha256:string;datasetSha256Aliases?:string[];scores:{poiId:number;score:number}[]};
      const [meta] = await this.db.query('SELECT sha256 FROM dataset_meta WHERE id=1');
      if (!meta || ![data.datasetSha256,...(data.datasetSha256Aliases || [])].includes(meta.sha256)) throw new Error('Artifact và catalog khác phiên bản dữ liệu');
      if (!['tas_gnn','lightgcn','hourly_popularity'].includes(data.source) || !Array.isArray(data.scores)) throw new Error('AI response không hợp lệ');
      const catalogIds = new Set(rows.map(p=>p.id));
      for (const item of data.scores) {
        if (!catalogIds.has(item.poiId) || scores.has(item.poiId) || !Number.isFinite(item.score) || item.score<0 || item.score>1) throw new Error('AI scores không hợp lệ');
        scores.set(item.poiId,item.score);
      }
      if (scores.size !== rows.length) throw new Error('Artifact thiếu POIs');
      source = data.source; smokeRun = !!data.smokeRun;
      artifact = data.artifact || null;
    } catch(error) {
      this.log.warn(`Using hourly fallback: ${(error as Error).message}`);
      scores.clear();
      warning = 'Mô hình AI chưa sẵn sàng hoặc artifact không khớp. Đang dùng độ phổ biến theo giờ từ dữ liệu mô phỏng.';
      const hourly = await this.db.query('SELECT poi_id,COUNT(*) AS count FROM checkins WHERE local_hour=? GROUP BY poi_id', [dto.hour]);
      const max = Math.max(1,...hourly.map(r=>Number(r.count)));
      hourly.forEach(row=>scores.set(Number(row.poi_id),Number(row.count)/max));
    }
    const candidates = rows.map(p=>({...p, distanceKm:haversine(dto.latitude,dto.longitude,p.latitude,p.longitude), preference:scores.get(p.id)||0}))
      .filter(p=>(!dto.category||p.category===dto.category) && p.distanceKm<=dto.radiusKm && (dto.maxPrice===undefined||p.price_avg<=dto.maxPrice) && !visited.has(p.id));
    // Rank within each category: hotel prices and cafe prices are not comparable.
    const groups = new Map<string,Candidate[]>();
    for (const p of candidates) groups.set(p.category,[...(groups.get(p.category)||[]),p]);
    const results = [...groups].map(([category,items])=>({category,total:items.length,items:topsis(items,weights).slice(0,dto.topK)}));
    return {source, warning, smokeRun, artifact, criteria:CRITERIA,weights,consistencyRatio, groups:results,
      totalCandidates:candidates.length, elapsedMs:Math.round(performance.now()-start),
      rankingScope:'within_category', dataProvenance:'synthetic_interactions', query:dto};
  }
}
