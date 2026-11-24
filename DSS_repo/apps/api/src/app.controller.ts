import { Body, Controller, Get, Headers, HttpCode, Param, Post, Query } from '@nestjs/common';
import { AppService } from './app.service';
import { AuthService } from './auth/auth.service';
import { FeedbackDto, PoiQuery, RecommendDto, ThemeRecommendDto } from './dto';
import { CRITERIA, PRESETS } from './dss';
import { RecommendService } from './recommend.service';

@Controller()
export class AppController {
  constructor(private readonly service: AppService, private readonly recommender: RecommendService, private readonly auth: AuthService) {}

  @Get('health') health() { return this.service.health(); }
  @Get('system') system() { return this.service.system(); }
  @Get('stats') stats() { return this.service.stats(); }
  @Get('pois') pois(@Query() q: PoiQuery) { return this.service.catalog(q.category, q.limit); }
  @Get('presets') presets() { return { criteria: CRITERIA, presets: PRESETS }; }
  @Get('themes') themes() { return this.recommender.themes(); }

  @Post('recommendations') @HttpCode(200)
  async recommend(@Body() dto: RecommendDto, @Headers('cookie') cookie?: string) {
    return this.recommender.recommend(dto, await this.auth.current(cookie));
  }

  @Post('themes/:slug/recommendations') @HttpCode(200)
  async theme(@Param('slug') slug: string, @Body() dto: ThemeRecommendDto, @Headers('cookie') cookie?: string) {
    return this.recommender.themeRecommend(slug, dto, await this.auth.current(cookie));
  }

  @Get('saved') async saved(@Headers('cookie') cookie?: string) { return this.service.saved(await this.auth.require(cookie)); }

  @Post('feedback') @HttpCode(200)
  async feedback(@Body() dto: FeedbackDto, @Headers('cookie') cookie?: string) {
    return this.service.feedback(dto, await this.auth.require(cookie));
  }
}
