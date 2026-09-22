import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class CreateCategoryDto {
  @ApiProperty({ example: 'Cafe', description: 'Tên danh mục' })
  @IsNotEmpty({ message: 'Tên danh mục không được để trống' })
  @IsString()
  name: string;

  @ApiProperty({ example: 'cafe', description: 'Slug duy nhất' })
  @IsNotEmpty({ message: 'Slug không được để trống' })
  @IsString()
  slug: string;

  @ApiPropertyOptional({ example: 'Quán cafe, trà sữa, thức uống giải khát tại Đà Nẵng' })
  @IsOptional()
  @IsString()
  description?: string;

  @ApiPropertyOptional({ example: 'coffee', description: 'Tên icon Lucide / Iconify' })
  @IsOptional()
  @IsString()
  icon?: string;
}
