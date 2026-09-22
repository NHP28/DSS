import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsEmail, IsNotEmpty, IsNumber, IsOptional, IsString } from 'class-validator';
import { Type } from 'class-transformer';

export class CreateUserDto {
  @ApiProperty({ example: 'Nguyễn Văn A', description: 'Họ và tên người dùng' })
  @IsNotEmpty()
  @IsString()
  name: string;

  @ApiProperty({ example: 'user@example.com', description: 'Email' })
  @IsNotEmpty()
  @IsEmail()
  email: string;

  @ApiPropertyOptional({ example: 16.0614, description: 'Vĩ độ mặc định tại Đà Nẵng' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  defaultLatitude?: number;

  @ApiPropertyOptional({ example: 108.2208, description: 'Kinh độ mặc định tại Đà Nẵng' })
  @IsOptional()
  @IsNumber()
  @Type(() => Number)
  defaultLongitude?: number;
}
