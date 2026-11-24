'use client';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Check, Info, Minus } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import { api } from '@/lib/api';
import { categories, count, DANANG, dayPart, modelNames, type Place, type Recommendation, type SystemStatus } from '@/lib/types';

// Fallback when the model service is off: counted from outputs/checkpoints/temporal_gnn_danang.pt.
const BLOCKS: Record<string, number> = { userEmbedding: 96000, poiEmbedding: 63744, timeEncoder: 8384, temporalGate: 8256, spatialEncoder: 4352, categoryEmbedding: 256 };
const blockNames: [string, string, string][] = [
  ['userEmbedding', 'Embedding người dùng', '1.500 × 64'], ['poiEmbedding', 'Embedding địa điểm', '996 × 64'],
  ['timeEncoder', 'Bộ mã hóa thời gian + 2 phép chiếu', 'Fourier 16 tần số, giờ 24×32, thứ 7×32, MLP'],
  ['temporalGate', 'Cổng thời gian', 'Linear 128 → 64 + sigmoid'], ['spatialEncoder', 'Bộ mã hóa không gian', 'MLP 2 → 64 → 64 trên (vĩ độ, kinh độ)'],
  ['categoryEmbedding', 'Embedding danh mục', '4 × 64'],
];
const hyper: [string, string][] = [
  ['Kích thước embedding', '64'], ['Chiều vector thời gian', '32'], ['Số lớp lan truyền đồ thị', '3 (lấy trung bình 4 tầng biểu diễn)'],
  ['Hàm mất mát', 'BPR + L2 (hệ số 1e-4)'], ['Tối ưu', 'Adam, tốc độ học 0,005'], ['Batch', '1.024 bộ ba (người dùng, địa điểm dương, địa điểm âm)'],
  ['Mẫu âm', '1 địa điểm ngẫu nhiên cho mỗi check-in'], ['Số epoch', '15'], ['Chia dữ liệu', '70% huấn luyện · 10% tinh chỉnh · 20% kiểm tra, theo thời gian từng người'],
  ['Môi trường huấn luyện', 'Google Colab (GPU T4), PyTorch'],
];
const pros = [
  'Một mô hình gộp ba nguồn tín hiệu: ai đã ghé đâu (đồ thị), ghé lúc nào (thời gian), địa điểm nằm ở đâu và thuộc loại gì (không gian, danh mục).',
  'Cùng một người, gợi ý thay đổi theo giờ và thứ nhờ cổng thời gian; LightGCN thì cho cùng một danh sách cả ngày.',
  'Nhẹ: khoảng 181 nghìn tham số, chấm điểm toàn bộ 996 địa điểm trong vài mili-giây trên CPU.',
  'Địa điểm ít tương tác vẫn có biểu diễn hợp lý nhờ tọa độ và danh mục.',
  'Tài khoản mới được cá nhân hóa ngay từ vài địa điểm đã chọn, không cần huấn luyện lại.',
];
const cons = [
  'Không mô hình hóa chuỗi di chuyển: không biết bạn vừa ở đâu. Heuristic "giờ × khoảng cách liền trước" nhờ thông tin đó mà đạt HR@10 cao hơn.',
  'Gradient Boosting dùng đặc trưng thủ công (khoảng cách tới vùng hoạt động, độ phổ biến theo giờ) cũng nhỉnh hơn trên dữ liệu Đà Nẵng.',
  'Check-in huấn luyện là dữ liệu mô phỏng; trên Gowalla (check-in thật) phần thời gian không cải thiện kết quả.',
  'Lúc suy luận, thời gian chỉ tác động qua phía người dùng: số hạng phía địa điểm cộng cùng một vector cho mọi địa điểm nên không đổi thứ hạng.',
  'Khách sạn không có check-in huấn luyện; người dùng hoàn toàn mới phải dựa vào độ phổ biến theo giờ.',
  'Mẫu âm lấy ngẫu nhiên đều, có thể trùng nơi người dùng đã ghé; chưa có dừng sớm theo tập tinh chỉnh.',
];

