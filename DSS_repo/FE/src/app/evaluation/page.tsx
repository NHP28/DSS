'use client';
import { useEffect, useState } from 'react';
import { Download, Info } from 'lucide-react';
import MetricBars, { GroupLegend, type BarItem } from '@/components/metric-bars';
import { count, percent } from '@/lib/types';

type Benchmark = {
  generatedAt: string; protocol: string; notes: Record<string, string>;
  dataset: { users: number; pois: number; events: number; trainEvents: number; testEvents: number; novelTestEvents: number };
  models: { key: string; label: string; group: string; main: boolean; usesPrevLocation: boolean; trainSeconds: number; metrics: Record<string, number> }[];
};
type Summary = {
  runId: string; seeds: number[]; assetBase: string;
  datasets: { id: string; users: number; pois: number; events: number; split: { novel_test_events: number }; models: { name: string; metrics: Record<string, { mean: number; std: number }> }[] }[];
};
const colabNames: Record<string, [string, string]> = {
  tas_gnn: ['TAS-GNN (bản Colab)', 'gnn'], lightgcn: ['LightGCN', 'gnn'], bpr_mf: ['BPR-MF', 'ml'], geo_hourly: ['Vị trí + giờ', 'heuristic'],
  hourly_popularity: ['Phổ biến theo giờ', 'heuristic'], popularity: ['Phổ biến chung', 'heuristic'],
  tas_no_time: ['TAS bỏ thời gian', 'gnn'], tas_no_space: ['TAS bỏ không gian', 'gnn'], tas_no_category: ['TAS bỏ danh mục', 'gnn'],
};
const metricInfo = [
  ['HR@K', 'Hit Rate', 'Tỉ lệ lần gợi ý mà địa điểm người dùng thật sự đến nằm trong K gợi ý đầu.', 'HR@K = (số lần trúng trong top K) / (số sự kiện test)'],
  ['NDCG@K', 'Normalized DCG', 'Như HR nhưng thưởng nhiều hơn khi địa điểm đúng đứng càng cao.', 'NDCG@K = trung bình của 1 / log₂(hạng + 1) nếu hạng ≤ K, ngược lại 0'],
  ['MRR@K', 'Mean Reciprocal Rank', 'Nghịch đảo thứ hạng của địa điểm đúng, lấy trung bình.', 'MRR@K = trung bình của 1 / hạng nếu hạng ≤ K, ngược lại 0'],
];

