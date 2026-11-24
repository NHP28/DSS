import { Controller, DefaultValuePipe, Get, Headers, NotFoundException, Param, ParseIntPipe, Query } from '@nestjs/common';
import { AuthService } from '../auth/auth.service';
import { Store } from '../store';
import { KgService } from './kg.service';

@Controller('kg')
export class KgController {
  constructor(private readonly kg: KgService, private readonly auth: AuthService, private readonly store: Store) {}

  @Get('stats') stats() { return this.kg.stats(); }

  @Get('poi/:id') async poi(@Param('id', ParseIntPipe) id: number) {
    const graph = await this.kg.neighbourhood(id);
    if (!graph) throw new NotFoundException('Không có địa điểm này trong đồ thị.');
    return graph;
  }

  @Get('poi/:id/similar') similar(@Param('id', ParseIntPipe) id: number, @Query('limit', new DefaultValuePipe(8), ParseIntPipe) limit: number) {
    return this.kg.similar(id, Math.min(Math.max(limit, 1), 20));
  }

  @Get('explain') async explain(@Query('poiId', ParseIntPipe) poiId: number,
    @Query('hour', new DefaultValuePipe(8), ParseIntPipe) hour: number, @Headers('cookie') cookie?: string) {
    const account = await this.auth.current(cookie);
    const anchors = new Set<number>();
    if (account) {
      (await this.store.feedback(account.id)).forEach(item => anchors.add(item.poiId));
      if (account.datasetUserId != null) (await this.store.visitedByDatasetUser(account.datasetUserId)).forEach(id => anchors.add(id));
    }
    anchors.delete(poiId);
    const result = await this.kg.explain(poiId, [...anchors], Math.min(Math.max(hour, 0), 23));
    if (!result) throw new NotFoundException('Không có địa điểm này trong đồ thị.');
    return result;
  }
}
