import { Injectable, NotFoundException } from '@nestjs/common';
import { DrizzleService } from '../../drizzle/drizzle.service';
import { places, Place } from '../../drizzle/schemas/places.schema';
import { recommendations, NewRecommendation } from '../../drizzle/schemas/recommendations.schema';
import { DssService } from '../dss/dss.service';
import { CprService } from '../dss/cpr/cpr.service';
import { RecommendQueryDto } from './dto/recommend-query.dto';
import { RecalculateWeightsDto } from './dto/recalculate-weights.dto';
import { AlternativeInput, TopsisRankedItem } from '../dss/topsis/topsis.service';
import { calculateHaversineDistance, getBoundingBox } from '../../common/utils/spatial.util';
import { and, eq, gte, lte, like, sql } from 'drizzle-orm';
import { randomUUID } from 'crypto';

@Injectable()
export class RecommendationService {
  constructor(
    private readonly drizzle: DrizzleService,
    private readonly dssService: DssService,
    private readonly cprService: CprService,
  ) {}

  /**
   * Đánh giá và đề xuất địa điểm tối ưu theo mô hình kết hợp CPR (IJCAI 2020) + AHP + TOPSIS
   */
  async getRecommendations(dto: RecommendQueryDto) {
    const {
      lat,
      lng,
      radiusKm = 5,
      categoryId,
      district,
      topK = 10,
      userId,
      hourOfDay,
      userTags,
      allDanang = false,
    } = dto;

    // 1. Tìm các địa điểm ứng viên
    const conditions: any[] = [];
    if (categoryId) {
      conditions.push(eq(places.categoryId, categoryId));
    }
    if (district) {
      conditions.push(like(places.district, `%${district}%`));
    }

    // Nếu không chọn allDanang thì lọc theo Bounding Box
    if (!allDanang && radiusKm > 0) {
      const bbox = getBoundingBox(lat, lng, radiusKm);
      conditions.push(
        gte(places.latitude, String(bbox.minLat)),
        lte(places.latitude, String(bbox.maxLat)),
        gte(places.longitude, String(bbox.minLng)),
        lte(places.longitude, String(bbox.maxLng)),
      );
    }

    const candidates = await this.drizzle
      .select()
      .from(places)
      .where(conditions.length > 0 ? and(...conditions) : undefined);

    if (candidates.length === 0) {
      return {
        sessionId: randomUUID(),
        totalCandidates: 0,
        recommendations: [],
        weights: dto.weights || {
          distance: 0.3,
          rating: 0.25,
          price: 0.2,
          preference: 0.15,
          popularity: 0.1,
        },
        message: 'Không tìm thấy địa điểm nào phù hợp tại Đà Nẵng',
      };
    }

    // 2. Tính khoảng cách Haversine (nếu allDanang = true thì lấy tất cả, ngược lại lọc theo radiusKm)
    const inRadiusPlaces: Place[] = [];
    const distances = new Map<number, number>();

    for (const p of candidates) {
      const pLat = Number(p.latitude);
      const pLng = Number(p.longitude);
      const dist = calculateHaversineDistance(lat, lng, pLat, pLng);

      if (allDanang || dist <= radiusKm) {
        inRadiusPlaces.push(p);
        distances.set(p.id, dist);
      }
    }

    if (inRadiusPlaces.length === 0) {
      return {
        sessionId: randomUUID(),
        totalCandidates: 0,
        recommendations: [],
        message: 'Không có địa điểm nào nằm trong phạm vi đã chọn',
      };
    }

    // 3. Gọi mô hình AI CPR (IJCAI 2020) để tính điểm Preference C4 theo ngữ cảnh
    const cprScoreMap = await this.cprService.getPreferenceScores({
      userId,
      hourOfDay: hourOfDay !== undefined ? hourOfDay : new Date().getHours(),
      userTags,
      candidates: inRadiusPlaces,
    });

    const alternatives: AlternativeInput[] = inRadiusPlaces.map((p) => {
      const dist = distances.get(p.id) || 0;
      const cprInfo = cprScoreMap.get(p.id);
      const preferenceScore = cprInfo ? cprInfo.preferenceScore : Number(p.matchPreference);

      return {
        id: p.id,
        name: p.name,
        address: p.address,
        district: p.district,
        ward: p.ward,
        latitude: Number(p.latitude),
        longitude: Number(p.longitude),
        imageUrl: p.imageUrl,
        openingHours: p.openingHours,
        phoneNumber: p.phoneNumber,
        categoryName: p.categoryId === 1 ? 'Cafe' : p.categoryId === 2 ? 'Nhà hàng' : p.categoryId === 3 ? 'Khách sạn' : 'Điểm du lịch',
        distance: dist, // C1 (Cost)
        rating: Number(p.rating), // C2 (Benefit)
        price: p.priceAvg, // C3 (Cost)
        preference: preferenceScore, // C4 (Benefit - Tính từ CPR Model)
        popularity: p.popularity, // C5 (Benefit)
        tags: p.tags ? p.tags.split(',').map((t) => t.trim()) : [],
        explanation: cprInfo?.explanation || {
          summary: `Điểm phù hợp: ${Math.round(preferenceScore * 100)}%`,
          detail: `Đánh giá ${p.rating}★`,
        },
      };
    });

    // 4. Thực thi thuật toán DSS (AHP + TOPSIS)
    const dssResult = this.dssService.processEvaluation(alternatives, {
      ahpMatrix: dto.ahpMatrix?.matrix,
      directWeights: dto.weights,
    });

    const sessionId = randomUUID();
    const rankedPlaces = dssResult.topsisResult.rankedItems;
    const topResults = rankedPlaces.slice(0, topK);

    // 5. Lưu kết quả xếp hạng vào database MySQL để theo dõi lịch sử
    try {
      const recordsToInsert: NewRecommendation[] = topResults.map((item) => ({
        sessionId,
        userLat: String(lat),
        userLng: String(lng),
        categoryId: categoryId || null,
        radiusKm: String(radiusKm),
        placeId: item.place.id,
        score: String(item.score),
        rank: item.rank,
        distanceKm: String(item.place.distance),
        weightsJson: dssResult.weights,
        evaluationDetails: {
          sPlus: item.distanceToPositiveIdeal,
          sMinus: item.distanceToNegativeIdeal,
          rawValues: item.rawValues,
          normalizedValues: item.normalizedValues,
          weightedValues: item.weightedValues,
        },
      }));

      await this.drizzle.insert(recommendations).values(recordsToInsert);
    } catch (err) {
      // Log error silently without failing request
    }

    return {
      sessionId,
      aiModel: 'CPR (Contextualized POI Recommendation - IJCAI 2020)',
      decisionMethod: 'AHP + TOPSIS Multi-Criteria Decision Making',
      userLocation: { lat, lng },
      radiusKm,
      evaluatedContext: {
        userId: userId || 'Guest',
        hourOfDay: hourOfDay !== undefined ? hourOfDay : new Date().getHours(),
        userTags: userTags || [],
      },
      totalCandidates: alternatives.length,
      weights: dssResult.weights,
      ahpDetails: dssResult.ahpResult,
      topsisIdealSolutions: {
        positiveA: dssResult.topsisResult.idealPositive,
        negativeA: dssResult.topsisResult.idealNegative,
      },
      topRecommendations: topResults,
      allRankedPlaces: rankedPlaces,
    };
  }

