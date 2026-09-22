import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsArray, IsNumber, IsOptional, ArrayMinSize, ArrayMaxSize } from 'class-validator';

export class AhpPairwiseMatrixDto {
  @ApiProperty({
    description: 'Ma trận so sánh cặp 5x5 (Distance, Rating, Price, Preference, Popularity)',
    example: [
      [1, 2, 3, 4, 5],
      [0.5, 1, 2, 3, 4],
      [0.333, 0.5, 1, 2, 3],
      [0.25, 0.333, 0.5, 1, 2],
      [0.2, 0.25, 0.333, 0.5, 1],
    ],
  })
  @IsArray()
  @ArrayMinSize(5)
  @ArrayMaxSize(5)
  matrix: number[][];
}

export class DirectCriteriaWeightsDto {
  @ApiPropertyOptional({ example: 0.30, description: 'Trọng số Khoảng cách (C1 - Cost)' })
  @IsOptional()
  @IsNumber()
  distanceWeight?: number;

  @ApiPropertyOptional({ example: 0.25, description: 'Trọng số Đánh giá Rating (C2 - Benefit)' })
  @IsOptional()
  @IsNumber()
  ratingWeight?: number;

  @ApiPropertyOptional({ example: 0.20, description: 'Trọng số Giá tiền (C3 - Cost)' })
  @IsOptional()
  @IsNumber()
  priceWeight?: number;

  @ApiPropertyOptional({ example: 0.15, description: 'Trọng số Mức độ phù hợp / Sở thích (C4 - Benefit)' })
  @IsOptional()
  @IsNumber()
  preferenceWeight?: number;

  @ApiPropertyOptional({ example: 0.10, description: 'Trọng số Độ phổ biến (C5 - Benefit)' })
  @IsOptional()
  @IsNumber()
  popularityWeight?: number;
}
