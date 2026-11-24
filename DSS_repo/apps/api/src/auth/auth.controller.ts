import { Body, Controller, Get, Headers, HttpCode, Post, Res } from '@nestjs/common';
import { LoginDto, RegisterDto } from '../dto';
import { Store } from '../store';
import { AuthService } from './auth.service';
import { sessionCookie } from './session';

type Reply = { header(name: string, value: string): unknown };

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService, private readonly store: Store) {}

  @Post('register') async register(@Body() dto: RegisterDto, @Res({ passthrough: true }) reply: Reply) {
    const account = await this.auth.register(dto);
    reply.header('Set-Cookie', sessionCookie(this.auth.token(account.id)));
    return { account };
  }

  @Post('login') @HttpCode(200) async login(@Body() dto: LoginDto, @Res({ passthrough: true }) reply: Reply) {
    const account = await this.auth.login(dto.username, dto.password);
    reply.header('Set-Cookie', sessionCookie(this.auth.token(account.id)));
    return { account };
  }

  @Post('logout') @HttpCode(200) logout(@Res({ passthrough: true }) reply: Reply) {
    reply.header('Set-Cookie', sessionCookie('', 0));
    return { ok: true };
  }

  @Get('me') async me(@Headers('cookie') cookie?: string) {
    return { account: await this.auth.require(cookie) };
  }

  /** Usernames of the seeded demo accounts, for the one-click demo buttons on the login page. */
  @Get('demo') async demo() { return this.store.demoAccounts(); }
}
