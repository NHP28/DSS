'use client';
import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import KgViewer, { nodeTones } from '@/components/kg-viewer';
import { api } from '@/lib/api';
import { categories, count, percent, weekdays } from '@/lib/types';

type Column = { column: string; type: string; meaning: string; origin: string };
type Profile = {
  danang: {
    pois: number; users: number; checkins: number; friendships: number; timeRange: string[]; density: number; poisWithoutCheckins: number;
    checkinsPerUser: { min: number; median: number; mean: number; max: number };
    categories: { key: string; pois: number; checkins: number }[]; districts: { name: string; pois: number }[];
    byHour: ({ hour: number; total: number } & Record<string, number>)[]; byWeekday: number[];
  };
  gowalla: { users: number; pois: number; checkins: number; source: string; note: string };
  schema: Record<string, Column[]>;
  graph: { nodes: Record<string, number>; relationships: Record<string, number> };
};
const fileNotes: Record<string, string> = {
  'danang_pois_full.csv': 'Catalog địa điểm: vị trí và tên thật từ OpenStreetMap; đánh giá, giá, độ phổ biến được sinh mô phỏng.',
  'danang_checkins_full.csv': 'Lịch sử tương tác: mỗi dòng là một lần người dùng ghé một địa điểm, kèm giờ và thứ.',
  'danang_social_full.csv': 'Quan hệ bạn bè giữa người dùng (không hướng).',
};
const relations: [string, string, string, string][] = [
  ['User', 'VISITED', 'POI', 'số lần ghé, lần đầu, lần cuối, giờ hay ghé nhất'],
  ['User', 'FRIEND_OF', 'User', 'quan hệ bạn bè'],
  ['POI', 'IN_CATEGORY', 'Category', 'cà phê, nhà hàng, khách sạn, tham quan'],
  ['POI', 'LOCATED_IN', 'District', '7 quận, huyện (đã gộp các cách viết)'],
  ['POI', 'NEAR', 'POI', '5 địa điểm gần nhất, kèm số km'],
  ['POI', 'BUSY_AT', 'TimeSlot', 'số lượt và tỉ lệ lượt ghé theo khung giờ'],
  ['User', 'ACTIVE_AT', 'TimeSlot', 'số lượt check-in của người dùng theo khung giờ'],
];
const hourTones: Record<string, string> = { cafe: 'var(--cafe)', restaurant: 'var(--restaurant)', tourist_spot: 'var(--tourist_spot)' };

