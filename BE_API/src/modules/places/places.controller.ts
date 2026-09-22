import { Controller, Get, Post, Body, Param, Query, ParseIntPipe } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiQuery } from '@nestjs/swagger';
import { PlacesService } from './places.service';
import { CreatePlaceDto } from './dto/create-place.dto';
import { QueryPlacesDto } from './dto/query-places.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Places (Địa điểm tại Đà Nẵng)')
@Controller('places')
export class PlacesController {
  constructor(private readonly placesService: PlacesService) {}

  @Get()
  @ApiOperation({
    summary: 'Tìm kiếm danh sách địa điểm theo tọa độ, bán kính, quận/huyện, danh mục',
    description: 'Hỗ trợ tính khoảng cách Haversine từ vị trí người dùng đến từng quán cafe, nhà hàng...',
  })
  @ApiResponse({ status: 200, description: 'Danh sách địa điểm thành công' })
  @ResponseMessage('Lấy danh sách địa điểm thành công')
  async getAll(@Query() query: QueryPlacesDto) {
    return this.placesService.findAll(query);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Lấy chi tiết địa điểm theo ID' })
  @ApiResponse({ status: 200, description: 'Chi tiết địa điểm' })
  @ResponseMessage('Lấy thông tin địa điểm thành công')
  async getById(@Param('id', ParseIntPipe) id: number) {
    return this.placesService.findById(id);
  }

  @Post()
  @ApiOperation({ summary: 'Thêm mới địa điểm' })
  @ApiResponse({ status: 201, description: 'Thêm địa điểm thành công' })
  @ResponseMessage('Tạo địa điểm thành công')
  async create(@Body() dto: CreatePlaceDto) {
    return this.placesService.create(dto);
  }
}
