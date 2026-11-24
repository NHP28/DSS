import { BadRequestException, Injectable, Logger, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { Account } from './auth/auth.service';
import { RecommendDto, ThemeRecommendDto } from './dto';
import { ahp, Candidate, CRITERIA, haversine, PRESETS, topsis } from './dss';
import { DEFAULT_SETTINGS, ModelSettings } from './settings/settings';
import { Poi, Store } from './store';
import { Theme, themeBySlug, THEMES } from './themes';

export const MIN_FOLDIN_HISTORY = 3;
const AI_SOURCES = ['tas_gnn', 'lightgcn', 'tas_gnn_foldin', 'lightgcn_foldin', 'hourly_popularity', 'popularity'];
type Artifact = { runId?: string; seed?: number | null; selectedEpoch?: number | null; trainedUsers?: number; pois?: number } | null;
type Extra = { cheapestShare?: number };

const vietnamNow = () => {
  const now = new Date(Date.now() + 7 * 3600 * 1000);
  return { hour: now.getUTCHours(), dayOfWeek: (now.getUTCDay() + 6) % 7 };
};

@Injectable()
export class RecommendService {
  private readonly log = new Logger(RecommendService.name);
  constructor(private readonly store: Store) {}

  async settingsFor(account: Account | null): Promise<ModelSettings> {
    return { ...DEFAULT_SETTINGS, ...(account ? await this.store.settings(account.id) || {} : {}) };
  }

  private weights(dto: RecommendDto, settings: ModelSettings) {
    const preset = dto.preset || settings.preset;
    const matrix = dto.matrix || (preset === 'custom' ? settings.weightLevels.map(a => settings.weightLevels.map(b => a / b)) : undefined);
    if (!matrix) return { weights: PRESETS[preset], consistencyRatio: 0 };
    try { return ahp(matrix); } catch (error) { throw new BadRequestException((error as Error).message); }
  }

  async recommend(dto: RecommendDto, account: Account | null, extra: Extra = {}) {
    const start = performance.now();
    const settings = await this.settingsFor(account);
    const { weights, consistencyRatio } = this.weights(dto, settings);
    const model = dto.model || settings.model, useTime = dto.useTime ?? settings.useTime;
    const topK = dto.topK ?? settings.topK, radiusKm = dto.radiusKm ?? settings.radiusKm;
    // An explicit null means "no limit" and overrides a saved budget; a missing field falls back to it.
    const maxPrice = (dto.maxPrice === null ? null : dto.maxPrice ?? settings.maxPrice) ?? undefined;
    const candidatePool = dto.candidatePool ?? settings.candidatePool;
    const excludeVisited = dto.excludeVisited ?? settings.excludeVisited;
    const categories = dto.categories?.length ? dto.categories : dto.category ? [dto.category] : undefined;

    const rows = await this.store.pois();
    if (!rows.length) throw new ServiceUnavailableException('Chưa có dữ liệu. Chạy npm run db:init.');
    const feedback = account ? await this.store.feedback(account.id) : [];
    const liked = new Set(feedback.filter(item => item.action === 'like').map(item => item.poiId));
    const visited = new Set(feedback.filter(item => item.action === 'visit').map(item => item.poiId));
    if (account?.datasetUserId != null) (await this.store.visitedByDatasetUser(account.datasetUserId)).forEach(id => visited.add(id));
    const history = [...new Set([...liked, ...feedback.filter(item => item.action === 'visit').map(item => item.poiId)])];

    let source = 'hourly_popularity', warning: string | null = null, artifact: Artifact = null, models: string[] = [];
    const scores = new Map<number, number>();
    try {
      const body = { hour: dto.hour, dayOfWeek: dto.dayOfWeek, model, useTime,
        ...(account?.datasetUserId != null ? { userId: account.datasetUserId }
          : history.length >= MIN_FOLDIN_HISTORY ? { historyPoiIds: history } : {}) };
      const res = await fetch(`${process.env.AI_URL || 'http://127.0.0.1:8000'}/score`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        signal: AbortSignal.timeout(Number(process.env.AI_TIMEOUT_MS || 5000)),
      });
      if (!res.ok) throw new Error(`AI HTTP ${res.status}`);
      const data = await res.json() as { source: string; models?: string[]; artifact?: Artifact; datasetSha256: string; datasetSha256Aliases?: string[]; scores: { poiId: number; score: number }[] };
      const sha = await this.store.datasetSha();
      if (!sha || ![data.datasetSha256, ...(data.datasetSha256Aliases || [])].includes(sha)) throw new Error('Model và catalog khác phiên bản dữ liệu');
      if (!AI_SOURCES.includes(data.source) || !Array.isArray(data.scores)) throw new Error('AI response không hợp lệ');
      const catalogIds = new Set(rows.map(p => p.id));
      for (const item of data.scores) {
        if (!catalogIds.has(item.poiId) || scores.has(item.poiId) || !Number.isFinite(item.score) || item.score < 0 || item.score > 1) throw new Error('AI scores không hợp lệ');
        scores.set(item.poiId, item.score);
      }
      if (scores.size !== rows.length) throw new Error('Model thiếu POIs');
      source = data.source; artifact = data.artifact || null; models = data.models || [];
    } catch (error) {
      this.log.warn(`Using hourly fallback: ${(error as Error).message}`);
      scores.clear(); source = 'hourly_popularity';
      warning = 'Dịch vụ mô hình chưa sẵn sàng. Đang xếp hạng theo độ phổ biến theo giờ từ dữ liệu mô phỏng.';
      const hourly = await this.store.hourlyCounts(dto.hour);
      const max = Math.max(1, ...hourly.values());
      hourly.forEach((count, id) => scores.set(id, count / max));
    }

    const candidates: (Candidate & { hidden: boolean })[] = rows
      .map((p: Poi) => ({ ...p, distanceKm: haversine(dto.latitude, dto.longitude, p.latitude, p.longitude), preference: scores.get(p.id) || 0 }))
      .filter(p => (!categories || categories.includes(p.category)) && (!dto.districts?.length || dto.districts.includes(p.district))
        && p.distanceKm <= radiusKm && (maxPrice === undefined || p.price_avg <= maxPrice)
        && !(excludeVisited && visited.has(p.id)) && (dto.showHidden || !p.hidden));

    // Rank within each category: hotel prices and cafe prices are not comparable.
    const grouped = new Map<string, Candidate[]>();
    for (const p of candidates) grouped.set(p.category, [...(grouped.get(p.category) || []), p]);
    let total = 0;
    const groups = [...grouped].map(([category, items]) => {
      if (extra.cheapestShare) items = [...items].sort((a, b) => a.price_avg - b.price_avg).slice(0, Math.max(1, Math.ceil(items.length * extra.cheapestShare)));
      total += items.length;
      // The GNN proposes, TOPSIS decides: keep the model's strongest candidates of this category.
      const pool = candidatePool > 0 ? [...items].sort((a, b) => b.preference - a.preference || a.id - b.id).slice(0, candidatePool) : items;
      return { category, total: items.length, items: topsis(pool, weights).slice(0, topK).map(item => ({ ...item, saved: liked.has(item.id), visited: visited.has(item.id) })) };
    });
    const personalization = source.endsWith('_foldin') ? 'foldin' : ['tas_gnn', 'lightgcn'].includes(source) ? 'trained_user' : 'cold_start';
    return { source, warning, smokeRun: false, artifact, models, model, useTime: useTime && source.startsWith('tas_gnn'),
      personalization, historyCount: history.length, minHistory: MIN_FOLDIN_HISTORY,
      criteria: CRITERIA, weights, consistencyRatio, groups, totalCandidates: total,
      elapsedMs: Math.round(performance.now() - start), rankingScope: 'within_category', dataProvenance: 'synthetic_interactions',
      query: { ...dto, topK, radiusKm, maxPrice: maxPrice ?? null, candidatePool, excludeVisited } };
  }

  private matches(theme: Theme, poi: Poi) {
    return theme.categories.includes(poi.category) && (!theme.districts || theme.districts.includes(poi.district))
      && (theme.maxPrice === undefined || poi.price_avg <= theme.maxPrice) && !poi.hidden;
  }

  async themes() {
    const pois = await this.store.pois();
    return THEMES.map(theme => {
      const count = pois.filter(poi => this.matches(theme, poi)).length;
      return { ...theme, count: theme.cheapestShare ? Math.ceil(count * theme.cheapestShare) : count };
    });
  }

  async themeRecommend(slug: string, dto: ThemeRecommendDto, account: Account | null) {
    const theme = themeBySlug(slug);
    if (!theme) throw new NotFoundException('Không có chủ đề này.');
    const now = vietnamNow(), settings = await this.settingsFor(account);
    const query = Object.assign(new RecommendDto(), {
      latitude: dto.latitude, longitude: dto.longitude,
      hour: dto.hour ?? (theme.hour === 'now' ? now.hour : theme.hour), dayOfWeek: dto.dayOfWeek ?? now.dayOfWeek,
      categories: theme.categories, districts: theme.districts,
      // Scenic spots sit outside the centre; a theme page should not come back empty by default.
      radiusKm: dto.radiusKm ?? Math.max(settings.radiusKm, 25),
      // A theme sets its own price rule; a saved personal budget would empty themes such as Lưu trú.
      maxPrice: theme.maxPrice ?? null,
      preset: settings.preset === 'custom' ? 'custom' : theme.preset,
    });
    return { theme, ...(await this.recommend(query, account, { cheapestShare: theme.cheapestShare })) };
  }
}