  /**
   * Tính toán lại thứ hạng khi người dùng thay đổi Slider trọng số trên giao diện
   */
  recalculate(dto: RecalculateWeightsDto) {
    const dssResult = this.dssService.processEvaluation(dto.candidates, {
      ahpMatrix: dto.ahpMatrix?.matrix,
      directWeights: dto.weights,
    });

    return {
      weights: dssResult.weights,
      ahpDetails: dssResult.ahpResult,
      topsisIdealSolutions: {
        positiveA: dssResult.topsisResult.idealPositive,
        negativeA: dssResult.topsisResult.idealNegative,
      },
      rankedPlaces: dssResult.topsisResult.rankedItems,
    };
  }

  /**
   * So sánh thực nghiệm giữa phương pháp Nearest Location (truyền thống) và L-DSS TOPSIS
   */
  async compareNearestVsDss(dto: RecommendQueryDto) {
    const dssResponse = await this.getRecommendations(dto);
    const allPlaces = dssResponse.allRankedPlaces || [];

    if (allPlaces.length === 0) {
      return {
        message: 'Không có đủ dữ liệu để so sánh',
      };
    }

    // Xếp hạng theo phương pháp truyền thống: Khoảng cách gần nhất
    const nearestRanked = [...allPlaces].sort(
      (a, b) => a.place.distance - b.place.distance,
    );

    const nearestTop5 = nearestRanked.slice(0, 5).map((item, idx) => ({
      ...item,
      nearestRank: idx + 1,
    }));

    const dssTop5 = allPlaces.slice(0, 5).map((item) => ({
      ...item,
      dssRank: item.rank,
    }));

    // Tính toán các chỉ số so sánh trung bình TOP 5
    const avgDistanceNearest =
      nearestTop5.reduce((acc, cur) => acc + cur.place.distance, 0) / nearestTop5.length;
    const avgRatingNearest =
      nearestTop5.reduce((acc, cur) => acc + cur.place.rating, 0) / nearestTop5.length;
    const avgPriceNearest =
      nearestTop5.reduce((acc, cur) => acc + cur.place.price, 0) / nearestTop5.length;
    const avgPopularityNearest =
      nearestTop5.reduce((acc, cur) => acc + cur.place.popularity, 0) / nearestTop5.length;

    const avgDistanceDss =
      dssTop5.reduce((acc, cur) => acc + cur.place.distance, 0) / dssTop5.length;
    const avgRatingDss =
      dssTop5.reduce((acc, cur) => acc + cur.place.rating, 0) / dssTop5.length;
    const avgPriceDss =
      dssTop5.reduce((acc, cur) => acc + cur.place.price, 0) / dssTop5.length;
    const avgPopularityDss =
      dssTop5.reduce((acc, cur) => acc + cur.place.popularity, 0) / dssTop5.length;

    return {
      comparisonSummary: {
        nearest: {
          avgDistanceKm: Math.round(avgDistanceNearest * 100) / 100,
          avgRating: Math.round(avgRatingNearest * 100) / 100,
          avgPriceVnd: Math.round(avgPriceNearest),
          avgPopularity: Math.round(avgPopularityNearest * 10) / 10,
        },
        dssTopsis: {
          avgDistanceKm: Math.round(avgDistanceDss * 100) / 100,
          avgRating: Math.round(avgRatingDss * 100) / 100,
          avgPriceVnd: Math.round(avgPriceDss),
          avgPopularity: Math.round(avgPopularityDss * 10) / 10,
        },
        finding:
          'L-DSS TOPSIS cân bằng toàn diện giữa khoảng cách, đánh giá chất lượng, mức giá và độ phổ biến thay vì chỉ chọn địa điểm gần nhất.',
      },
      nearestRankedTop5: nearestTop5,
      dssRankedTop5: dssTop5,
    };
  }
}
