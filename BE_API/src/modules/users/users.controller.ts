import { Controller, Get, Post, Body, Param, ParseIntPipe } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { CreateUserDto } from './dto/create-user.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Users (Người dùng & Tùy chọn vị trí)')
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy danh sách người dùng' })
  @ApiResponse({ status: 200, description: 'Danh sách người dùng thành công' })
  @ResponseMessage('Lấy danh sách người dùng thành công')
  async getAll() {
    return this.usersService.findAll();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Lấy chi tiết người dùng theo ID' })
  @ApiResponse({ status: 200, description: 'Chi tiết người dùng' })
  @ResponseMessage('Lấy chi tiết người dùng thành công')
  async getById(@Param('id', ParseIntPipe) id: number) {
    return this.usersService.findById(id);
  }

  @Post()
  @ApiOperation({ summary: 'Tạo mới người dùng kèm vị trí mặc định tại Đà Nẵng' })
  @ApiResponse({ status: 201, description: 'Tạo người dùng thành công' })
  @ResponseMessage('Tạo người dùng thành công')
  async create(@Body() dto: CreateUserDto) {
    return this.usersService.create(dto);
  }
}
