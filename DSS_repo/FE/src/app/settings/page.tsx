'use client';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Check, Info, RotateCcw, Save, Settings2 } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import { api } from '@/lib/api';
import { categories, count, criteria, DANANG, modelNames, money, presets, vietnamNow, type ModelSettings, type Recommendation, type SystemStatus } from '@/lib/types';

const modelOptions: { key: ModelSettings['model']; note: string }[] = [
  { key: 'tas_gnn', note: 'Model chính: đồ thị + thời gian + không gian' },
  { key: 'lightgcn', note: 'Đối chứng: đồ thị tĩnh, không dùng thời gian' },
  { key: 'hourly_popularity', note: 'Không học: nơi đông nhất theo giờ' },
  { key: 'popularity', note: 'Không học: nơi đông nhất nói chung' },
];
const pools = [[0, 'Tất cả'], [20, 'Top 20'], [50, 'Top 50'], [100, 'Top 100']] as const;
const budgets = [[null, 'Không giới hạn'], [50000, '50.000 đ'], [100000, '100.000 đ'], [300000, '300.000 đ'], [1000000, '1.000.000 đ']] as const;

export default function SettingsPage() {
  const { account, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [saved, setSaved] = useState<ModelSettings | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [preview, setPreview] = useState<Recommendation | null>(null);
  const [previewError, setPreviewError] = useState('');
  const [message, setMessage] = useState<{ kind: 'info' | 'error'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [context] = useState(() => ({ ...DANANG, ...vietnamNow() }));

  useEffect(() => { api<SystemStatus>('system').then(setSystem).catch(() => setSystem({ database: false, graph: false, ai: { ready: false } })); }, []);
  useEffect(() => {
    if (!account) return;
    api<{ settings: ModelSettings }>('settings').then(data => { setSettings(data.settings); setSaved(data.settings); })
      .catch(problem => setMessage({ kind: 'error', text: (problem as Error).message }));
  }, [account]);

  const dirty = !!settings && !!saved && JSON.stringify(settings) !== JSON.stringify(saved);
  const total = settings ? settings.weightLevels.reduce((sum, level) => sum + level, 0) : 1;
  const key = useMemo(() => settings ? JSON.stringify(settings) : '', [settings]);
  // Live preview with the unsaved settings, so each control shows its effect before saving.
  useEffect(() => {
    if (!key) return;
    const current: ModelSettings = JSON.parse(key);
    const timer = setTimeout(() => {
      api<Recommendation>('recommendations', {
        ...context, categories: ['restaurant', 'cafe', 'tourist_spot'], topK: 5, model: current.model, useTime: current.useTime, candidatePool: current.candidatePool,
        radiusKm: current.radiusKm, excludeVisited: current.excludeVisited, maxPrice: current.maxPrice,
        ...(current.preset === 'custom' ? { matrix: current.weightLevels.map(a => current.weightLevels.map(b => a / b)) } : { preset: current.preset }),
      }).then(data => { setPreview(data); setPreviewError(''); }).catch(problem => setPreviewError((problem as Error).message));
    }, 400);
    return () => clearTimeout(timer);
  }, [key, context]);

  const change = <K extends keyof ModelSettings>(name: K, value: ModelSettings[K]) => { setSettings(previous => previous && { ...previous, [name]: value }); setMessage(null); };
  const save = async () => {
    if (!settings) return;
    setBusy(true);
    try { const data = await api<{ settings: ModelSettings }>('settings', settings, 'PUT'); setSaved(data.settings); setSettings(data.settings); setMessage({ kind: 'info', text: 'Đã lưu. Các trang gợi ý sẽ dùng cài đặt này.' }); }
    catch (problem) { setMessage({ kind: 'error', text: (problem as Error).message }); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { const data = await api<{ settings: ModelSettings }>('settings', undefined, 'DELETE'); setSaved(data.settings); setSettings(data.settings); setMessage({ kind: 'info', text: 'Đã khôi phục cài đặt mặc định.' }); }
    catch (problem) { setMessage({ kind: 'error', text: (problem as Error).message }); }
    finally { setBusy(false); }
  };

  if (authLoading) return <main className="wrap page"><div className="skeleton" style={{ height: 320 }} /></main>;
  if (!account) return <main className="wrap page"><div className="empty"><Settings2 size={34} /><h3>Đăng nhập để cài đặt mô hình</h3>
    <p>Cài đặt được lưu theo từng tài khoản: mô hình chấm điểm, ngữ cảnh thời gian, số gợi ý và trọng số ưu tiên.</p><Link href="/login" className="btn coral">Đăng nhập</Link></div></main>;
  const available = system?.ai.models || [];
  const info = system?.ai.info;
  const picks = (preview?.groups || []).flatMap(group => group.items.slice(0, 2)).sort((a, b) => a.rank - b.rank).slice(0, 5);

  return <main className="wrap page stack" style={{ ['--gap' as string]: '1.5rem' }}>
    <header className="row between">
      <div><span className="eyebrow">Cài đặt mô hình</span><h1 style={{ marginTop: '.8rem', fontSize: 'clamp(2rem,4vw,3rem)' }}>Điều chỉnh cách <em>gợi ý.</em></h1>
        <p className="lede" style={{ marginTop: '.6rem' }}>Lưu riêng cho tài khoản {account.displayName}. Khung bên phải cập nhật ngay khi bạn đổi cài đặt.</p></div>
      <div className="row"><button className="btn quiet" disabled={busy} onClick={() => void reset()}><RotateCcw size={16} />Khôi phục mặc định</button>
        <button className="btn coral" disabled={busy || !dirty} onClick={() => void save()}><Save size={16} />{dirty ? 'Lưu cài đặt' : 'Đã lưu'}</button></div>
    </header>
    {message && <div className={message.kind === 'error' ? 'notice error' : 'notice info'} role="status">{message.kind === 'error' ? <Info size={18} /> : <Check size={18} />}<span>{message.text}</span></div>}
    {!settings ? <div className="skeleton" style={{ height: 420 }} /> : <div className="settings-layout">
      <div className="stack" style={{ ['--gap' as string]: '1.25rem' }}>
        <section className="card flat stack">
          <h2 style={{ fontSize: '1.4rem' }}>1 · Mô hình chấm điểm sở thích</h2>
          <div className="option-grid" role="radiogroup" aria-label="Mô hình chấm điểm">{modelOptions.map(option => {
            const needsAi = option.key === 'tas_gnn' || option.key === 'lightgcn';
            const locked = needsAi && system !== null && !available.includes(option.key);
            return <button key={option.key} type="button" role="radio" className="option" aria-checked={settings.model === option.key} disabled={locked} onClick={() => change('model', option.key)}>
              <strong>{modelNames[option.key]}{option.key === 'tas_gnn' && <span className="badge coral" style={{ marginLeft: '.5rem' }}>Model chính</span>}</strong>
              <span>{locked ? 'Chưa nạp được: dịch vụ mô hình (cổng 8000) chưa chạy.' : option.note}</span></button>;
          })}</div>
          <label className="switch"><span><strong>Dùng ngữ cảnh thời gian</strong><br /><span className="small muted">Tắt để xem TAS-GNN xếp hạng thế nào khi bỏ giờ và thứ. Đây là tắt lúc suy luận, khác biến thể "bỏ thời gian" được huấn luyện riêng trong bảng ablation.</span></span>
            <input type="checkbox" checked={settings.useTime} disabled={settings.model !== 'tas_gnn'} onChange={event => change('useTime', event.target.checked)} /></label>
          <div><strong>Số ứng viên của mô hình đưa vào TOPSIS</strong><p className="small muted">Giữ N địa điểm có điểm sở thích cao nhất của mỗi danh mục (sau khi lọc), rồi mới xếp hạng đa tiêu chí.</p>
            <div className="row" style={{ marginTop: '.6rem' }}>{pools.map(([value, label]) => <button key={value} type="button" className="chip" aria-pressed={settings.candidatePool === value} onClick={() => change('candidatePool', value)}>{label}</button>)}</div></div>
        </section>

        <section className="card flat stack">
          <h2 style={{ fontSize: '1.4rem' }}>2 · Kết quả hiển thị</h2>
          <label className="field">Số gợi ý mỗi danh mục (Top-K): {settings.topK}<input type="range" min="5" max="20" value={settings.topK} onChange={event => change('topK', Number(event.target.value))} /></label>
          <label className="field">Bán kính mặc định: {settings.radiusKm} km<input type="range" min="1" max="30" value={settings.radiusKm} onChange={event => change('radiusKm', Number(event.target.value))} /></label>
          <div><strong>Ngân sách mặc định</strong><div className="row" style={{ marginTop: '.6rem' }}>{budgets.map(([value, label]) => <button key={label} type="button" className="chip" aria-pressed={settings.maxPrice === value} onClick={() => change('maxPrice', value)}>{label}</button>)}</div></div>
          <label className="switch"><span><strong>Ẩn nơi đã ghé</strong><br /><span className="small muted">Chỉ gợi ý địa điểm mới với bạn.</span></span>
            <input type="checkbox" checked={settings.excludeVisited} onChange={event => change('excludeVisited', event.target.checked)} /></label>
        </section>

        <section className="card flat stack">
          <h2 style={{ fontSize: '1.4rem' }}>3 · Điều gì quan trọng với bạn (AHP)</h2>
          <div className="row">{Object.entries(presets).map(([name, label]) => <button key={name} type="button" className="chip" aria-pressed={settings.preset === name} onClick={() => change('preset', name as ModelSettings['preset'])}>{label}</button>)}</div>
          {settings.preset === 'custom' ? <div className="stack">{criteria.map((label, index) => <label key={label} className="field">
            <span className="row between"><span>{label}</span><span className="num">{Math.round(settings.weightLevels[index] / total * 100)}%</span></span>
            <input type="range" min="1" max="9" value={settings.weightLevels[index]} aria-valuetext={`Mức ${settings.weightLevels[index]} trên 9`}
              onChange={event => change('weightLevels', settings.weightLevels.map((level, i) => i === index ? Number(event.target.value) : level))} /></label>)}
            <p className="small muted">Mỗi mức 1–9 được đổi thành ma trận so sánh cặp AHP (tỉ số hai mức). Ma trận dạng này luôn nhất quán, nên CR = 0.</p></div>
            : preview && <div className="bars">{criteria.map((label, index) => <div className="bar-row" key={label}><span className="label">{label}</span>
              <div className="track"><div className="fill" style={{ width: `${preview.weights[index] * 100}%` }} /></div><span className="value">{Math.round(preview.weights[index] * 100)}%</span></div>)}</div>}
        </section>
      </div>

      <aside className="settings-preview stack" style={{ ['--gap' as string]: '1.25rem' }}>
        <section className="card dark stack">
          <div className="row between"><strong>Xem trước · Top 5 lúc {String(context.hour).padStart(2, '0')}:00</strong>{dirty && <span className="badge sun">Chưa lưu</span>}</div>
          {previewError ? <p className="small">{previewError}</p> : !preview ? <div className="skeleton" style={{ height: 220, opacity: .25 }} /> : <>
            <p className="small muted">{modelNames[preview.source] || preview.source} + TOPSIS · {preview.personalization === 'cold_start' ? 'chưa cá nhân hóa' : preview.personalization === 'foldin' ? `từ ${preview.historyCount} nơi bạn chọn` : 'theo lịch sử demo'}
              {preview.source.startsWith('tas_gnn') && (preview.useTime ? ' · có thời gian' : ' · đã tắt thời gian')}</p>
            {preview.warning && <p className="small" style={{ color: 'var(--sun)' }}>{preview.warning}</p>}
            <ol style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '.6rem' }}>{picks.map(place => <li key={place.id}><strong>{place.name}</strong>
              <br /><span className="small muted">{categories[place.category]?.label} · {place.distanceKm.toFixed(1)} km · {money(place.price_avg)} · hợp sở thích {Math.round(place.preference * 100)}</span></li>)}</ol>
            {!picks.length && <p className="small">Không có địa điểm nào khớp cài đặt này. Thử tăng bán kính hoặc ngân sách.</p>}
          </>}
        </section>
        <section className="card flat stack">
          <strong>Trạng thái hệ thống</strong>
          {!system ? <div className="skeleton" style={{ height: 120 }} /> : <>
            <div className="small"><span className={`status-dot ${system.ai.ready ? 'on' : 'off'}`} />Dịch vụ mô hình: {system.ai.ready ? `đang chạy (${(system.ai.models || []).map(name => modelNames[name]).join(', ')})` : 'chưa chạy — đang dùng phương án dự phòng'}</div>
            <div className="small"><span className={`status-dot ${system.database ? 'on' : 'off'}`} />MySQL: {system.database ? 'đã kết nối' : 'chưa kết nối'}</div>
            <div className="small"><span className={`status-dot ${system.graph ? 'on' : 'off'}`} />Neo4j (đồ thị tri thức): {system.graph ? 'đã kết nối' : 'chưa bật — phần "vì sao gợi ý" sẽ ẩn'}</div>
            {info && <dl className="kv" style={{ marginTop: '.4rem' }}>
              <dt>Nguồn model</dt><dd>{system.ai.origin === 'repo_checkpoint' ? 'outputs/checkpoints' : 'Colab artifact'}</dd>
              <dt>Kích thước embedding</dt><dd>{info.embeddingDim}</dd>
              {info.timeDim && <><dt>Chiều vector thời gian</dt><dd>{info.timeDim}</dd></>}
              <dt>Số lớp lan truyền</dt><dd>{info.layers}</dd>
              {info.parameters && <><dt>Tham số TAS-GNN</dt><dd>{count(info.parameters)}</dd></>}
              {info.users && <><dt>Người dùng đã huấn luyện</dt><dd>{count(info.users)}</dd></>}
            </dl>}
            <p className="small muted">Kích thước embedding, số lớp và tốc độ học được chốt lúc huấn luyện trên Colab, nên chỉ xem được ở đây. <Link className="link" href="/model">Xem trang Mô hình</Link></p>
          </>}
        </section>
      </aside>
    </div>}
  </main>;
}
