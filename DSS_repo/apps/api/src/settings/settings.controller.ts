import { BadRequestException, Body, Controller, Delete, Get, Headers, Put } from '@nestjs/common';
import { AuthService } from '../auth/auth.service';
import { Store } from '../store';
import { DEFAULT_SETTINGS, ModelSettings, parseSettings } from './settings';

@Controller('settings')
export class SettingsController {
  constructor(private readonly auth: AuthService, private readonly store: Store) {}

  @Get() async read(@Headers('cookie') cookie?: string) {
    const account = await this.auth.require(cookie);
    return { settings: { ...DEFAULT_SETTINGS, ...(await this.store.settings(account.id) || {}) }, defaults: DEFAULT_SETTINGS };
  }

  @Put() async save(@Body() body: Record<string, unknown>, @Headers('cookie') cookie?: string) {
    const account = await this.auth.require(cookie);
    let settings: ModelSettings;
    try { settings = parseSettings(body); } catch (error) { throw new BadRequestException((error as Error).message); }
    await this.store.saveSettings(account.id, settings);
    return { settings };
  }

  @Delete() async reset(@Headers('cookie') cookie?: string) {
    const account = await this.auth.require(cookie);
    await this.store.deleteSettings(account.id);
    return { settings: DEFAULT_SETTINGS };
  }
}
