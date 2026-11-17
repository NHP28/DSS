import { Type } from 'class-transformer';
import { IsArray, IsBoolean, IsIn, IsInt, IsNumber, IsOptional, Max, Min } from 'class-validator';

export class RecommendDto {
  @IsOptional() @IsInt() @Min(0) userId?: number;
  @IsNumber() @Min(-90) @Max(90) latitude = 16.0678;
  @IsNumber() @Min(-180) @Max(180) longitude = 108.2208;
  @IsInt() @Min(0) @Max(23) hour = 8;
  @IsInt() @Min(0) @Max(6) dayOfWeek = 0;
  @IsInt() @Min(1) @Max(50) topK = 10;
  @IsOptional() @IsIn(['cafe','restaurant','hotel','tourist_spot']) category?: string;
  @IsNumber() @Min(.1) @Max(100) radiusKm = 10;
  @IsOptional() @IsNumber() @Min(0) @Max(100000000) maxPrice?: number;
  @IsBoolean() excludeVisited = true;
  @IsIn(['balanced','proximity','budget','ai_centric']) preset = 'balanced';
  @IsOptional() @IsArray() @IsArray({each:true}) matrix?: number[][];
}
export class PoiQuery {
  @IsOptional() @IsIn(['cafe','restaurant','hotel','tourist_spot']) category?: string;
  @IsOptional() @Type(()=>Number) @IsInt() @Min(1) @Max(1000) limit = 100;
}
export class FeedbackDto {
  @IsInt() @Min(0) userId!: number;
  @IsInt() @Min(0) poiId!: number;
  @IsIn(['like','dislike','visit']) action!: 'like'|'dislike'|'visit';
}
export class UserQuery {
  @Type(()=>Number) @IsInt() @Min(1) @Max(1500) limit = 100;
}
