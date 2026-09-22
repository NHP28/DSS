import { Controller, Get, Post, Body, Param, ParseIntPipe } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { CategoriesService } from './categories.service';
import { CreateCategoryDto } from './dto/create-category.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Categories (Danh mục địa điểm)')
@Controller('categories')
export class CategoriesController {
  constructor(private readonly categoriesService: CategoriesService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy toàn bộ danh mục địa điểm (Cafe, Nhà hàng, Khách sạn, Du lịch)' })
  @ApiResponse({ status: 200, description: 'Danh sách danh mục thành công' })
  @ResponseMessage('Lấy danh sách danh mục thành công')
  async getAll() {
    return this.categoriesService.findAll();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Lấy chi tiết danh mục theo ID' })
  @ApiResponse({ status: 200, description: 'Chi tiết danh mục' })
  @ResponseMessage('Lấy chi tiết danh mục thành công')
  async getById(@Param('id', ParseIntPipe) id: number) {
    return this.categoriesService.findById(id);
  }

  @Post()
  @ApiOperation({ summary: 'Tạo mới danh mục địa điểm' })
  @ApiResponse({ status: 201, description: 'Tạo danh mục thành công' })
  @ResponseMessage('Tạo danh mục thành công')
  async create(@Body() dto: CreateCategoryDto) {
    return this.categoriesService.create(dto);
  }
}
