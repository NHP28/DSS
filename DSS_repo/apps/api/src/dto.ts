import { Type } from 'class-transformer';
import { ArrayMaxSize, ArrayMinSize, IsArray, IsBoolean, IsIn, IsInt, IsNumber, IsOptional, IsString, Matches, Max, MaxLength, Min, MinLength } from 'class-validator';

const CATEGORIES = ['cafe', 'restaurant', 'hotel', 'tourist_spot'];

export class RecommendDto {
  @IsNumber() @Min(-90) @Max(90) latitude = 16.0678;
  @IsNumber() @Min(-180) @Max(180) longitude = 108.2208;
  @IsInt() @Min(0) @Max(23) hour = 8;
  @IsInt() @Min(0) @Max(6) dayOfWeek = 0;
  // Fields left out fall back to the signed-in account's saved model settings.
  @IsOptional() @IsInt() @Min(1) @Max(50) topK?: number;
  @IsOptional() @IsIn(CATEGORIES) category?: string;
  @IsOptional() @IsArray() @ArrayMaxSize(4) @IsIn(CATEGORIES, { each: true }) categories?: string[];
  @IsOptional() @IsArray() @ArrayMaxSize(10) @IsString({ each: true }) districts?: string[];
  @IsOptional() @IsNumber() @Min(.1) @Max(100) radiusKm?: number;
  @IsOptional() @IsNumber() @Min(0) @Max(100000000) maxPrice?: number | null;
  @IsOptional() @IsBoolean() excludeVisited?: boolean;
  @IsOptional() @IsIn(['balanced', 'proximity', 'budget', 'ai_centric', 'custom']) preset?: string;
  @IsOptional() @IsArray() @IsArray({ each: true }) matrix?: number[][];
  @IsOptional() @IsIn(['tas_gnn', 'lightgcn', 'hourly_popularity', 'popularity']) model?: string;
  @IsOptional() @IsBoolean() useTime?: boolean;
  @IsOptional() @IsInt() @Min(0) @Max(200) candidatePool?: number;
  @IsOptional() @IsBoolean() showHidden?: boolean;
}
export class ThemeRecommendDto {
  @IsNumber() @Min(-90) @Max(90) latitude = 16.0678;
  @IsNumber() @Min(-180) @Max(180) longitude = 108.2208;
  @IsOptional() @IsInt() @Min(0) @Max(23) hour?: number;
  @IsOptional() @IsInt() @Min(0) @Max(6) dayOfWeek?: number;
  @IsOptional() @IsNumber() @Min(.1) @Max(100) radiusKm?: number;
}
export class PoiQuery {
  @IsOptional() @IsIn(CATEGORIES) category?: string;
  @IsOptional() @Type(() => Number) @IsInt() @Min(1) @Max(1000) limit = 100;
}
export class FeedbackDto {
  @IsInt() @Min(0) poiId!: number;
  @IsIn(['like', 'unlike', 'visit', 'unvisit']) action!: 'like' | 'unlike' | 'visit' | 'unvisit';
}
export class RegisterDto {
  @IsString() @Matches(/^[a-z0-9_]{3,30}$/, { message: 'Tên đăng nhập gồm 3–30 ký tự: chữ thường, số hoặc dấu gạch dưới.' }) username!: string;
  @IsString() @MinLength(1) @MaxLength(60) displayName!: string;
  @IsString() @MinLength(8, { message: 'Mật khẩu cần ít nhất 8 ký tự.' }) @MaxLength(200) password!: string;
  @IsArray() @ArrayMinSize(1, { message: 'Chọn ít nhất một chủ đề yêu thích.' }) @ArrayMaxSize(8) @IsString({ each: true }) interests!: string[];
}
export class LoginDto {
  @IsString() @MinLength(1) @MaxLength(30) username!: string;
  @IsString() @MinLength(1) @MaxLength(200) password!: string;
}
