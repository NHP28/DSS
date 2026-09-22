import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsArray, IsNotEmpty, IsOptional, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { DirectCriteriaWeightsDto, AhpPairwiseMatrixDto } from '../../dss/dto/ahp-matrix.dto';
import { AlternativeInput } from '../../dss/topsis/topsis.service';

export class RecalculateWeightsDto {
  @ApiProperty({ description: 'Danh sách địa điểm ứng viên kèm thông số hiện tại' })
  @IsNotEmpty()
  @IsArray()
  candidates: AlternativeInput[];

  @ApiPropertyOptional({ description: 'Trọng số trực tiếp mới' })
  @IsOptional()
  @ValidateNested()
  @Type(() => DirectCriteriaWeightsDto)
  weights?: DirectCriteriaWeightsDto;

  @ApiPropertyOptional({ description: 'Ma trận AHP 5x5 mới' })
  @IsOptional()
  @ValidateNested()
  @Type(() => AhpPairwiseMatrixDto)
  ahpMatrix?: AhpPairwiseMatrixDto;
}
