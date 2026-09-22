import { Injectable, Logger } from '@nestjs/common';
import { Place } from '../../../drizzle/schemas/places.schema';

export interface CprScoredResult {
  placeId: number;
  preferenceScore: number; // 0.00 -> 1.00 (Tiêu chí C4 cho TOPSIS)
  confidence: number;
  explanation: {
    summary: string;
    detail: string;
  };
}

@Injectable()
export class CprService {
  private readonly logger = new Logger(CprService.name);
  private readonly cprServiceUrl = process.env.CPR_AI_SERVICE_URL || 'http://localhost:8000';

  /**
   * Tính điểm sở thích cá nhân hóa (C4) dựa trên mô hình CPR (IJCAI 2020)
   * Tích hợp tự động Fallback nếu Python AI Service chưa chạy.
   */
  async getPreferenceScores(params: {
    userId?: number;
    hourOfDay?: number;
    userTags?: string[];
    candidates: Place[];
  }): Promise<Map<number, CprScoredResult>> {
    const resultMap = new Map<number, CprScoredResult>();
    const { userId, hourOfDay = new Date().getHours(), userTags = [], candidates } = params;

    if (!candidates || candidates.length === 0) {
      return resultMap;
    }

    try {
      // 1. Chuẩn bị payload gửi sang Python FastAPI CPR Service
      const payload = {
        userId: userId || null,
        hourOfDay,
        userTags,
        candidates: candidates.map((p) => ({
          id: p.id,
          name: p.name,
          latitude: Number(p.latitude),
          longitude: Number(p.longitude),
          categoryId: p.categoryId,
          tags: p.tags ? p.tags.split(',').map((t) => t.trim()) : [],
          rating: Number(p.rating),
          priceAvg: p.priceAvg,
          popularity: p.popularity,
        })),
      };

      // 2. Gọi HTTP POST sang FastAPI
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2s timeout

      const response = await fetch(`${this.cprServiceUrl}/api/cpr/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        for (const item of data.results) {
          resultMap.set(item.placeId, {
            placeId: item.placeId,
            preferenceScore: item.preferenceScore,
            confidence: item.confidence,
            explanation: item.explanation,
          });
        }
        return resultMap;
      }
    } catch (error) {
      this.logger.warn(
        `Không thể kết nối tới CPR AI Service (${this.cprServiceUrl}). Tự động kích hoạt cơ chế Fallback Heuristic.`,
      );
    }

    // 3. Fallback Heuristic (Nếu AI service offline hoặc lỗi)
    return this.calculateFallbackScores(candidates, hourOfDay, userTags);
  }

  /**
   * Thuật toán Fallback Heuristic dựa trên đặc trưng cục bộ khi AI Server offline
   */
  private calculateFallbackScores(
    candidates: Place[],
    hourOfDay: number,
    userTags: string[],
  ): Map<number, CprScoredResult> {
    const resultMap = new Map<number, CprScoredResult>();
    const userTagSet = new Set(userTags.map((t) => t.toLowerCase()));

    for (const p of candidates) {
      let temporalBoost = 0;
      if (p.categoryId === 1 && (hourOfDay <= 11 || (hourOfDay >= 14 && hourOfDay <= 17) || hourOfDay >= 19)) {
        temporalBoost = 0.15; // Cafe
      } else if (p.categoryId === 2 && ((hourOfDay >= 11 && hourOfDay <= 13) || (hourOfDay >= 18 && hourOfDay <= 21))) {
        temporalBoost = 0.20; // Restaurant
      }

      let tagMatch = 0;
      const placeTags = p.tags ? p.tags.split(',').map((t) => t.trim().toLowerCase()) : [];
      if (userTagSet.size > 0 && placeTags.length > 0) {
        const matches = placeTags.filter((t) => userTagSet.has(t));
        tagMatch = matches.length / userTagSet.size;
      }

      const ratingFactor = Number(p.rating) / 5.0;
      const popFactor = p.popularity / 100.0;

      const fallbackScore = Math.min(
        0.98,
        Math.max(0.2, Number((0.35 * ratingFactor + 0.25 * temporalBoost + 0.25 * tagMatch + 0.15 * popFactor).toFixed(4))),
      );

      resultMap.set(p.id, {
        placeId: p.id,
        preferenceScore: fallbackScore,
        confidence: 0.7,
        explanation: {
          summary: `Độ phù hợp cơ bản: ${Math.round(fallbackScore * 100)}%`,
          detail: `Đánh giá ${p.rating}★, phù hợp khung giờ ${hourOfDay}h`,
        },
      });
    }

    return resultMap;
  }
}