export default function ModelPage() {
  const { account } = useAuth();
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [hour, setHour] = useState(8);
  const [useTime, setUseTime] = useState(true);
  const [demo, setDemo] = useState<Recommendation | null>(null);
  const [demoError, setDemoError] = useState('');
  useEffect(() => { api<SystemStatus>('system').then(setSystem).catch(() => {}); }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      api<Recommendation>('recommendations', { ...DANANG, hour, dayOfWeek: 2, radiusKm: 30, topK: 20, model: 'tas_gnn', useTime, preset: 'ai_centric', excludeVisited: false, categories: ['cafe', 'restaurant', 'tourist_spot'] })
        .then(data => { setDemo(data); setDemoError(''); }).catch(problem => setDemoError((problem as Error).message));
    }, 250);
    return () => clearTimeout(timer);
  }, [hour, useTime, account?.id]);
  const blocks = system?.ai.info?.blocks || BLOCKS;
  const total = Object.values(blocks).reduce((sum, value) => sum + value, 0);
  // Which categories the model itself prefers right now: its 10 highest preference scores.
  const top = useMemo(() => (demo?.groups || []).flatMap(group => group.items).sort((a, b) => b.preference - a.preference).slice(0, 10), [demo]);
  const mix = useMemo(() => ['cafe', 'restaurant', 'tourist_spot'].map(key => ({ key, n: top.filter((place: Place) => place.category === key).length })), [top]);
  const personal = demo && demo.personalization !== 'cold_start';

  return <main className="wrap page stack" style={{ ['--gap' as string]: '2.5rem' }}>
    <header><span className="eyebrow">Mô hình</span>
      <h1 style={{ marginTop: '.8rem' }}>TAS-GNN: đồ thị biết <em>mấy giờ rồi.</em></h1>
      <p className="lede" style={{ marginTop: '.8rem' }}>Time-Aware Spatial Graph Neural Network. Mô hình chính của hệ thống: lan truyền trên đồ thị người dùng–địa điểm, rồi điều chỉnh sở thích theo thời điểm truy vấn. LightGCN (đồ thị tĩnh) là mô hình đối chứng.</p></header>

    <section className="card stack">
      <h2>Kiến trúc</h2>
      <div className="arch">
        <div className="arch-label">Đầu vào</div>
        <div className="arch-box graph"><strong>Đồ thị người dùng – địa điểm</strong>cạnh = đã từng ghé<br /><code>phần VISITED của đồ thị tri thức</code></div>
        <div className="arch-box time"><strong>Thời điểm truy vấn</strong>timestamp, giờ (0–23), thứ (0–6)</div>
        <div className="arch-box"><strong>Tọa độ địa điểm</strong>vĩ độ, kinh độ</div>
        <div className="arch-box"><strong>Danh mục địa điểm</strong>cà phê, nhà hàng, khách sạn, tham quan</div>
        <div className="arch-label">Mã hóa</div>
        <div className="arch-box graph"><strong>3 lớp lan truyền kiểu LightGCN</strong>ma trận kề chuẩn hóa đối xứng, trung bình các tầng<br /><code>e_u , e_i ∈ ℝ⁶⁴</code></div>
        <div className="arch-box time"><strong>Bộ mã hóa thời gian</strong>Fourier học được + embedding giờ + embedding thứ → MLP<br /><code>τ ∈ ℝ³²</code></div>
        <div className="arch-box"><strong>MLP không gian</strong>2 → 64 → 64<br /><code>s_i ∈ ℝ⁶⁴</code></div>
        <div className="arch-box"><strong>Embedding danh mục</strong>4 × 64<br /><code>c_i ∈ ℝ⁶⁴</code></div>
        <div className="arch-label">Kết hợp</div>
        <div className="arch-box time" style={{ gridColumn: 'span 2' }}><strong>Cổng thời gian phía người dùng</strong>quyết định từng chiều sở thích nhận bao nhiêu ngữ cảnh thời gian<br /><code>e_u(t) = e_u + σ(W_g[e_u ‖ W_u τ]) ⊙ W_u τ</code></div>
        <div className="arch-box" style={{ gridColumn: 'span 2' }}><strong>Biểu diễn địa điểm</strong>cộng đồ thị, không gian, danh mục và ngữ cảnh thời gian<br /><code>e_i(t) = e_i + s_i + c_i + W_i τ</code></div>
        <div className="arch-label">Đầu ra</div>
        <div className="arch-box out" style={{ gridColumn: '1 / -1' }}><strong>Điểm sở thích = e_u(t) · e_i(t)</strong>xếp hạng 996 địa điểm → tiêu chí C4 "Hợp sở thích" của TOPSIS, bên cạnh khoảng cách, đánh giá, chi phí và độ phổ biến<br /><code>src/models/temporal_gnn.py · phục vụ qua ml/repo_models.py</code></div>
      </div>
    </section>

    <section className="stack">
      <div><span className="eyebrow">Cơ chế thông tin thời gian</span><h2 style={{ marginTop: '.6rem' }}>Thời gian đi vào mô hình <em>bằng ba bước</em></h2></div>
      <div className="grid-3">
        <div className="card flat stack"><span className="badge coral">Bước 1</span><h3>Mã hóa thời điểm</h3>
          <p className="small">Timestamp liên tục qua 16 tần số Fourier có tham số học được, bắt các chu kỳ dài ngắn khác nhau. Giờ trong ngày và thứ trong tuần qua hai bảng embedding rời rạc.</p>
          <div className="formula">Φ(t) = [cos(ω·t/86400 + b), sin(ω·t/86400 + b)]</div>
          <div className="formula">τ = MLP([Φ(t) ‖ E_giờ(h) + E_thứ(w)])</div></div>
        <div className="card flat stack"><span className="badge coral">Bước 2</span><h3>Cổng thời gian</h3>
          <p className="small">Một cổng sigmoid nhìn cả sở thích tĩnh lẫn ngữ cảnh thời gian, rồi mở từng chiều nhiều hay ít. Người chỉ đi cà phê buổi sáng và người đi cả ngày sẽ nhận mức điều chỉnh khác nhau.</p>
          <div className="formula">g = σ(W_g [e_u ‖ W_u τ])</div>
          <div className="formula">e_u(t) = e_u + g ⊙ W_u τ</div></div>
        <div className="card flat stack"><span className="badge coral">Bước 3</span><h3>Học từ check-in có giờ</h3>
          <p className="small">Mỗi check-in huấn luyện mang theo giờ và thứ thật của nó. Khi huấn luyện, ngữ cảnh phía địa điểm còn được điều biến theo danh mục, để "8 giờ sáng" kéo cà phê lên mà không kéo nhà hàng.</p>
          <div className="formula">e_i(t) = e_i + W_i τ ⊙ σ(c_i)</div>
          <div className="formula">L = −Σ ln σ(ŷ_ui(t) − ŷ_uj(t)) + λ‖Θ‖²</div></div>
      </div>

      <div className="card stack">
        <div className="row between"><h3>Thử ngay: đổi giờ, xem mô hình thay đổi gì</h3>
          <label className="row small"><input type="checkbox" checked={useTime} onChange={event => setUseTime(event.target.checked)} />Dùng ngữ cảnh thời gian</label></div>
        <label className="field">Thời điểm: {String(hour).padStart(2, '0')}:00 · {dayPart(hour)} thứ Tư
          <input type="range" min="0" max="23" value={hour} onChange={event => setHour(Number(event.target.value))} aria-valuetext={`${hour} giờ`} /></label>
        {demoError ? <div className="notice error"><Info size={18} /><span>{demoError}</span></div> : !demo ? <div className="skeleton" style={{ height: 160 }} /> : <>
          {!personal && <div className="notice"><Info size={18} /><span>{demo.warning || <>Bạn đang là khách nên kết quả dưới đây là <strong>độ phổ biến theo giờ</strong>, chưa phải TAS-GNN. <Link className="link" href="/login">Đăng nhập bằng tài khoản demo</Link> để thấy cổng thời gian của mô hình hoạt động trên một người dùng cụ thể.</>}</span></div>}
          <div className="grid-2" style={{ alignItems: 'start' }}>
            <div className="stack" style={{ ['--gap' as string]: '.6rem' }}>
              <strong>10 địa điểm {modelNames[demo.source] || demo.source} chấm cao nhất thuộc danh mục nào</strong>
              <div className="bars">{mix.map(row => <div className="bar-row" key={row.key} style={{ gridTemplateColumns: '170px minmax(0,1fr) 40px' }}><span className="label">{categories[row.key].symbol} {categories[row.key].label}</span>
                <div className="track"><div className="fill" style={{ width: `${row.n * 10}%`, ['--tone' as string]: `var(--${row.key})` }} /></div><span className="value">{row.n}</span></div>)}</div>
              <p className="small muted">{personal ? (demo.useTime ? 'Kéo thanh trượt: tỉ lệ danh mục thay đổi theo giờ.' : 'Đã tắt thời gian: danh sách giữ nguyên dù bạn kéo thanh trượt.') : 'Độ phổ biến theo giờ cũng đổi theo thanh trượt, nhưng giống nhau với mọi người.'}</p>
            </div>
            <ol style={{ margin: 0, paddingLeft: '1.3rem', display: 'grid', gap: '.35rem' }}>{top.slice(0, 6).map(place => <li key={place.id}><strong>{place.name}</strong> <span className="small muted">· {categories[place.category]?.label} · điểm {Math.round(place.preference * 100)}</span></li>)}</ol>
          </div></>}
      </div>
    </section>

    <section className="grid-2" style={{ alignItems: 'start' }}>
      <div className="card flat stack"><h2 style={{ fontSize: '1.5rem' }}>Thông số huấn luyện</h2>
        <dl className="kv">{hyper.map(([name, value]) => <div key={name} style={{ display: 'contents' }}><dt>{name}</dt><dd style={{ fontWeight: 500 }}>{value}</dd></div>)}</dl>
        <p className="small muted">Lấy từ <code>src/train_compare.py</code> và <code>src/models/temporal_gnn.py</code>. Notebook: <code>notebooks/DSS_POI_Colab (1).ipynb</code>.</p></div>
      <div className="card flat stack"><h2 style={{ fontSize: '1.5rem' }}>Tham số theo khối · {count(total)}</h2>
        <div className="bars">{blockNames.map(([key, label, shape]) => <div className="bar-row" key={key} style={{ gridTemplateColumns: 'minmax(0,1.2fr) minmax(0,1fr) 70px' }}>
          <span className="label">{label}<br /><span className="small muted">{shape}</span></span>
          <div className="track" style={{ height: 16 }}><div className="fill" style={{ width: `${(blocks[key] || 0) / Math.max(...Object.values(blocks)) * 100}%`, ['--tone' as string]: key.startsWith('time') || key === 'temporalGate' ? 'var(--coral)' : 'var(--sea)' }} /></div>
          <span className="value">{count(blocks[key] || 0)}</span></div>)}</div>
        <p className="small muted">{system?.ai.ready ? 'Đếm trực tiếp từ model đang chạy.' : 'Đếm từ checkpoint trong repo (dịch vụ mô hình đang tắt).'} LightGCN đối chứng chỉ có hai bảng embedding: {count(159744)} tham số.</p></div>
    </section>

    <section className="grid-2" style={{ alignItems: 'start' }}>
      <div className="card flat stack"><h2 style={{ fontSize: '1.5rem' }}>Ưu điểm</h2>
        <ul className="pros">{pros.map(text => <li key={text}><Check size={20} color="var(--ok)" /><span>{text}</span></li>)}</ul></div>
      <div className="card flat stack"><h2 style={{ fontSize: '1.5rem' }}>Nhược điểm và giới hạn</h2>
        <ul className="pros">{cons.map(text => <li key={text}><Minus size={20} color="var(--coral)" /><span>{text}</span></li>)}</ul></div>
    </section>

    <section className="card dark row between">
      <div><h3>Mô hình này so với các phương pháp khác ra sao?</h3><p className="muted small" style={{ marginTop: '.3rem' }}>Bảng so sánh 9 phương pháp, ablation và giao thức đánh giá.</p></div>
      <Link href="/evaluation" className="btn coral">Xem đánh giá</Link>
    </section>
  </main>;
}
