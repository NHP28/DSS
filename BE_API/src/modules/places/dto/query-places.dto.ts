import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsOptional, IsNumber, IsString, Min } from 'class-validator';
import { Type } from 'class-transformer';

export class QueryPlacesDto {
  @ApiPropertyOptional({ example: 1, description: 'Lọc theo ID danh mục' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  categoryId?: number;

  @ApiPropertyOptional({ example: 'Hai Chau', description: 'Lọc theo Quận/Huyện tại Đà Nẵng' })
  @IsOptional()
  @IsString()
  district?: string;

  @ApiPropertyOptional({ example: 'Cafe', description: 'Tìm kiếm theo tên địa điểm hoặc địa chỉ' })
  @IsOptional()
  @IsString()
  search?: string;

  @ApiPropertyOptional({ example: 16.0614, description: 'Vĩ độ tâm tìm kiếm' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  lat?: number;

  @ApiPropertyOptional({ example: 108.2208, description: 'Kinh độ tâm tìm kiếm' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  lng?: number;

  @ApiPropertyOptional({ example: 5, description: 'Bán kính tìm kiếm (km)' })
  @IsOptional()
  @IsNumber()
  @Min(0.1)
  @Type(() => Number)
  radiusKm?: number;

  @ApiPropertyOptional({ example: 50, description: 'Số lượng kết quả tối đa' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  limit?: number;

  @ApiPropertyOptional({ example: 0, description: 'Offset phân trang' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  offset?: number;
}
