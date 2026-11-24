'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ArrowRight, Info, RotateCw } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import { api } from '@/lib/api';
import type { Theme } from '@/lib/types';

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [themes, setThemes] = useState<Theme[]>([]);
  const [form, setForm] = useState({ displayName: '', username: '', password: '' });
  const [interests, setInterests] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { api<Theme[]>('themes').then(setThemes).catch(() => setError('Chưa tải được danh sách chủ đề. Kiểm tra API đã chạy chưa.')); }, []);
  const toggle = (slug: string) => setInterests(previous => previous.includes(slug) ? previous.filter(item => item !== slug) : [...previous, slug]);
  const usernameOk = /^[a-z0-9_]{3,30}$/.test(form.username);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!interests.length) return setError('Chọn ít nhất một chủ đề bạn thích.');
    setBusy(true); setError('');
    try { await register({ ...form, displayName: form.displayName.trim(), interests }); router.push('/'); }
    catch (problem) { setError((problem as Error).message); }
    finally { setBusy(false); }
  };
  return <main className="wrap page auth-shell">
    <section className="rise">
      <span className="eyebrow">Tạo tài khoản</span>
      <h1 style={{ marginTop: '1rem' }}>Kể cho chúng tôi <em>bạn thích gì.</em></h1>
      <p className="lede" style={{ marginTop: '1rem' }}>Tài khoản mới chưa có lịch sử, nên ban đầu bạn sẽ thấy gợi ý theo độ phổ biến. Sau khi bạn thích hoặc đánh dấu đã ghé <strong>3 địa điểm</strong>, mô hình sẽ dựng hồ sơ sở thích từ chính những nơi đó.</p>
    </section>
    <form className="card stack rise" style={{ ['--i' as string]: 2 }} onSubmit={submit}>
      <h2 style={{ fontSize: '1.7rem' }}>Đăng ký</h2>
      {error && <div className="notice error" role="alert"><Info size={18} /><span>{error}</span></div>}
      <label className="field">Tên hiển thị<input required maxLength={60} autoComplete="name" value={form.displayName} onChange={event => setForm({ ...form, displayName: event.target.value })} /></label>
      <label className="field">Tên đăng nhập<input required maxLength={30} autoComplete="username" value={form.username} aria-invalid={!!form.username && !usernameOk}
        onChange={event => setForm({ ...form, username: event.target.value.toLowerCase() })} />
        <span className="hint">3–30 ký tự: chữ thường không dấu, số hoặc dấu gạch dưới.</span></label>
      <label className="field">Mật khẩu<input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} />
        <span className="hint">Ít nhất 8 ký tự.</span></label>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="field" style={{ marginBottom: '.5rem' }}>Chủ đề bạn thích (chọn ít nhất một)</legend>
        <div className="row">{themes.map(theme => <button key={theme.slug} type="button" className="chip" aria-pressed={interests.includes(theme.slug)} onClick={() => toggle(theme.slug)}>{theme.symbol} {theme.title}</button>)}</div>
      </fieldset>
      <button className="btn coral block" disabled={busy || !usernameOk || form.password.length < 8}>{busy ? <RotateCw size={18} className="spin" /> : null}{busy ? 'Đang tạo…' : 'Tạo tài khoản'}{!busy && <ArrowRight size={18} />}</button>
      <p className="small muted">Đã có tài khoản? <Link className="link" href="/login">Đăng nhập</Link></p>
    </form>
  </main>;
}
