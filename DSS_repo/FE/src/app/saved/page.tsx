'use client';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { Check, Heart, Info, MapPin, Star, Trash2, Wallet } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import { api } from '@/lib/api';
import { categories, money } from '@/lib/types';

type Poi = { id: number; name: string; category: string; district: string; rating: number; price_avg: number };
type Saved = { liked: Poi[]; visited: Poi[] };
const MIN_HISTORY = 3;

export default function SavedPage() {
  const { account, loading } = useAuth();
  const [saved, setSaved] = useState<Saved | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => { setError(''); api<Saved>('saved').then(setSaved).catch(problem => setError((problem as Error).message)); }, []);
  useEffect(() => { if (account) load(); }, [account, load]);
  const remove = async (poiId: number, action: 'unlike' | 'unvisit') => {
    try { await api('feedback', { poiId, action }); load(); } catch (problem) { setError((problem as Error).message); }
  };
  if (loading) return <main className="wrap page"><div className="skeleton" style={{ height: 240 }} /></main>;
  if (!account) return <main className="wrap page"><div className="empty"><Heart size={34} /><h3>Đăng nhập để xem địa điểm đã lưu</h3>
    <p>Những nơi bạn thích và đã ghé được lưu theo tài khoản, và là dữ liệu để mô hình cá nhân hóa gợi ý.</p><Link href="/login" className="btn coral">Đăng nhập</Link></div></main>;
  const distinct = new Set([...(saved?.liked || []), ...(saved?.visited || [])].map(poi => poi.id)).size;
  const list = (title: string, icon: React.ReactNode, items: Poi[], action: 'unlike' | 'unvisit', empty: string) => <section className="card flat">
    <h2 style={{ fontSize: '1.5rem' }} className="row">{icon}{title} <span className="badge plain num">{items.length}</span></h2>
    {items.length === 0 ? <p className="muted" style={{ marginTop: '.8rem' }}>{empty}</p> : <div className="stack" style={{ marginTop: '1rem', ['--gap' as string]: '.6rem' }}>
      {items.map(poi => <div key={poi.id} className="place" style={{ gridTemplateColumns: 'minmax(0,1fr) auto', ['--cat' as string]: `var(--${poi.category})` }}>
        <div><h3>{poi.name}</h3><div className="place-meta"><span>{categories[poi.category]?.symbol} {categories[poi.category]?.label}</span><span><MapPin size={14} />{poi.district}</span>
          <span className="star"><Star size={14} fill="currentColor" />{poi.rating.toFixed(1)}</span><span><Wallet size={14} />{money(poi.price_avg)}</span></div></div>
        <button className="icon-btn" aria-label={`Bỏ ${poi.name} khỏi danh sách`} title="Bỏ khỏi danh sách" onClick={() => void remove(poi.id, action)}><Trash2 size={16} /></button>
      </div>)}</div>}
  </section>;
  return <main className="wrap page stack" style={{ ['--gap' as string]: '1.5rem' }}>
    <header><span className="eyebrow">Của {account.displayName}</span><h1 style={{ marginTop: '.8rem', fontSize: 'clamp(2rem,4vw,3rem)' }}>Địa điểm <em>đã lưu.</em></h1></header>
    {error && <div className="notice error" role="alert"><Info size={18} /><span>{error}</span><button onClick={load}>Thử lại</button></div>}
    {account.datasetUserId !== null ? <div className="notice info"><Info size={18} /><span>Đây là tài khoản demo: gợi ý dùng lịch sử check-in có sẵn trong dữ liệu. Những nơi bạn lưu thêm ở đây chỉ dùng để ẩn nơi đã ghé và giải thích gợi ý.</span></div>
      : saved && <div className={distinct >= MIN_HISTORY ? 'notice info' : 'notice'}><Info size={18} /><span>{distinct >= MIN_HISTORY
        ? <>Mô hình đang cá nhân hóa gợi ý từ <strong>{distinct} địa điểm</strong> dưới đây.</>
        : <>Bạn đã chọn <strong>{distinct}/{MIN_HISTORY}</strong> địa điểm. Chọn đủ {MIN_HISTORY} nơi để nhận gợi ý riêng. <Link className="link" href="/explore">Đi khám phá</Link></>}</span></div>}
    {!saved && !error ? <div className="skeleton" style={{ height: 240 }} /> : saved && <div className="grid-2" style={{ alignItems: 'start' }}>
      {list('Yêu thích', <Heart size={22} color="var(--coral)" />, saved.liked, 'unlike', 'Bấm biểu tượng trái tim ở một địa điểm để lưu vào đây.')}
      {list('Đã ghé', <Check size={22} color="var(--ok)" />, saved.visited, 'unvisit', 'Đánh dấu "đã ghé" để ẩn nơi đó khỏi các gợi ý sau.')}
    </div>}
  </main>;
}
