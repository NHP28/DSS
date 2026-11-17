import { Body, Controller, Get, Post, Query } from '@nestjs/common';
import { AppService } from './app.service';
import { FeedbackDto, PoiQuery, RecommendDto, UserQuery } from './dto';
import { CRITERIA, PRESETS } from './dss';

@Controller()
export class AppController {
  constructor(private readonly service: AppService) {}
  @Get('health') health() { return this.service.health(); }
  @Get('stats') stats() { return this.service.stats(); }
  @Get('pois') pois(@Query() q: PoiQuery) { return this.service.catalog(q.category,q.limit); }
  @Get('users') users(@Query() q: UserQuery) { return this.service.users(q.limit); }
  @Get('presets') presets() { return {criteria:CRITERIA,presets:PRESETS}; }
  @Post('recommendations') recommend(@Body() dto: RecommendDto) { return this.service.recommend(dto); }
  @Post('feedback') feedback(@Body() dto: FeedbackDto) { return this.service.feedback(dto); }
}
