import { Controller, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { RecommendationService } from './recommendation.service';
import { RecommendQueryDto } from './dto/recommend-query.dto';
import { RecalculateWeightsDto } from './dto/recalculate-weights.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Recommendations (Đề xuất địa điểm L-DSS)')
@Controller('recommendations')
export class RecommendationController {
  constructor(private readonly recommendationService: RecommendationService) {}

  @Post('evaluate')
  @ApiOperation({
    summary: 'Đánh giá và đề xuất TOP địa điểm tối ưu theo vị trí người dùng tại Đà Nẵng',
    description:
      'Lọc các địa điểm trong bán kính, chạy thuật toán AHP + TOPSIS theo 5 tiêu chí: Khoảng cách, Đánh giá, Giá cả, Mức độ phù hợp, Độ phổ biến.',
  })
  @ApiResponse({ status: 200, description: 'Danh sách địa điểm xếp hạng thành công' })
  @ResponseMessage('Đề xuất địa điểm DSS thành công')
  async evaluate(@Body() dto: RecommendQueryDto) {
    return this.recommendationService.getRecommendations(dto);
  }

  @Post('recalculate')
  @ApiOperation({
    summary: 'Tính toán lại thứ hạng khi người dùng thay đổi Slider trọng số',
    description: 'Chạy lại thuật toán TOPSIS trên tập ứng viên hiện tại với bộ trọng số mới mà không cần truy vấn lại DB',
  })
  @ApiResponse({ status: 200, description: 'Cập nhật xếp hạng thành công' })
  @ResponseMessage('Cập nhật thứ hạng DSS thành công')
  recalculate(@Body() dto: RecalculateWeightsDto) {
    return this.recommendationService.recalculate(dto);
  }

  @Post('compare')
  @ApiOperation({
    summary: 'So sánh thực nghiệm: Nearest Location (Địa điểm gần nhất) vs L-DSS TOPSIS',
    description: 'Cung cấp dữ liệu phân tích, biểu đồ và kết luận thực nghiệm cho đề tài nghiên cứu DSS',
  })
  @ApiResponse({ status: 200, description: 'Dữ liệu so sánh thực nghiệm thành công' })
  @ResponseMessage('So sánh thực nghiệm thành công')
  async compare(@Body() dto: RecommendQueryDto) {
    return this.recommendationService.compareNearestVsDss(dto);
  }
}
