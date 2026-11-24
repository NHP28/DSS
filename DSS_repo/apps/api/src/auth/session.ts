import { createHmac, timingSafeEqual } from 'node:crypto';

export const SESSION_COOKIE = 'dss_session';
export const SESSION_SECONDS = 7 * 24 * 3600;
const sign = (payload: string, secret: string) => createHmac('sha256', secret).update(payload).digest('base64url');

export function signSession(session: { accountId: number; exp: number }, secret: string): string {
  const payload = Buffer.from(JSON.stringify(session)).toString('base64url');
  return `${payload}.${sign(payload, secret)}`;
}

export function readSession(token: string | undefined, secret: string): { accountId: number } | null {
  if (!token) return null;
  const [payload, signature, extra] = token.split('.');
  if (!payload || !signature || extra !== undefined) return null;
  const expected = Buffer.from(sign(payload, secret)), given = Buffer.from(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    if (!Number.isInteger(data.accountId) || typeof data.exp !== 'number' || data.exp * 1000 < Date.now()) return null;
    return { accountId: data.accountId };
  } catch { return null; }
}

export function cookieValue(header: string | undefined, name: string): string | undefined {
  for (const part of (header || '').split(';')) {
    const index = part.indexOf('=');
    if (index > 0 && part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return undefined;
}

export const sessionCookie = (token: string, maxAge = SESSION_SECONDS) =>
  `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${process.env.COOKIE_SECURE === 'true' ? '; Secure' : ''}`;
