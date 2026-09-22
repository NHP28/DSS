import { Controller, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { DssService } from './dss.service';
import { AhpPairwiseMatrixDto, DirectCriteriaWeightsDto } from './dto/ahp-matrix.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('DSS Engine (Thuật toán AHP & TOPSIS)')
@Controller('dss')
export class DssController {
  constructor(private readonly dssService: DssService) {}

  @Post('ahp/calculate')
  @ApiOperation({
    summary: 'Tính vector trọng số và kiểm định tỷ số nhất quán CR từ ma trận AHP 5x5',
    description: 'Thực hiện phân tích thứ bậc AHP, kiểm tra tính hợp lệ CR <= 0.1 của ma trận so sánh cặp',
  })
  @ApiResponse({ status: 200, description: 'Kết quả tính toán trọng số AHP' })
  @ResponseMessage('Tính toán trọng số AHP thành công')
  calculateAhp(@Body() dto: AhpPairwiseMatrixDto) {
    return this.dssService.calculateAhp(dto);
  }

  @Post('weights/normalize')
  @ApiOperation({
    summary: 'Chuẩn hóa trọng số trực tiếp khi người dùng chỉnh Slider',
    description: 'Đảm bảo tổng trọng số của 5 tiêu chí luôn bằng 1.0 (100%)',
  })
  @ApiResponse({ status: 200, description: 'Trọng số đã được chuẩn hóa' })
  @ResponseMessage('Chuẩn hóa trọng số thành công')
  normalizeWeights(@Body() dto: DirectCriteriaWeightsDto) {
    return this.dssService.normalizeDirectWeights(dto);
  }
}
