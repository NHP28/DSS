'use client';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Clock3, Info, RotateCw, Search, Sparkles, UserRound } from 'lucide-react';
import { api } from '@/lib/api';
import { categories, categoryOrder, count, dayPart, modelNames, money, weekdays, type Place, type Recommendation } from '@/lib/types';
import { useAuth } from './auth-context';
import PlaceCard from './place-card';

const PoiMap = dynamic(() => import('./poi-map'), { ssr: false, loading: () => <div className="map-status">Đang tải bản đồ…</div> });
type Props = { result: Recommendation | null; loading: boolean; error: string; onRetry: () => void; onChanged?: () => void; emptyHint?: string };

/** One sentence that says where this ranking comes from, in the visitor's terms. */
function Personalization({ result }: { result: Recommendation }) {
  const { account } = useAuth();
  const model = modelNames[result.source] || result.source;
  if (result.personalization === 'trained_user') return <><UserRound size={16} /><span><strong>Riêng cho bạn</strong> · {model} dùng lịch sử check-in của tài khoản demo này.</span></>;
  if (result.personalization === 'foldin') return <><Sparkles size={16} /><span><strong>Cá nhân hóa từ {result.historyCount} địa điểm bạn đã chọn</strong> · {model} (xấp xỉ, chưa đánh giá offline).</span></>;
  if (!account) return <><Info size={16} /><span>Bạn đang xem với tư cách khách: xếp theo độ phổ biến theo giờ. <Link className="link" href="/login">Đăng nhập</Link> để nhận gợi ý riêng.</span></>;
  const missing = Math.max(0, result.minHistory - result.historyCount);
  return <><Info size={16} /><span>{missing > 0 ? <>Thích hoặc đánh dấu đã ghé thêm <strong>{missing} địa điểm</strong> để nhận gợi ý riêng. Hiện xếp theo độ phổ biến theo giờ.</> : 'Đang xếp theo độ phổ biến theo giờ.'}</span></>;
}

