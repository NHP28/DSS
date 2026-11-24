import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { Account } from './auth/auth.service';
import { FeedbackDto } from './dto';
import { GoogleService } from './google/google.service';
import { KgService } from './kg/kg.service';
import { Store } from './store';

@Injectable()
export class AppService {
  constructor(private readonly store: Store, private readonly kg: KgService, private readonly google: GoogleService) {}

  private async ai() {
    try {
      const res = await fetch(`${process.env.AI_URL || 'http://127.0.0.1:8000'}/health`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) return await res.json() as { ready: boolean; models?: string[]; origin?: string; info?: unknown; artifact?: unknown };
    } catch { /* reported as not ready */ }
    return { ready: false, models: [] as string[] };
  }

  async health() {
    try { await this.store.ping(); }
    catch { throw new ServiceUnavailableException('Chưa kết nối MySQL. Kiểm tra .env và chạy npm run db:init.'); }
    return { database: 'connected', ai: await this.ai() };
  }

  /** Which optional services are up; pages use it to explain disabled features. */
  async system() {
    const [ai, graph] = await Promise.all([this.ai(), this.kg.available()]);
    return { database: true, ai, graph, places: this.google.enabled };
  }

  async catalog(category: string | undefined, limit: number) {
    return (await this.store.pois()).filter(poi => !category || poi.category === category).slice(0, limit);
  }

  async stats() {
    return { ...(await this.store.stats()), provenance: 'POI từ OpenStreetMap; check-in, giá, đánh giá và độ phổ biến là dữ liệu mô phỏng.' };
  }

  async feedback(dto: FeedbackDto, account: Account) {
    if (!(await this.store.pois()).some(poi => poi.id === dto.poiId)) throw new BadRequestException('Địa điểm không tồn tại.');
    if (dto.action === 'like' || dto.action === 'visit') await this.store.addFeedback(account.id, dto.poiId, dto.action);
    else await this.store.removeFeedback(account.id, dto.poiId, dto.action === 'unlike' ? 'like' : 'visit');
    return { saved: true };
  }

  async saved(account: Account) {
    const [pois, feedback] = await Promise.all([this.store.pois(), this.store.feedback(account.id)]);
    const byId = new Map(pois.map(poi => [poi.id, poi]));
    const pick = (action: string) => feedback.filter(item => item.action === action).map(item => byId.get(item.poiId)).filter(Boolean);
    return { liked: pick('like'), visited: pick('visit') };
  }
}
