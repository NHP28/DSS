import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  Min,
} from 'class-validator';
import { Type } from 'class-transformer';

export class CreatePlaceDto {
  @ApiProperty({ example: 1, description: 'ID danh mục' })
  @IsNotEmpty()
  @IsNumber()
  @Type(() => Number)
  categoryId: number;

  @ApiProperty({ example: 'The Cup Cafe Đà Nẵng', description: 'Tên địa điểm' })
  @IsNotEmpty()
  @IsString()
  name: string;

  @ApiPropertyOptional({ example: '233 Nguyễn Văn Thoại, Phước Mỹ, Sơn Trà, Đà Nẵng' })
  @IsOptional()
  @IsString()
  address?: string;

  @ApiPropertyOptional({ example: 'Sơn Trà' })
  @IsOptional()
  @IsString()
  district?: string;

  @ApiPropertyOptional({ example: 'Phước Mỹ' })
  @IsOptional()
  @IsString()
  ward?: string;

  @ApiProperty({ example: 16.0614, description: 'Vĩ độ (Latitude)' })
  @IsNotEmpty()
  @IsNumber()
  @Type(() => Number)
  latitude: number;

  @ApiProperty({ example: 108.2208, description: 'Kinh độ (Longitude)' })
  @IsNotEmpty()
  @IsNumber()
  @Type(() => Number)
  longitude: number;

  @ApiPropertyOptional({ example: 4.8, description: 'Đánh giá (0 - 5.0)' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(5)
  @Type(() => Number)
  rating?: number;

  @ApiPropertyOptional({ example: 250, description: 'Tổng số lượt đánh giá' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  userRatingsTotal?: number;

  @ApiPropertyOptional({ example: 45000, description: 'Giá trung bình (VNĐ)' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  priceAvg?: number;

  @ApiPropertyOptional({ example: 2, description: 'Mức giá 1 (rẻ) -> 4 (cao cấp)' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  priceLevel?: number;

  @ApiPropertyOptional({ example: 85, description: 'Độ phổ biến (0 - 100)' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(100)
  @Type(() => Number)
  popularity?: number;

  @ApiPropertyOptional({ example: 0.9, description: 'Mức độ phù hợp phong cách (0.00 - 1.00)' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(1)
  @Type(() => Number)
  matchPreference?: number;

  @ApiPropertyOptional({ example: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb' })
  @IsOptional()
  @IsString()
  imageUrl?: string;

  @ApiPropertyOptional({ example: '07:00 - 22:30' })
  @IsOptional()
  @IsString()
  openingHours?: string;

  @ApiPropertyOptional({ example: '0905123456' })
  @IsOptional()
  @IsString()
  phoneNumber?: string;

  @ApiPropertyOptional({ example: 'Quán cafe view đẹp gần biển Mỹ Khê' })
  @IsOptional()
  @IsString()
  description?: string;
}