export default function DataPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [failed, setFailed] = useState(false);
  const [live, setLive] = useState<Profile['graph'] | null>(null);
  useEffect(() => {
    fetch('/artifacts/data-profile.json').then(response => response.ok ? response.json() : Promise.reject()).then(setProfile).catch(() => setFailed(true));
    api<Profile['graph']>('kg/stats').then(setLive).catch(() => setLive(null));
  }, []);
  if (failed) return <main className="wrap page"><div className="notice error"><Info size={18} /><span>Chưa có hồ sơ dữ liệu. Chạy <code>python tools/export_data_profile.py</code> rồi tải lại trang.</span></div></main>;
  if (!profile) return <main className="wrap page"><div className="skeleton" style={{ height: 420 }} /></main>;
  const d = profile.danang, graph = live || profile.graph;
  const maxHour = Math.max(...d.byHour.map(row => row.total)), maxDistrict = Math.max(...d.districts.map(row => row.pois)), maxDay = Math.max(...d.byWeekday);
  const nodeTotal = Object.values(graph.nodes).reduce((sum, value) => sum + value, 0), edgeTotal = Object.values(graph.relationships).reduce((sum, value) => sum + value, 0);

  return <main className="wrap page stack" style={{ ['--gap' as string]: '2.5rem' }}>
    <header><span className="eyebrow">Dữ liệu & đồ thị tri thức</span>
      <h1 style={{ marginTop: '.8rem' }}>Khách đến Đà Nẵng, <em>dưới dạng đồ thị.</em></h1>
      <p className="lede" style={{ marginTop: '.8rem' }}>Bộ dữ liệu Đà Nẵng dùng để huấn luyện và phục vụ website; bộ mẫu Gowalla dùng để đối chiếu trên check-in thật. Toàn bộ được nạp vào Neo4j thành một đồ thị tri thức.</p></header>

    <section className="stat-strip" style={{ marginTop: 0 }}>
      {[[count(d.pois), 'địa điểm thật từ OpenStreetMap'], [count(d.users), 'người dùng'], [count(d.checkins), 'lượt check-in'], [count(d.friendships), 'quan hệ bạn bè']]
        .map(([value, label]) => <div key={label}><strong className="num">{value}</strong><span>{label}</span></div>)}
    </section>

    <div className="notice"><Info size={18} /><span><strong>Nguồn gốc dữ liệu.</strong> Tên, tọa độ, danh mục và quận của địa điểm lấy từ OpenStreetMap. Người dùng, check-in, bạn bè, điểm đánh giá, giá và độ phổ biến là <strong>dữ liệu mô phỏng</strong> theo nhịp sinh hoạt đô thị, vì Đà Nẵng chưa có bộ check-in công khai.</span></div>

    <section className="stack">
      <h2>Cấu trúc bộ dữ liệu Đà Nẵng</h2>
      <p className="muted">Ba file CSV trong <code>data/danang</code>. Thời gian: {d.timeRange[0].slice(0, 10)} đến {d.timeRange[1].slice(0, 10)}.</p>
      {Object.entries(profile.schema).map(([file, columns]) => <div key={file} className="stack" style={{ ['--gap' as string]: '.5rem' }}>
        <h3 className="mono" style={{ fontSize: '1.05rem' }}>{file}</h3><p className="small muted">{fileNotes[file]}</p>
        <div className="table-wrap"><table className="data"><thead><tr><th scope="col">Cột</th><th scope="col" style={{ textAlign: 'left' }}>Kiểu</th><th scope="col" style={{ textAlign: 'left' }}>Ý nghĩa</th><th scope="col">Nguồn</th></tr></thead>
          <tbody>{columns.map(column => <tr key={column.column}><th scope="row" className="mono">{column.column}</th><td style={{ textAlign: 'left' }}>{column.type}</td><td style={{ textAlign: 'left', whiteSpace: 'normal' }}>{column.meaning}</td>
            <td><span className={column.origin === 'OpenStreetMap' ? 'badge' : 'badge sun'}>{column.origin}</span></td></tr>)}</tbody></table></div>
      </div>)}
    </section>

    <section className="grid-2" style={{ alignItems: 'start' }}>
      <div className="card flat stack">
        <h3>Địa điểm và check-in theo danh mục</h3>
        <div className="table-wrap"><table className="data" style={{ minWidth: 0 }}><thead><tr><th scope="col">Danh mục</th><th scope="col">Địa điểm</th><th scope="col">Check-in</th><th scope="col">Tỉ lệ</th></tr></thead>
          <tbody>{d.categories.map(row => <tr key={row.key}><th scope="row">{categories[row.key]?.symbol} {categories[row.key]?.label}</th><td>{count(row.pois)}</td><td>{count(row.checkins)}</td><td>{percent(row.checkins / d.checkins, 1)}</td></tr>)}</tbody></table></div>
        <p className="small muted">{count(d.poisWithoutCheckins)} địa điểm chưa có lượt check-in nào (toàn bộ khách sạn). Mật độ ma trận người dùng × địa điểm: {percent(d.density, 2)}.</p>
        <dl className="kv"><dt>Check-in mỗi người dùng</dt><dd>{d.checkinsPerUser.min} – {d.checkinsPerUser.max}</dd><dt>Trung vị / trung bình</dt><dd>{d.checkinsPerUser.median} / {String(d.checkinsPerUser.mean).replace('.', ',')}</dd></dl>
      </div>
      <div className="card flat stack">
        <h3>Địa điểm theo quận</h3>
        <div className="bars">{d.districts.map(row => <div className="bar-row" key={row.name} style={{ gridTemplateColumns: '130px minmax(0,1fr) 50px' }}><span className="label">{row.name}</span>
          <div className="track" style={{ height: 18 }}><div className="fill" style={{ width: `${row.pois / maxDistrict * 100}%`, ['--tone' as string]: 'var(--hotel)' }} /></div><span className="value">{row.pois}</span></div>)}</div>
      </div>
    </section>

    <section className="card stack">
      <h2>Tín hiệu thời gian trong dữ liệu</h2>
      <p className="muted">Số lượt check-in theo giờ trong ngày, tách theo danh mục. Đây là quy luật mà cơ chế thời gian của TAS-GNN cần học: cà phê dồn về 7–10 giờ sáng, nhà hàng chiếm trọn buổi trưa, còn tham quan chỉ xuất hiện từ 15 giờ đến tối. Không có check-in nào trước 7 giờ, lúc 14 giờ và sau 21 giờ.</p>
      <div className="legend">{Object.entries(hourTones).map(([key, tone]) => <span key={key}><i style={{ ['--tone' as string]: tone }} />{categories[key].label}</span>)}</div>
      <div><div className="hours" role="img" aria-label={`Check-in theo giờ: ${d.byHour.filter(row => row.total).map(row => `${row.hour} giờ ${row.total}`).join(', ')}`}>
        {d.byHour.map(row => <div className="col" key={row.hour} title={`${String(row.hour).padStart(2, '0')}:00 · ${count(row.total)} lượt`}>
          {Object.entries(hourTones).map(([key, tone]) => <i key={key} style={{ height: `${(row[key] || 0) / maxHour * 100}%`, ['--tone' as string]: tone }} />)}</div>)}</div>
        <div className="hours-axis">{d.byHour.map(row => <span key={row.hour}>{row.hour % 3 === 0 ? row.hour : ''}</span>)}</div></div>
      <div className="bars" style={{ marginTop: '.5rem' }}>{d.byWeekday.map((value, index) => <div className="bar-row" key={index} style={{ gridTemplateColumns: '90px minmax(0,1fr) 64px' }}><span className="label">{weekdays[index]}</span>
        <div className="track" style={{ height: 14 }}><div className="fill" style={{ width: `${value / maxDay * 100}%`, ['--tone' as string]: index >= 5 ? 'var(--coral)' : 'var(--sea)' }} /></div><span className="value">{count(value)}</span></div>)}</div>
    </section>

    <section className="card flat stack">
      <h2>Bộ mẫu đối chiếu: Gowalla</h2>
      <div className="table-wrap"><table className="data"><thead><tr><th scope="col">Bộ dữ liệu</th><th scope="col">Người dùng</th><th scope="col">Địa điểm</th><th scope="col">Check-in</th><th scope="col" style={{ textAlign: 'left' }}>Tương tác</th><th scope="col" style={{ textAlign: 'left' }}>Vai trò</th></tr></thead>
        <tbody><tr className="main"><th scope="row">Đà Nẵng</th><td>{count(d.users)}</td><td>{count(d.pois)}</td><td>{count(d.checkins)}</td><td style={{ textAlign: 'left' }}>Mô phỏng</td><td style={{ textAlign: 'left' }}>Huấn luyện, đánh giá, phục vụ web</td></tr>
          <tr><th scope="row">Gowalla</th><td>{count(profile.gowalla.users)}</td><td>{count(profile.gowalla.pois)}</td><td>{count(profile.gowalla.checkins)}</td><td style={{ textAlign: 'left' }}>Thật</td><td style={{ textAlign: 'left' }}>Đối chiếu trên notebook Colab</td></tr></tbody></table></div>
      <p className="small muted">{profile.gowalla.source}. {profile.gowalla.note}</p>
    </section>

    <section className="stack">
      <div><span className="eyebrow">Neo4j</span><h2 style={{ marginTop: '.6rem' }}>Đồ thị tri thức: {count(nodeTotal)} nút, {count(edgeTotal)} cạnh</h2>
        <p className="muted" style={{ marginTop: '.4rem' }}>Dựng bằng <code>tools/build_kg.py</code> từ ba file CSV. Đồ thị hai phía Người dùng–Địa điểm mà TAS-GNN lan truyền chính là phần <code>VISITED</code> của đồ thị này; website dùng các cạnh còn lại để giải thích từng gợi ý.
          {' '}{live ? <span className="badge"><span className="status-dot on" />Số liệu đọc trực tiếp từ Neo4j</span> : <span className="badge sun">Neo4j chưa bật: số liệu tính từ CSV</span>}</p></div>
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div className="card flat stack"><h3>Loại nút</h3>
          <dl className="kv">{Object.entries({ User: 'Người dùng', POI: 'Địa điểm', Category: 'Danh mục', District: 'Quận', TimeSlot: 'Khung giờ' }).map(([type, label]) => <div key={type} style={{ display: 'contents' }}>
            <dt><span className="status-dot" style={{ background: nodeTones[type] }} />{label} <code>:{type}</code></dt><dd>{count(graph.nodes[type] || 0)}</dd></div>)}</dl>
          <p className="small muted">Khung giờ: sáng 5–10h, trưa 11–13h, chiều 14–17h, tối 18–22h, khuya 23–4h.</p></div>
        <div className="card flat stack"><h3>Loại quan hệ</h3>
          <div className="table-wrap"><table className="data" style={{ minWidth: 0 }}><tbody>{relations.map(([from, type, to, note]) => <tr key={type}>
            <th scope="row"><span className="mono small">(:{from})-[:{type}]-&gt;(:{to})</span><div className="small muted" style={{ fontWeight: 400 }}>{note}</div></th><td>{count(graph.relationships[type] || 0)}</td></tr>)}</tbody></table></div></div>
      </div>
      <div className="card stack"><h3>Xem trực tiếp một vùng của đồ thị</h3><KgViewer /></div>
    </section>
  </main>;
}
