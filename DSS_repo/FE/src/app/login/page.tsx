'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ArrowRight, Info, RotateCw } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import { api } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { account, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [demo, setDemo] = useState<{ username: string; displayName: string }[]>([]);
  useEffect(() => { api<typeof demo>('auth/demo').then(setDemo).catch(() => {}); }, []);
  useEffect(() => { if (account) router.replace('/'); }, [account, router]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try { await login(username.trim().toLowerCase(), password); router.push('/'); }
    catch (problem) { setError((problem as Error).message); }
    finally { setBusy(false); }
  };
  return <main className="wrap page auth-shell">
    <section className="rise">
      <span className="eyebrow">Tài khoản</span>
      <h1 style={{ marginTop: '1rem' }}>Đăng nhập để Đà Nẵng <em>hiểu gu của bạn.</em></h1>
      <p className="lede" style={{ marginTop: '1rem' }}>Mỗi tài khoản có lịch sử và cài đặt mô hình riêng, nên cùng một giờ, hai người sẽ nhận hai danh sách khác nhau.</p>
      {demo.length > 0 && <div className="card flat" style={{ marginTop: '1.8rem' }}>
        <strong>Tài khoản demo có sẵn lịch sử</strong>
        <p className="small muted" style={{ margin: '.3rem 0 .9rem' }}>Bấm để điền tên đăng nhập. Mật khẩu demo là giá trị <code>DEMO_PASSWORD</code> trong <code>apps/api/.env</code>.</p>
        <div className="row">{demo.map(item => <button key={item.username} type="button" className="chip" aria-pressed={username === item.username}
          onClick={() => { setUsername(item.username); document.getElementById('password')?.focus(); }}>{item.displayName}</button>)}</div>
      </div>}
    </section>
    <form className="card stack rise" style={{ ['--i' as string]: 2 }} onSubmit={submit}>
      <h2 style={{ fontSize: '1.7rem' }}>Đăng nhập</h2>
      {error && <div className="notice error" role="alert"><Info size={18} /><span>{error}</span></div>}
      <label className="field">Tên đăng nhập<input autoComplete="username" required maxLength={30} value={username} onChange={event => setUsername(event.target.value)} /></label>
      <label className="field">Mật khẩu<input id="password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label>
      <button className="btn coral block" disabled={busy}>{busy ? <RotateCw size={18} className="spin" /> : null}{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}{!busy && <ArrowRight size={18} />}</button>
      <p className="small muted">Chưa có tài khoản? <Link className="link" href="/register">Đăng ký</Link> · <Link className="link" href="/explore">Tiếp tục với tư cách khách</Link></p>
    </form>
  </main>;
}
