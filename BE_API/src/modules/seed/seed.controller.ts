import { Controller, Post, Get, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiQuery } from '@nestjs/swagger';
import { SeedService } from './seed.service';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Seed Data & Crawl (Dữ liệu Đà Nẵng)')
@Controller('seed')
export class SeedController {
  constructor(private readonly seedService: SeedService) {}

  @Post('init')
  @ApiOperation({
    summary: 'Khởi tạo dữ liệu mẫu Đà Nẵng (Categories + 30+ Places thực tế)',
    description: 'Nạp danh mục và danh sách các quán cafe, nhà hàng, khách sạn, điểm du lịch thực tế tại Đà Nẵng vào MySQL',
  })
  @ApiResponse({ status: 201, description: 'Khởi tạo dữ liệu thành công' })
  @ResponseMessage('Khởi tạo dữ liệu mẫu thành công')
  async initData() {
    return this.seedService.seedAll();
  }

  @Post('crawl-osm')
  @ApiOperation({
    summary: 'Thu thập thêm địa điểm thực tế từ bản đồ Đà Nẵng (OpenStreetMap / Overpass)',
    description: 'Crawl trực tiếp tọa độ, địa chỉ, loại hình từ OpenStreetMap cho khu vực Đà Nẵng',
  })
  @ApiQuery({ name: 'categorySlug', required: false, enum: ['cafe', 'restaurant', 'hotel', 'tourist_spot'] })
  @ApiQuery({ name: 'limit', required: false, type: Number, example: 30 })
  @ApiResponse({ status: 201, description: 'Crawl dữ liệu thành công' })
  @ResponseMessage('Crawl dữ liệu thành công')
  async crawlOsm(
    @Query('categorySlug') categorySlug?: 'cafe' | 'restaurant' | 'hotel' | 'tourist_spot',
    @Query('limit') limit?: number,
  ) {
    return this.seedService.crawlFromOsm({ categorySlug, limit });
  }

  @Get('status')
  @ApiOperation({ summary: 'Kiểm tra trạng thái số lượng dữ liệu hiện có trong Database' })
  @ApiResponse({ status: 200, description: 'Trạng thái dữ liệu' })
  @ResponseMessage('Lấy trạng thái dữ liệu thành công')
  async getStatus() {
    return this.seedService.getStatus();
  }
}
