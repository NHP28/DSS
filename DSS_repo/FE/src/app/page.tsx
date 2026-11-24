'use client';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Compass, Sparkles } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import PlaceCard from '@/components/place-card';
import { api } from '@/lib/api';
import { count, DANANG, dayPart, modelNames, vietnamNow, weekdays, type Theme } from '@/lib/types';
import { useRecommendations } from '@/lib/use-recommendations';

const PoiMap = dynamic(() => import('@/components/poi-map'), { ssr: false });
const greeting = (hour: number) => hour < 5 ? 'Khuya rồi' : hour < 11 ? 'Chào buổi sáng' : hour < 14 ? 'Chào buổi trưa' : hour < 18 ? 'Chào buổi chiều' : 'Chào buổi tối';
const question = (hour: number) => hour < 5 ? 'giờ này còn đi đâu?' : hour < 10 ? 'sáng nay ăn gì, uống gì?' : hour < 14 ? 'trưa nay ăn ở đâu?' : hour < 18 ? 'chiều nay đi đâu chơi?' : 'tối nay đi đâu?';

export default function HomePage() {
  const { account, loading: authLoading } = useAuth();
  const [now, setNow] = useState<{ hour: number; dayOfWeek: number } | null>(null);
  const [themes, setThemes] = useState<Theme[] | null>(null);
  const [stats, setStats] = useState<{ pois: number; users: number; checkins: number } | null>(null);
  useEffect(() => {
    setNow(vietnamNow());
    api<Theme[]>('themes').then(setThemes).catch(() => setThemes([]));
    api<{ pois: number; users: number; checkins: number }>('stats').then(setStats).catch(() => {});
  }, []);
  const body = useMemo(() => now && !authLoading ? { ...DANANG, hour: now.hour, dayOfWeek: now.dayOfWeek, topK: 5, categories: ['restaurant', 'cafe', 'tourist_spot'] } : null, [now, authLoading]);
  const { result, error, reload } = useRecommendations('recommendations', body, [account?.id]);
  // Two best of each category, interleaved, so the strip shows variety.
  const picks = useMemo(() => (result?.groups || []).flatMap(group => group.items.slice(0, 2)).sort((a, b) => a.rank - b.rank).slice(0, 6), [result]);
  const hour = now?.hour ?? 8;
  const ordered = useMemo(() => themes && account ? [...themes].sort((a, b) => Number(account.interests.includes(b.slug)) - Number(account.interests.includes(a.slug))) : themes, [themes, account]);

  return <main className="wrap page">
    <section className="hero">
      <div className="rise">
        <span className="eyebrow">Đà Nẵng · {now ? `${String(hour).padStart(2, '0')}:00 ${weekdays[now.dayOfWeek]}` : 'hôm nay'}</span>
        <h1 style={{ marginTop: '1rem' }}>{greeting(hour)}{account ? `, ${account.displayName.split(/[ ·]/)[0]}` : ''} — <em>{question(hour)}</em></h1>
        <p className="lede">Gợi ý nơi ăn uống, cà phê, tham quan và lưu trú hợp với bạn, đúng giờ bạn cần. Mô hình đồ thị TAS-GNN học thói quen theo thời gian; AHP–TOPSIS cân thêm khoảng cách, giá và đánh giá.</p>
        <div className="row hero-actions">
          <Link href="/explore" className="btn coral"><Compass size={18} />Tìm quanh tôi</Link>
          {!account && !authLoading && <Link href="/login" className="btn ghost">Đăng nhập để nhận gợi ý riêng</Link>}
          {account && <Link href="/settings" className="btn ghost">Cài đặt mô hình</Link>}
        </div>
      </div>
      <div className="hero-map rise" style={{ ['--i' as string]: 2 }}>
        <PoiMap places={picks} latitude={DANANG.latitude} longitude={DANANG.longitude} interactive={false} />
        <div className="hero-stamp"><strong>{picks.length ? `${picks.length} gợi ý cho ${dayPart(hour)}` : 'Trung tâm Đà Nẵng'}</strong><br /><span className="muted">16.0678° B · 108.2208° Đ</span></div>
      </div>
    </section>

    <div className="stat-strip">
      {[[stats ? count(stats.pois) : '996', 'địa điểm từ OpenStreetMap'], [stats ? count(stats.users) : '1.500', 'người dùng mô phỏng'], [stats ? count(stats.checkins) : '36.210', 'lượt check-in có giờ'], ['9', 'phương pháp được so sánh']]
        .map(([value, label]) => <div key={label}><strong className="num">{value}</strong><span>{label}</span></div>)}
    </div>

    <section className="section">
      <div className="row between"><div><span className="eyebrow">Chủ đề du lịch</span><h2 style={{ marginTop: '.6rem' }}>Bạn đang tìm <em>điều gì?</em></h2></div></div>
      <div className="theme-grid" style={{ marginTop: '1.5rem' }}>
        {ordered === null ? Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton" style={{ height: 178, borderRadius: 18 }} />)
          : ordered.length === 0 ? <div className="notice" style={{ gridColumn: '1 / -1' }}>Chưa tải được danh sách chủ đề. Kiểm tra API đã chạy chưa.</div>
            : ordered.map((theme, index) => <Link key={theme.slug} href={`/themes/${theme.slug}`}
              className={`theme-tile rise${index === 0 ? ' feature' : ''}${account?.interests.includes(theme.slug) ? ' mine' : ''}`} style={{ ['--i' as string]: index }}>
              <span className="symbol" aria-hidden="true">{theme.symbol}</span>
              <span className={index === 0 ? 'badge sun count' : 'badge plain count'}>{count(theme.count || 0)} nơi</span>
              <h3>{theme.title}</h3><p>{theme.tagline}</p>
            </Link>)}
      </div>
    </section>

    <section className="section">
      <div className="row between">
        <div><span className="eyebrow">Ngay lúc này</span><h2 style={{ marginTop: '.6rem' }}>Gợi ý cho {account ? 'bạn' : 'khách mới'} <em>{dayPart(hour)}</em></h2></div>
        {result && <span className="badge"><Sparkles size={13} />{modelNames[result.source] || result.source} + TOPSIS</span>}
      </div>
      <div className="grid-2" style={{ marginTop: '1.5rem' }}>
        {error ? <div className="notice error" style={{ gridColumn: '1 / -1' }}><span><strong>Chưa tải được gợi ý.</strong> {error}</span><button onClick={() => void reload()}>Thử lại</button></div>
          : !result ? Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ height: 150 }} />)
            : picks.map(place => <PlaceCard key={place.id} place={place} showCategory hour={hour} origin={DANANG} />)}
      </div>
      {result && <p className="small muted" style={{ marginTop: '1rem' }}>
        {result.personalization === 'cold_start' ? (account ? `Thích thêm ${Math.max(0, result.minHistory - result.historyCount)} địa điểm để danh sách này thành của riêng bạn.` : 'Bạn đang xem bản dành cho khách: xếp theo độ phổ biến theo giờ.')
          : result.personalization === 'foldin' ? `Cá nhân hóa từ ${result.historyCount} địa điểm bạn đã chọn.` : 'Dựa trên lịch sử check-in của tài khoản demo.'}
        {' '}<Link className="link" href="/explore">Xem đầy đủ trên bản đồ <ArrowRight size={14} /></Link>
      </p>}
    </section>

    <section className="section grid-3">
      {[['/model', 'Mô hình', 'TAS-GNN hoạt động thế nào', 'Kiến trúc, thông số, cơ chế thời gian, ưu và nhược điểm.'],
        ['/evaluation', 'Đánh giá', 'So với machine learning truyền thống', 'HR@K, NDCG@K, MRR@K của 9 phương pháp trên cùng một giao thức.'],
        ['/data', 'Dữ liệu', 'Dataset và đồ thị tri thức Neo4j', 'Cấu trúc dữ liệu Đà Nẵng, bộ mẫu Gowalla và đồ thị 2.512 nút.']]
        .map(([href, eyebrow, title, text]) => <Link key={href} href={href} className="card flat" style={{ display: 'block' }}>
          <span className="eyebrow">{eyebrow}</span><h3 style={{ margin: '.8rem 0 .4rem' }}>{title}</h3><p className="muted small">{text}</p>
          <span className="link" style={{ marginTop: '.9rem' }}>Xem chi tiết <ArrowRight size={14} /></span></Link>)}
    </section>
  </main>;
}
