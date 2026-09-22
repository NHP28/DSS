import { Injectable } from '@nestjs/common';

export type CriterionType = 'benefit' | 'cost';

export interface AlternativeInput {
  id: number;
  name: string;
  distance: number; // C1 (Cost) - km
  rating: number; // C2 (Benefit) - 1.0 - 5.0
  price: number; // C3 (Cost) - VNĐ
  preference: number; // C4 (Benefit) - 0.0 - 1.0
  popularity: number; // C5 (Benefit) - 0 - 100
  [key: string]: any;
}

export interface TopsisRankedItem {
  place: AlternativeInput;
  score: number; // Closeness Coefficient Ci (0.0000 - 1.0000)
  rank: number;
  distanceToPositiveIdeal: number; // S+
  distanceToNegativeIdeal: number; // S-
  rawValues: {
    distance: number;
    rating: number;
    price: number;
    preference: number;
    popularity: number;
  };
  normalizedValues: number[];
  weightedValues: number[];
}

export interface TopsisResult {
  rankedItems: TopsisRankedItem[];
  criteriaNames: string[];
  criteriaTypes: CriterionType[];
  weightsUsed: number[];
  idealPositive: number[]; // A+
  idealNegative: number[]; // A-
}

@Injectable()
export class TopsisService {
  private readonly criteriaTypes: CriterionType[] = [
    'cost', // C1: Distance
    'benefit', // C2: Rating
    'cost', // C3: Price
    'benefit', // C4: Preference
    'benefit', // C5: Popularity
  ];

  private readonly criteriaNames = [
    'Khoảng cách (Distance - Cost)',
    'Đánh giá (Rating - Benefit)',
    'Giá cả (Price - Cost)',
    'Mức độ phù hợp (Preference - Benefit)',
    'Độ phổ biến (Popularity - Benefit)',
  ];

