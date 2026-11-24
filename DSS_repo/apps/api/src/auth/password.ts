import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto';

const N = 16384, KEY_LENGTH = 64;
const derive = (password: string, salt: Buffer, n: number) => new Promise<Buffer>((resolve, reject) =>
  scrypt(password.normalize('NFKC'), salt, KEY_LENGTH, { N: n }, (error, key) => error ? reject(error) : resolve(key)));

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  return `scrypt$${N}$${salt.toString('base64')}$${(await derive(password, salt, N)).toString('base64')}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const [scheme, n, salt, hash] = stored.split('$');
  if (scheme !== 'scrypt' || !salt || !hash || Number(n) !== N) return false;
  const expected = Buffer.from(hash, 'base64');
  const actual = await derive(password, Buffer.from(salt, 'base64'), N);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
