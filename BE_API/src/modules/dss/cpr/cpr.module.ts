import { Module } from '@nestjs/common';
import { CprService } from './cpr.service';

@Module({
  providers: [CprService],
  exports: [CprService],
})
export class CprModule {}