  /**
   * Tính toán xếp hạng địa điểm theo phương pháp TOPSIS
   * @param alternatives Danh sách địa điểm ứng viên kèm giá trị tiêu chí
   * @param weights Vector trọng số [w1, w2, w3, w4, w5] (tổng = 1.0)
   */
  evaluate(alternatives: AlternativeInput[], weights: number[]): TopsisResult {
    const m = alternatives.length;
    if (m === 0) {
      return {
        rankedItems: [],
        criteriaNames: this.criteriaNames,
        criteriaTypes: this.criteriaTypes,
        weightsUsed: weights,
        idealPositive: [],
        idealNegative: [],
      };
    }

    // Nếu chỉ có 1 địa điểm, điểm số là 1.0
    if (m === 1) {
      const single = alternatives[0];
      return {
        rankedItems: [
          {
            place: single,
            score: 1.0,
            rank: 1,
            distanceToPositiveIdeal: 0,
            distanceToNegativeIdeal: 1,
            rawValues: {
              distance: single.distance,
              rating: single.rating,
              price: single.price,
              preference: single.preference,
              popularity: single.popularity,
            },
            normalizedValues: [1, 1, 1, 1, 1],
            weightedValues: [...weights],
          },
        ],
        criteriaNames: this.criteriaNames,
        criteriaTypes: this.criteriaTypes,
        weightsUsed: weights,
        idealPositive: [...weights],
        idealNegative: [0, 0, 0, 0, 0],
      };
    }

    const n = 5; // 5 tiêu chí

    // 1. Xây dựng ma trận quyết định X (m x n)
    const X: number[][] = alternatives.map((alt) => [
      Math.max(alt.distance, 0.01), // tránh chia 0 hoặc 0 km
      Math.max(alt.rating, 0.1),
      Math.max(alt.price, 1000),
      Math.max(alt.preference, 0.01),
      Math.max(alt.popularity, 1),
    ]);

    // 2. Chuẩn hóa ma trận bằng phương pháp Vector Normalization: r_ij = x_ij / sqrt(sum(x_kj^2))
    const colNorms: number[] = new Array(n).fill(0);
    for (let j = 0; j < n; j++) {
      let sumSq = 0;
      for (let i = 0; i < m; i++) {
        sumSq += X[i][j] * X[i][j];
      }
      colNorms[j] = Math.sqrt(sumSq) || 1;
    }

    const R: number[][] = [];
    for (let i = 0; i < m; i++) {
      R[i] = [];
      for (let j = 0; j < n; j++) {
        R[i][j] = X[i][j] / colNorms[j];
      }
    }

    // 3. Ma trận quyết định có trọng số V: v_ij = w_j * r_ij
    const V: number[][] = [];
    for (let i = 0; i < m; i++) {
      V[i] = [];
      for (let j = 0; j < n; j++) {
        V[i][j] = R[i][j] * weights[j];
      }
    }

    // 4. Xác định nghiệm lý tưởng tốt nhất (A+) và nghiệm lý tưởng xấu nhất (A-)
    const idealPositive: number[] = new Array(n).fill(0);
    const idealNegative: number[] = new Array(n).fill(0);

    for (let j = 0; j < n; j++) {
      const colValues = V.map((row) => row[j]);
      const maxVal = Math.max(...colValues);
      const minVal = Math.min(...colValues);

      if (this.criteriaTypes[j] === 'benefit') {
        idealPositive[j] = maxVal;
        idealNegative[j] = minVal;
      } else {
        // Cost criterion (Khoảng cách, Giá) -> Càng nhỏ càng tốt
        idealPositive[j] = minVal;
        idealNegative[j] = maxVal;
      }
    }

    // 5. Tính khoảng cách Euclidean đến A+ (S+) và A- (S-)
    const S_plus: number[] = new Array(m).fill(0);
    const S_minus: number[] = new Array(m).fill(0);
    const C: number[] = new Array(m).fill(0);

    for (let i = 0; i < m; i++) {
      let sumSqPlus = 0;
      let sumSqMinus = 0;

      for (let j = 0; j < n; j++) {
        const diffPlus = V[i][j] - idealPositive[j];
        const diffMinus = V[i][j] - idealNegative[j];
        sumSqPlus += diffPlus * diffPlus;
        sumSqMinus += diffMinus * diffMinus;
      }

      S_plus[i] = Math.sqrt(sumSqPlus);
      S_minus[i] = Math.sqrt(sumSqMinus);

      // 6. Tính hệ số gần với phương án lý tưởng C_i = S_i- / (S_i+ + S_i-)
      const totalDist = S_plus[i] + S_minus[i];
      C[i] = totalDist === 0 ? 0.5 : S_minus[i] / totalDist;
    }

    // 7. Tạo kết quả chi tiết cho từng địa điểm
    const evaluatedItems: TopsisRankedItem[] = alternatives.map((alt, idx) => ({
      place: alt,
      score: Math.round(C[idx] * 10000) / 10000,
      rank: 0, // sẽ gán sau khi sắp xếp
      distanceToPositiveIdeal: Math.round(S_plus[idx] * 10000) / 10000,
      distanceToNegativeIdeal: Math.round(S_minus[idx] * 10000) / 10000,
      rawValues: {
        distance: alt.distance,
        rating: alt.rating,
        price: alt.price,
        preference: alt.preference,
        popularity: alt.popularity,
      },
      normalizedValues: R[idx].map((val) => Math.round(val * 10000) / 10000),
      weightedValues: V[idx].map((val) => Math.round(val * 10000) / 10000),
    }));

    // Sắp xếp điểm TOPSIS Ci từ cao xuống thấp
    evaluatedItems.sort((a, b) => b.score - a.score);

    // Gán thứ hạng Rank
    evaluatedItems.forEach((item, index) => {
      item.rank = index + 1;
    });

    return {
      rankedItems: evaluatedItems,
      criteriaNames: this.criteriaNames,
      criteriaTypes: this.criteriaTypes,
      weightsUsed: weights.map((w) => Math.round(w * 10000) / 10000),
      idealPositive: idealPositive.map((v) => Math.round(v * 10000) / 10000),
      idealNegative: idealNegative.map((v) => Math.round(v * 10000) / 10000),
    };
  }
}