export default function ResultsView({ result, loading, error, onRetry, onChanged, emptyHint }: Props) {
  const { account } = useAuth();
  const [tab, setTab] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [pending, setPending] = useState<number | null>(null);
  const [toast, setToast] = useState('');
  // Local copy of saved/visited flags so a tap answers immediately.
  const [flags, setFlags] = useState<Record<number, { saved?: boolean; visited?: boolean }>>({});
  useEffect(() => { setFlags({}); setSelected(null); }, [result]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 4500); return () => clearTimeout(timer); }, [toast]);

  const groups = useMemo(() => [...(result?.groups || [])].sort((a, b) => categoryOrder.indexOf(a.category) - categoryOrder.indexOf(b.category)), [result]);
  useEffect(() => { if (tab && !groups.some(group => group.category === tab)) setTab(''); }, [groups, tab]);
  const term = search.trim().toLocaleLowerCase('vi');
  const visible = groups.filter(group => !tab || group.category === tab)
    .map(group => ({ ...group, items: group.items.map(place => ({ ...place, ...flags[place.id] })).filter(place => !term || `${place.name} ${place.district}`.toLocaleLowerCase('vi').includes(term)) }))
    .filter(group => group.items.length);
  const places: Place[] = visible.flatMap(group => group.items);

  const feedback = async (place: Place, action: 'like' | 'unlike' | 'visit' | 'unvisit') => {
    if (!account) { setToast('Đăng nhập để lưu địa điểm và nhận gợi ý riêng.'); return; }
    setPending(place.id);
    try {
      await api('feedback', { poiId: place.id, action });
      setFlags(previous => ({ ...previous, [place.id]: { saved: action === 'like' ? true : action === 'unlike' ? false : place.saved, visited: action === 'visit' ? true : action === 'unvisit' ? false : place.visited } }));
      setToast(action === 'like' ? `Đã thích ${place.name}.` : action === 'visit' ? `Đã ghi nhận bạn từng ghé ${place.name}.` : 'Đã cập nhật.');
      onChanged?.();
    } catch (problem) { setToast((problem as Error).message); }
    finally { setPending(null); }
  };
  const select = (id: number) => { setSelected(id); document.getElementById(`place-${id}`)?.scrollIntoView({ block: 'nearest' }); };

  if (error) return <div className="notice error" role="alert"><Info size={18} /><span><strong>Chưa tải được gợi ý.</strong> {error}</span><button onClick={onRetry}>Thử lại</button></div>;
  if (!result) return <div className="results"><div className="results-list">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ height: 132 }} />)}</div><div className="map-panel skeleton" /></div>;
  const query = result.query;
  return <div className="stack" aria-busy={loading}>
    <div className="context-bar">
      <Personalization result={result} />
    </div>
    {result.warning && <div className="notice"><Info size={18} /><span>{result.warning}</span></div>}
    <div className="row between">
      <div className="row small muted">
        <span className="badge plain"><Clock3 size={13} />{String(query.hour).padStart(2, '0')}:00 · {dayPart(query.hour)} · {weekdays[query.dayOfWeek]}</span>
        <span className="badge plain">Trong {query.radiusKm} km</span>
        {query.maxPrice !== null && <span className="badge plain">Tối đa {money(query.maxPrice)}</span>}
        <span className="badge">{modelNames[result.source] || result.source} + TOPSIS</span>
        {result.source.startsWith('tas_gnn') && <span className={result.useTime ? 'badge coral' : 'badge plain'}>{result.useTime ? 'Có ngữ cảnh thời gian' : 'Đã tắt thời gian'}</span>}
        {loading && <span className="badge sun"><RotateCw size={13} className="spin" />Đang cập nhật</span>}
      </div>
      <label className="row" style={{ gap: '.4rem' }}><Search size={16} className="muted" /><span className="sr-only">Tìm trong kết quả</span>
        <input className="input" style={{ width: 220, padding: '.5rem .8rem' }} placeholder="Tìm tên hoặc quận…" value={search} onChange={event => setSearch(event.target.value)} /></label>
    </div>
    {groups.length > 1 && <div className="tabs" role="tablist" aria-label="Danh mục">
      <button role="tab" aria-selected={tab === ''} className="chip" onClick={() => setTab('')}>Tất cả <span className="num">{count(result.totalCandidates)}</span></button>
      {groups.map(group => <button role="tab" key={group.category} aria-selected={tab === group.category} className="chip" onClick={() => setTab(group.category)}>
        {categories[group.category]?.symbol} {categories[group.category]?.label} <span className="num">{count(group.total)}</span></button>)}
    </div>}
    {!places.length ? <div className="empty"><Search size={30} /><h3>Chưa có địa điểm phù hợp</h3>
      <p>{term ? 'Không có kết quả khớp từ khóa. Thử từ khác.' : emptyHint || 'Thử tăng bán kính, đổi giờ hoặc bỏ giới hạn ngân sách.'}</p></div>
      : <div className="results">
        <div className="results-list">
          {visible.map(group => <section key={group.category} aria-label={categories[group.category]?.label}>
            {visible.length > 1 && <h3 className="group-title">{categories[group.category]?.symbol} {categories[group.category]?.label}<small>{group.items.length} gợi ý hàng đầu trong {count(group.total)} nơi phù hợp</small></h3>}
            <div className="results-list" style={{ marginTop: '.6rem' }}>{group.items.map((place, index) => <div key={place.id} className="rise" style={{ ['--i' as string]: Math.min(index, 6) }}>
              <PlaceCard place={place} hour={query.hour} origin={query} selected={selected === place.id} busy={pending === place.id}
                onSelect={() => setSelected(place.id)} onFeedback={action => void feedback(place, action)} /></div>)}</div>
          </section>)}
          <p className="small muted" style={{ marginTop: '.5rem' }}>Thứ hạng tính riêng trong từng danh mục: giá khách sạn và giá cà phê không so được với nhau. Giá, đánh giá và check-in là dữ liệu mô phỏng, cần kiểm tra lại trước khi đến.</p>
        </div>
        <div className="map-panel"><PoiMap places={places} selected={selected} onSelect={select} latitude={query.latitude} longitude={query.longitude} /></div>
      </div>}
    {toast && <div className="toast" role="status">{toast}{!account && <Link href="/login" className="link" style={{ color: 'var(--sun)' }}>Đăng nhập</Link>}</div>}
  </div>;
}
