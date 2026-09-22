import { Injectable } from '@nestjs/common';
import { AhpService, AhpResult } from './ahp/ahp.service';
import { TopsisService, TopsisResult, AlternativeInput } from './topsis/topsis.service';
import { AhpPairwiseMatrixDto, DirectCriteriaWeightsDto } from './dto/ahp-matrix.dto';

export interface DssPipelineOptions {
  ahpMatrix?: number[][];
  directWeights?: DirectCriteriaWeightsDto;
}

@Injectable()
export class DssService {
  constructor(
    private readonly ahpService: AhpService,
    private readonly topsisService: TopsisService,
  ) {}

  /**
   * Tính trọng số AHP từ ma trận so sánh cặp
   */
  calculateAhp(matrixDto: AhpPairwiseMatrixDto): AhpResult {
    return this.ahpService.calculateFromPairwiseMatrix(matrixDto.matrix);
  }

  /**
   * Chuẩn hóa trọng số trực tiếp từ Slider người dùng
   */
  normalizeDirectWeights(dto?: DirectCriteriaWeightsDto) {
    return this.ahpService.normalizeDirectWeights(dto);
  }

  /**
   * Chạy quy trình DSS tổng hợp: AHP (hoặc Direct Weights) -> TOPSIS
   */
  processEvaluation(
    alternatives: AlternativeInput[],
    options?: DssPipelineOptions,
  ): {
    ahpResult?: AhpResult;
    topsisResult: TopsisResult;
    weights: {
      distance: number;
      rating: number;
      price: number;
      preference: number;
      popularity: number;
    };
  } {
    let weightsArray: number[];
    let weightsObj: {
      distance: number;
      rating: number;
      price: number;
      preference: number;
      popularity: number;
    };
    let ahpResult: AhpResult | undefined;

    if (options?.ahpMatrix && options.ahpMatrix.length === 5) {
      ahpResult = this.ahpService.calculateFromPairwiseMatrix(options.ahpMatrix);
      weightsArray = ahpResult.weightsArray;
      weightsObj = ahpResult.weights;
    } else {
      const normalized = this.ahpService.normalizeDirectWeights(options?.directWeights);
      weightsArray = normalized.weightsArray;
      weightsObj = normalized.weights;
    }

    const topsisResult = this.topsisService.evaluate(alternatives, weightsArray);

    return {
      ahpResult,
      topsisResult,
      weights: weightsObj,
    };
  }
}
