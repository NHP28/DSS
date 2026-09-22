import { Injectable, BadRequestException } from '@nestjs/common';
import { DirectCriteriaWeightsDto } from '../dto/ahp-matrix.dto';

export interface AhpResult {
  weights: {
    distance: number;
    rating: number;
    price: number;
    preference: number;
    popularity: number;
  };
  weightsArray: number[];
  lambdaMax: number;
  consistencyIndex: number;
  consistencyRatio: number;
  isConsistent: boolean;
}

const RANDOM_INDEX_MAP: Record<number, number> = {
  1: 0.0,
  2: 0.0,
  3: 0.58,
  4: 0.90,
  5: 1.12,
  6: 1.24,
  7: 1.32,
  8: 1.41,
  9: 1.45,
  10: 1.49,
};

@Injectable()
export class AhpService {
  /**
   * Tính toán vector trọng số tiêu chí và kiểm tra chỉ số nhất quán CR từ ma trận so sánh cặp AHP
   * Tiêu chí: [Distance (C1), Rating (C2), Price (C3), Preference (C4), Popularity (C5)]
   */
  calculateFromPairwiseMatrix(matrix: number[][]): AhpResult {
    const n = matrix.length;
    if (n !== 5 || matrix.some((row) => row.length !== 5)) {
      throw new BadRequestException('Ma trận so sánh cặp AHP phải có kích thước 5x5');
    }

    // 1. Tính tổng các cột (Column sums)
    const colSums = new Array(n).fill(0);
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        colSums[j] += matrix[i][j];
      }
    }

    // 2. Chuẩn hóa ma trận (Normalize matrix) & tính vector trọng số (Priority vector)
    const normalizedMatrix: number[][] = [];
    const weightsArray: number[] = new Array(n).fill(0);

    for (let i = 0; i < n; i++) {
      normalizedMatrix[i] = [];
      let rowSum = 0;
      for (let j = 0; j < n; j++) {
        const val = matrix[i][j] / colSums[j];
        normalizedMatrix[i][j] = val;
        rowSum += val;
      }
      weightsArray[i] = rowSum / n;
    }

    // 3. Tính Lambda Max (Giá trị riêng cực đại)
    let lambdaMax = 0;
    for (let j = 0; j < n; j++) {
      lambdaMax += colSums[j] * weightsArray[j];
    }

    // 4. Tính Consistency Index (CI) & Consistency Ratio (CR)
    const CI = (lambdaMax - n) / (n - 1);
    const RI = RANDOM_INDEX_MAP[n] || 1.12;
    const CR = RI === 0 ? 0 : CI / RI;

    return {
      weights: {
        distance: Math.round(weightsArray[0] * 10000) / 10000,
        rating: Math.round(weightsArray[1] * 10000) / 10000,
        price: Math.round(weightsArray[2] * 10000) / 10000,
        preference: Math.round(weightsArray[3] * 10000) / 10000,
        popularity: Math.round(weightsArray[4] * 10000) / 10000,
      },
      weightsArray: weightsArray.map((w) => Math.round(w * 10000) / 10000),
      lambdaMax: Math.round(lambdaMax * 10000) / 10000,
      consistencyIndex: Math.round(CI * 10000) / 10000,
      consistencyRatio: Math.round(CR * 10000) / 10000,
      isConsistent: CR <= 0.1,
    };
  }

  /**
   * Chuẩn hóa trực tiếp khi người dùng tùy chỉnh thanh trượt trọng số (Sliders)
   */
  normalizeDirectWeights(dto?: DirectCriteriaWeightsDto): {
    weights: {
      distance: number;
      rating: number;
      price: number;
      preference: number;
      popularity: number;
    };
    weightsArray: number[];
  } {
    const rawDistance = dto?.distanceWeight ?? 0.30;
    const rawRating = dto?.ratingWeight ?? 0.25;
    const rawPrice = dto?.priceWeight ?? 0.20;
    const rawPreference = dto?.preferenceWeight ?? 0.15;
    const rawPopularity = dto?.popularityWeight ?? 0.10;

    const sum = rawDistance + rawRating + rawPrice + rawPreference + rawPopularity;
    const safeSum = sum > 0 ? sum : 1;

    const distance = Math.round((rawDistance / safeSum) * 10000) / 10000;
    const rating = Math.round((rawRating / safeSum) * 10000) / 10000;
    const price = Math.round((rawPrice / safeSum) * 10000) / 10000;
    const preference = Math.round((rawPreference / safeSum) * 10000) / 10000;
    const popularity = Math.round((rawPopularity / safeSum) * 10000) / 10000;

    return {
      weights: {
        distance,
        rating,
        price,
        preference,
        popularity,
      },
      weightsArray: [distance, rating, price, preference, popularity],
    };
  }
}
