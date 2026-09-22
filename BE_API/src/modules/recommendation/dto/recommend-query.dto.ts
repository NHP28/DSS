import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  Min,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';
import { DirectCriteriaWeightsDto, AhpPairwiseMatrixDto } from '../../dss/dto/ahp-matrix.dto';

export class RecommendQueryDto {
  @ApiProperty({ example: 16.0614, description: 'Vĩ độ hiện tại của người dùng (Latitude)' })
  @IsNotEmpty()
  @IsNumber()
  @Type(() => Number)
  lat: number;

  @ApiProperty({ example: 108.2208, description: 'Kinh độ hiện tại của người dùng (Longitude)' })
  @IsNotEmpty()
  @IsNumber()
  @Type(() => Number)
  lng: number;

  @ApiPropertyOptional({ example: 1, description: 'ID danh mục (1: Cafe, 2: Nhà hàng, 3: Khách sạn, 4: Du lịch)' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  categoryId?: number;

  @ApiPropertyOptional({ example: 5, description: 'Bán kính tìm kiếm (km)' })
  @IsOptional()
  @IsNumber()
  @Min(0.5)
  @Type(() => Number)
  radiusKm?: number;

  @ApiPropertyOptional({ example: 'Hai Chau', description: 'Lọc theo Quận/Huyện tại Đà Nẵng' })
  @IsOptional()
  @IsString()
  district?: string;

  @ApiPropertyOptional({ description: 'Trọng số trực tiếp các tiêu chí' })
  @IsOptional()
  @ValidateNested()
  @Type(() => DirectCriteriaWeightsDto)
  weights?: DirectCriteriaWeightsDto;

  @ApiPropertyOptional({ description: 'Ma trận AHP 5x5 nếu người dùng muốn tính qua AHP' })
  @IsOptional()
  @ValidateNested()
  @Type(() => AhpPairwiseMatrixDto)
  ahpMatrix?: AhpPairwiseMatrixDto;

  @ApiPropertyOptional({ example: 10, description: 'Số lượng kết quả đề xuất trả về (TOP K)' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  topK?: number;

  @ApiPropertyOptional({ example: 1, description: 'ID người dùng để tính điểm cá nhân hóa CPR (IJCAI 2020)' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  userId?: number;

  @ApiPropertyOptional({ example: 19, description: 'Khung giờ hiện tại (0 - 23) để tính ngữ cảnh thời gian' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  hourOfDay?: number;

  @ApiPropertyOptional({ example: ['yên tĩnh', 'làm việc', 'view đẹp'], description: 'Danh sách tags sở thích của người dùng' })
  @IsOptional()
  userTags?: string[];

  @ApiPropertyOptional({ example: true, description: 'Gợi ý trên toàn bộ TP. Đà Nẵng (bỏ qua giới hạn bán kính)' })
  @IsOptional()
  allDanang?: boolean;
}
