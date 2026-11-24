'use client';
import { useEffect, useMemo, useState } from 'react';
import { LocateFixed, Search, SlidersHorizontal } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import ResultsView from '@/components/results-view';
import { api } from '@/lib/api';
import { categories, categoryOrder, DANANG, dayPart, presets, vietnamNow, weekdays, type ModelSettings } from '@/lib/types';
import { useRecommendations } from '@/lib/use-recommendations';

type Form = { latitude: number; longitude: number; hour: number; dayOfWeek: number; category: string; radiusKm: number; maxPrice: string; preset: string; showHidden: boolean };
const budgets = [['', 'Không giới hạn'], ['50000', 'Dưới 50.000 đ'], ['100000', 'Dưới 100.000 đ'], ['300000', 'Dưới 300.000 đ'], ['1000000', 'Dưới 1.000.000 đ']];

export default function ExplorePage() {
  const { account, loading: authLoading } = useAuth();
  const [form, setForm] = useState<Form | null>(null);
  const [applied, setApplied] = useState<Form | null>(null);
  const [more, setMore] = useState(false);
  const [notice, setNotice] = useState('');
  // Start from the account's saved defaults, so the settings page visibly matters here.
  useEffect(() => {
    if (authLoading) return;
    const start = (settings?: ModelSettings) => {
      const initial: Form = { ...DANANG, ...vietnamNow(), category: '', radiusKm: settings?.radiusKm ?? 10, maxPrice: settings?.maxPrice ? String(settings.maxPrice) : '', preset: settings?.preset ?? 'balanced', showHidden: false };
      setForm(initial); setApplied(initial);
    };
    if (!account) return start();
    api<{ settings: ModelSettings }>('settings').then(data => start(data.settings)).catch(() => start());
  }, [account, authLoading]);

  const body = useMemo(() => applied && {
    latitude: applied.latitude, longitude: applied.longitude, hour: applied.hour, dayOfWeek: applied.dayOfWeek, radiusKm: applied.radiusKm, preset: applied.preset,
    ...(applied.category ? { category: applied.category } : {}), maxPrice: applied.maxPrice ? Number(applied.maxPrice) : null, ...(applied.showHidden ? { showHidden: true } : {}),
  }, [applied]);
  const { result, loading, error, reload } = useRecommendations('recommendations', body, [account?.id]);
  const change = <K extends keyof Form>(key: K, value: Form[K]) => setForm(previous => previous && { ...previous, [key]: value });
  const dirty = !!form && !!applied && JSON.stringify(form) !== JSON.stringify(applied);
  const locate = () => {
    if (!navigator.geolocation) return setNotice('Trình duyệt không hỗ trợ định vị.');
    navigator.geolocation.getCurrentPosition(position => {
      setForm(previous => previous && { ...previous, latitude: Number(position.coords.latitude.toFixed(5)), longitude: Number(position.coords.longitude.toFixed(5)) });
      setNotice('Đã lấy vị trí của bạn. Bấm Tìm địa điểm để cập nhật.');
    }, () => setNotice('Chưa lấy được vị trí. Đang dùng trung tâm Đà Nẵng.'), { timeout: 10000 });
  };

  return <main className="wrap page stack" style={{ ['--gap' as string]: '1.5rem' }}>
    <header><span className="eyebrow">Khám phá</span><h1 style={{ marginTop: '.8rem', fontSize: 'clamp(2rem,4vw,3rem)' }}>Tìm nơi hợp với bạn, <em>đúng lúc.</em></h1>
      <p className="lede" style={{ marginTop: '.7rem' }}>Đổi giờ để thấy gợi ý thay đổi: thứ hạng phụ thuộc cả thói quen theo thời gian lẫn khoảng cách, giá và đánh giá.</p></header>

    {form && <form className="card" onSubmit={event => { event.preventDefault(); setApplied(form); if (!dirty) void reload(); }}>
      <div className="filter-bar">
        <label className="field">Giờ đến<select value={form.hour} onChange={event => change('hour', Number(event.target.value))}>
          {Array.from({ length: 24 }, (_, hour) => <option key={hour} value={hour}>{String(hour).padStart(2, '0')}:00 · {dayPart(hour)}</option>)}</select></label>
        <label className="field">Ngày<select value={form.dayOfWeek} onChange={event => change('dayOfWeek', Number(event.target.value))}>
          {weekdays.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label>
        <label className="field">Loại địa điểm<select value={form.category} onChange={event => change('category', event.target.value)}>
          <option value="">Tất cả</option>{categoryOrder.map(key => <option key={key} value={key}>{categories[key].label}</option>)}</select></label>
        <label className="field">Ưu tiên<select value={form.preset} onChange={event => change('preset', event.target.value)}>
          {Object.entries(presets).filter(([key]) => key !== 'custom' || account).map(([key, label]) => <option key={key} value={key}>{label}{key === 'custom' ? ' (theo cài đặt)' : ''}</option>)}</select></label>
        <button className="btn coral" type="submit" disabled={loading}><Search size={18} />{loading ? 'Đang tìm…' : 'Tìm địa điểm'}</button>
      </div>
      <div className="row between" style={{ marginTop: '1rem' }}>
        <div className="row small muted"><button type="button" className="chip" onClick={locate}><LocateFixed size={15} />Dùng vị trí của tôi</button>
          <span className="num">{form.latitude.toFixed(4)}, {form.longitude.toFixed(4)}</span></div>
        <button type="button" className="chip" aria-expanded={more} onClick={() => setMore(!more)}><SlidersHorizontal size={15} />Bộ lọc thêm</button>
      </div>
      {more && <div className="grid-3" style={{ marginTop: '1rem' }}>
        <label className="field">Bán kính: {form.radiusKm} km<input type="range" min="1" max="30" step="1" value={form.radiusKm} onChange={event => change('radiusKm', Number(event.target.value))} /></label>
        <label className="field">Ngân sách<select value={form.maxPrice} onChange={event => change('maxPrice', event.target.value)}>{budgets.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="row" style={{ alignSelf: 'end', paddingBottom: '.7rem' }}><input type="checkbox" checked={form.showHidden} onChange={event => change('showHidden', event.target.checked)} />
          <span className="small">Hiện cả điểm ngắm cảnh có tên chưa rõ ràng</span></label>
      </div>}
      {notice && <p className="small muted" role="status" style={{ marginTop: '.8rem' }}>{notice}</p>}
      {dirty && <p className="small" role="status" style={{ marginTop: '.8rem', color: 'var(--warn-ink)' }}>Bộ lọc đã đổi; kết quả bên dưới vẫn là của lần tìm trước.</p>}
    </form>}

    <ResultsView result={result} loading={loading} error={error} onRetry={() => void reload()} onChanged={() => void reload()} />
  </main>;
}