export default function EvaluationPage() {
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [failed, setFailed] = useState(false);
  const [metric, setMetric] = useState('HR@10');
  const [colabSet, setColabSet] = useState('danang');
  useEffect(() => {
    fetch('/artifacts/benchmark-ml.json').then(response => response.ok ? response.json() : Promise.reject()).then(setBenchmark).catch(() => setFailed(true));
    fetch('/artifacts/training-summary.json').then(response => response.ok ? response.json() : Promise.reject()).then(setSummary).catch(() => {});
  }, []);
  if (failed) return <main className="wrap page"><div className="notice error"><Info size={18} /><span>Chưa có kết quả đánh giá. Chạy <code>python src/benchmark_ml.py</code> trong thư mục <code>DSS_repo</code> rồi tải lại trang.</span></div></main>;
  if (!benchmark) return <main className="wrap page"><div className="skeleton" style={{ height: 420 }} /></main>;

  const by = (key: string) => benchmark.models.find(model => model.key === key)!;
  const tas = by('tas_gnn'), light = by('lightgcn');
  const ranked = [...benchmark.models].sort((a, b) => b.metrics['HR@10'] - a.metrics['HR@10']);
  const tasRank = ranked.findIndex(model => model.key === 'tas_gnn') + 1;
  const ahead = ranked.slice(0, tasRank - 1);
  const bars: BarItem[] = benchmark.models.map(model => ({ key: model.key, label: model.label, value: model.metrics[metric], group: model.group, main: model.main, note: model.usesPrevLocation ? 'biết vị trí liền trước' : undefined }));
  const colab = summary?.datasets.find(item => item.id === colabSet);
  const colabBars: BarItem[] = (colab?.models || []).map(model => ({ key: model.name, label: colabNames[model.name]?.[0] || model.name, group: colabNames[model.name]?.[1] || 'gnn', main: model.name === 'tas_gnn', value: model.metrics['HR@10'].mean, spread: model.metrics['HR@10'].std }));
  const ablation = summary?.datasets.find(item => item.id === 'danang')?.models.filter(model => model.name.startsWith('tas_'));

  return <main className="wrap page stack" style={{ ['--gap' as string]: '2.5rem' }}>
    <header>
      <span className="eyebrow">Đánh giá & so sánh</span>
      <h1 style={{ marginTop: '.8rem' }}>TAS-GNN so với <em>machine learning truyền thống.</em></h1>
      <p className="lede" style={{ marginTop: '.8rem' }}>Chín phương pháp, một bộ dữ liệu Đà Nẵng, một cách chia, một bộ chỉ số. Kết quả chạy lại được bằng một lệnh.</p>
    </header>

    <section className="grid-4">
      {[[percent(tas.metrics['HR@10']), 'HR@10 của TAS-GNN', `hạng ${tasRank}/${benchmark.models.length}`],
        [`+${((tas.metrics['HR@10'] - light.metrics['HR@10']) * 100).toFixed(2).replace('.', ',')} điểm`, 'so với LightGCN', `${percent(light.metrics['HR@10'])} → ${percent(tas.metrics['HR@10'])}`],
        [count(benchmark.dataset.novelTestEvents), 'sự kiện test được chấm', 'toàn bộ, không lấy mẫu'],
        [count(benchmark.dataset.pois - 1), 'địa điểm cạnh tranh', 'xếp hạng trên cả catalog']]
        .map(([value, label, note]) => <div key={label} className="card flat"><strong className="num" style={{ fontFamily: 'var(--display)', fontSize: '2rem', lineHeight: 1.1 }}>{value}</strong>
          <div style={{ marginTop: '.4rem', fontWeight: 600 }}>{label}</div><div className="small muted">{note}</div></div>)}
    </section>

    <section className="card stack">
      <div className="row between"><h2>Kết quả trên Đà Nẵng</h2>
        <div className="tabs" role="tablist" aria-label="Chỉ số">{['HR@5', 'HR@10', 'HR@20', 'NDCG@10', 'MRR@10'].map(name => <button key={name} role="tab" className="chip" aria-selected={metric === name} onClick={() => setMetric(name)}>{name}</button>)}</div></div>
      <GroupLegend groups={['main', 'gnn', 'ml', 'heuristic']} />
      <MetricBars items={bars} metric={metric} />
      <div className="notice info"><Info size={18} /><div>
        <strong>Đọc kết quả thế nào.</strong> TAS-GNN đứng trên LightGCN, User-KNN, Item-KNN, BPR-MF và hai mức phổ biến ở HR@10: thêm thời gian và không gian vào đồ thị có tác dụng.
        {ahead.length > 0 && <> Nhưng nó <strong>chưa phải tốt nhất</strong>: {ahead.map(model => `${model.label} (${percent(model.metrics['HR@10'])})`).join(' và ')} đứng trên.
          Heuristic khoảng cách được biết vị trí check-in ngay trước đó, thông tin mà TAS-GNN không nhận; Gradient Boosting dùng trực tiếp khoảng cách tới vùng hoạt động của người dùng và độ phổ biến theo giờ.
          Cả hai cho thấy trên dữ liệu này, tín hiệu "gần và đúng giờ" mạnh hơn tín hiệu cộng tác.</>}
      </div></div>
      <div className="table-wrap"><table className="data">
        <caption>{benchmark.protocol} Thời gian huấn luyện đo trên CPU máy cá nhân. Lần chạy: {new Date(benchmark.generatedAt).toLocaleString('vi-VN')}.</caption>
        <thead><tr><th scope="col">Phương pháp</th>{['HR@5', 'HR@10', 'HR@20', 'NDCG@10', 'MRR@10'].map(name => <th scope="col" key={name}>{name}</th>)}<th scope="col">Huấn luyện</th></tr></thead>
        <tbody>{ranked.map(model => <tr key={model.key} className={model.main ? 'main' : ''}>
          <th scope="row">{model.label}{benchmark.notes[model.key] && <div className="small muted" style={{ fontWeight: 400 }}>{benchmark.notes[model.key]}</div>}
            {model.group === 'gnn' && <div className="small muted" style={{ fontWeight: 400 }}>{benchmark.notes.gnn}</div>}</th>
          {['HR@5', 'HR@10', 'HR@20', 'NDCG@10', 'MRR@10'].map(name => <td key={name}>{percent(model.metrics[name])}</td>)}
          <td>{model.group === 'gnn' ? 'có sẵn' : model.trainSeconds < 0.1 ? '< 0,1 s' : `${model.trainSeconds.toFixed(1).replace('.', ',')} s`}</td></tr>)}</tbody>
      </table></div>
      <div className="row"><a className="link" href="/artifacts/benchmark-ml.json" download><Download size={15} />Tải kết quả (JSON)</a>
        <span className="small muted">Chạy lại, có biểu đồ: <code>notebooks/01…03</code></span></div>
    </section>

    <section className="grid-3">{metricInfo.map(([short, name, text, formula]) => <div key={short} className="card flat stack">
      <div><span className="badge">{short}</span></div><h3>{name}</h3><p className="small">{text}</p><p className="small muted mono">{formula}</p></div>)}</section>

    <section className="card stack">
      <h2>Giao thức đánh giá</h2>
      <ol style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '.5rem' }}>
        <li>Sắp xếp check-in của từng người dùng theo thời gian: <strong>80% đầu để huấn luyện</strong> ({count(benchmark.dataset.trainEvents)} sự kiện), <strong>20% cuối để kiểm tra</strong> ({count(benchmark.dataset.testEvents)} sự kiện). Không dùng tương lai để dự đoán quá khứ.</li>
        <li>Chỉ chấm các lần ghé <strong>địa điểm mới</strong> ({count(benchmark.dataset.novelTestEvents)} sự kiện): gợi ý lại nơi đã quen không chứng minh được gì.</li>
        <li>Với mỗi sự kiện, mô hình xếp hạng <strong>toàn bộ {count(benchmark.dataset.pois)} địa điểm</strong> trừ những nơi người dùng đã ghé trong tập huấn luyện. Không lấy mẫu âm.</li>
        <li>Siêu tham số của BPR-MF và Gradient Boosting được chọn trên phần cuối của tập huấn luyện, không nhìn vào tập test.</li>
      </ol>
      <p className="small muted">Checkpoint TAS-GNN và LightGCN được huấn luyện trên 70% đầu (theo <code>src/train_compare.py</code>), nằm gọn trong phần huấn luyện ở trên.</p>
    </section>

    {summary && colab && <section className="card stack">
      <div className="row between"><div><h2>Lượt chạy Colab · {summary.seeds.length} seed</h2>
        <p className="small muted" style={{ marginTop: '.3rem' }}>Bản TAS-GNN viết lại trong notebook (<code>ml/poi_model.py</code>), chia theo mốc thời gian toàn cục, HR@10 trung bình ± độ lệch chuẩn. Kiến trúc và cách chia khác bảng trên, nên không so trực tiếp hai bảng.</p></div>
        <div className="tabs" role="tablist" aria-label="Bộ dữ liệu">{summary.datasets.map(item => <button key={item.id} role="tab" className="chip" aria-selected={colabSet === item.id} onClick={() => setColabSet(item.id)}>{item.id === 'danang' ? 'Đà Nẵng' : 'Gowalla (bộ mẫu)'}</button>)}</div></div>
      <p className="small">{count(colab.users)} người dùng · {count(colab.pois)} địa điểm · {count(colab.events)} check-in · {count(colab.split.novel_test_events)} sự kiện test mới</p>
      <MetricBars items={colabBars} metric="HR@10" />
      {colabSet === 'gowalla' && <div className="notice"><Info size={18} /><span>Trên Gowalla (check-in thật, không có danh mục), TAS-GNN <strong>không thắng</strong>: các phương pháp nằm sát nhau quanh 5,1–5,6% và phần thời gian không giúp thêm. Lợi thế của TAS-GNN trên Đà Nẵng một phần đến từ quy luật giờ giấc rõ ràng của dữ liệu mô phỏng.</span></div>}
      <div className="grid-2">{['comparison', 'learning_curves'].map(file => <figure key={file} className="table-wrap" style={{ margin: 0 }}>
        <a href={`${summary.assetBase}/${colabSet}_${file}.png`} target="_blank" rel="noreferrer"><img src={`${summary.assetBase}/${colabSet}_${file}.png`} alt={file === 'comparison' ? 'Biểu đồ so sánh mô hình từ notebook' : 'Đường học: loss và HR@10 validation theo epoch'} loading="lazy" style={{ width: '100%', display: 'block' }} /></a>
        <figcaption className="small muted" style={{ padding: '.6rem .9rem' }}>{file === 'comparison' ? 'So sánh mô hình (xuất từ notebook)' : 'Diễn biến huấn luyện theo epoch'}</figcaption></figure>)}</div>
    </section>}

    {ablation && <section className="card stack">
      <h2>Ablation: mỗi thành phần đóng góp bao nhiêu</h2>
      <p className="small muted">Lượt Colab trên Đà Nẵng, mỗi biến thể được huấn luyện riêng, HR@10 trung bình {summary!.seeds.length} seed.</p>
      <MetricBars metric="HR@10" items={ablation.map(model => ({ key: model.name, label: model.name === 'tas_gnn' ? 'TAS-GNN đầy đủ' : colabNames[model.name][0], group: 'gnn', main: model.name === 'tas_gnn', value: model.metrics['HR@10'].mean, spread: model.metrics['HR@10'].std }))} />
      <p className="small">Bỏ <strong>không gian</strong> làm giảm nhiều nhất, sau đó là <strong>thời gian</strong>; bỏ danh mục chỉ giảm nhẹ.</p>
    </section>}

    <section className="card flat stack">
      <h2>Giới hạn cần nói rõ</h2>
      <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '.5rem' }}>
        <li>Check-in, đánh giá và giá của bộ Đà Nẵng là <strong>dữ liệu mô phỏng</strong>. Kết quả cho thấy mô hình học được quy luật trong dữ liệu đó, chưa chứng minh hiệu quả với người dùng thật.</li>
        <li>295 khách sạn không có lượt check-in nào, nên chưa đánh giá được chất lượng gợi ý lưu trú.</li>
        <li>Bảng này đo bước chấm điểm sở thích. Bước AHP–TOPSIS (khoảng cách, giá, đánh giá) chưa có thước đo offline.</li>
        <li>Cá nhân hóa cho tài khoản tự đăng ký (dựng hồ sơ từ các địa điểm đã chọn) là xấp xỉ và chưa được đánh giá.</li>
      </ul>
    </section>
  </main>;
}
