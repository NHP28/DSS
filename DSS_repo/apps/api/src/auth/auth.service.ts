import { BadRequestException, ConflictException, HttpException, Injectable, UnauthorizedException } from '@nestjs/common';
import { AccountRow, Store } from '../store';
import { THEMES } from '../themes';
import { hashPassword, verifyPassword } from './password';
import { cookieValue, readSession, SESSION_COOKIE, SESSION_SECONDS, signSession } from './session';

export interface Account { id: number; username: string; displayName: string; datasetUserId: number | null; interests: string[] }
const MAX_FAILURES = 10, WINDOW_MS = 15 * 60 * 1000;
const publicAccount = ({ passwordHash: _hash, ...account }: AccountRow): Account => account;

@Injectable()
export class AuthService {
  private readonly failures = new Map<string, { count: number; first: number }>();
  constructor(private readonly store: Store) {}

  private secret(): string {
    const secret = process.env.AUTH_SECRET;
    // The value shipped in .env.example is public: anyone could sign a session with it.
    if (!secret || secret.length < 32 || secret.startsWith('doi-chuoi-nay')) throw new HttpException('Máy chủ chưa cấu hình AUTH_SECRET (tối thiểu 32 ký tự).', 500);
    return secret;
  }

  token(accountId: number) {
    return signSession({ accountId, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS }, this.secret());
  }

  /** Account of the request's session cookie, or null for guests and invalid/expired cookies. */
  async current(cookieHeader: string | undefined): Promise<Account | null> {
    const token = cookieValue(cookieHeader, SESSION_COOKIE);
    if (!token) return null; // guests never need the signing key
    const session = readSession(token, this.secret());
    if (!session) return null;
    const account = await this.store.accountById(session.accountId);
    return account ? publicAccount(account) : null;
  }

  async require(cookieHeader: string | undefined): Promise<Account> {
    const account = await this.current(cookieHeader);
    if (!account) throw new UnauthorizedException('Bạn cần đăng nhập để dùng chức năng này.');
    return account;
  }

  async register(input: { username: string; displayName: string; password: string; interests: string[] }): Promise<Account> {
    const interests = [...new Set(input.interests)];
    if (interests.some(slug => !THEMES.some(theme => theme.slug === slug))) throw new BadRequestException('Chủ đề yêu thích không hợp lệ.');
    const created = await this.store.createAccount({ username: input.username, displayName: input.displayName.trim(),
      passwordHash: await hashPassword(input.password), interests });
    if (!created) throw new ConflictException('Tên đăng nhập đã được dùng.');
    return publicAccount(created);
  }

  async login(username: string, password: string): Promise<Account> {
    // One counter per account however the name is typed ("Demo_Cafe ", "DEMO_CAFE").
    username = username.trim().toLowerCase();
    const now = Date.now();
    if (this.failures.size > 5000) for (const [key, value] of this.failures) if (now - value.first > WINDOW_MS) this.failures.delete(key);
    const record = this.failures.get(username);
    if (record && now - record.first > WINDOW_MS) this.failures.delete(username);
    const current = this.failures.get(username) || { count: 0, first: now };
    if (current.count >= MAX_FAILURES) throw new HttpException('Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.', 429);
    // Count the attempt before the slow hash check so parallel guesses cannot all slip through.
    this.failures.set(username, { count: current.count + 1, first: current.first });
    const account = await this.store.accountByUsername(username);
    // Verify against a fixed hash when the user is unknown so timing does not reveal usernames.
    const valid = await verifyPassword(password, account?.passwordHash || 'scrypt$16384$AAAAAAAAAAAAAAAAAAAAAA==$AA==');
    if (!account || !valid) throw new UnauthorizedException('Tên đăng nhập hoặc mật khẩu không đúng.');
    this.failures.delete(username);
    return publicAccount(account);
  }
}
