import { Controller, Get, Param, ParseIntPipe } from '@nestjs/common';
import { GoogleService } from './google.service';

@Controller('pois')
export class GoogleController {
  constructor(private readonly google: GoogleService) {}

  /** Photo and rating from Google Maps for one place; `available: false` when there is nothing to show. */
  @Get(':id/google') place(@Param('id', ParseIntPipe) id: number) { return this.google.place(id); }
}
