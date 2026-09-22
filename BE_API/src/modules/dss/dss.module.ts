import { Module } from '@nestjs/common';
import { DssController } from './dss.controller';
import { DssService } from './dss.service';
import { AhpService } from './ahp/ahp.service';
import { TopsisService } from './topsis/topsis.service';
import { CprService } from './cpr/cpr.service';

@Module({
  controllers: [DssController],
  providers: [DssService, AhpService, TopsisService, CprService],
  exports: [DssService, AhpService, TopsisService, CprService],
})
export class DssModule {}
