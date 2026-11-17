'use client';
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownUp, ArrowRight, Check, ChevronDown, Clock3, Compass, FlaskConical, GitCompareArrows, Heart, Info, LocateFixed, MapPin, Navigation, RotateCw, Search, SlidersHorizontal, Sparkles, Star, X } from 'lucide-react';
import { api, categories, money, Place, Recommendation } from '@/lib/types';
import { defaultForm, recommendationQuery, sameQuery, searchText, type ExplorerForm as Form } from '@/lib/explorer-query';
import PriorityControls from './priority-controls';
import TrainingArtifacts from './training-artifacts';

const PoiMap = dynamic(()=>import('./poi-map'),{ssr:false,loading:()=> <div className="map-loading">Đang tải bản đồ…</div>});
const presets = {balanced:'Cân bằng',proximity:'Gần tôi nhất',budget:'Tiết kiệm',ai_centric:'Hợp sở thích'};
const criterionLabels = ['Khoảng cách','Đánh giá','Chi phí','Phù hợp','Phổ biến'];
const weekdays = ['Thứ hai','Thứ ba','Thứ tư','Thứ năm','Thứ sáu','Thứ bảy','Chủ nhật'];
const scenarios = [
  {id:'morning',symbol:'☕',title:'Cafe sáng gần bạn',description:'08:00 · dưới 60.000đ · trong 5 km'},
  {id:'evening',symbol:'♨',title:'Một bữa tối thảnh thơi',description:'19:00 · dưới 200.000đ · trong 8 km'},
  {id:'personal',symbol:'✦',title:'Khám phá theo sở thích',description:'Chọn người dùng có lịch sử để trải nghiệm'},
];

export default function Explorer() {
  const [section,setSection] = useState('explore');
  const [form,setForm] = useState<Form>(defaultForm);
  const [appliedForm,setAppliedForm] = useState<Form|null>(null);
  const [activeScenario,setActiveScenario] = useState<string|null>(null);
  const [pendingFeedback,setPendingFeedback] = useState<number|null>(null);
  const [savedPlaces,setSavedPlaces] = useState<Set<string>>(new Set());
  const [users,setUsers] = useState<{id:number;display_name:string}[]>([]);
  const [stats,setStats] = useState<{pois:number;users:number;checkins:number}|null>(null);
  const [result,setResult] = useState<Recommendation|null>(null);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [tab,setTab] = useState('cafe');
  const [selected,setSelected] = useState<number|null>(null);
  const [compare,setCompare] = useState<Place[]>([]);
  const [search,setSearch] = useState('');
  const [location,setLocation] = useState({latitude:form.latitude,longitude:form.longitude});
  const [filtersOpen,setFiltersOpen] = useState(false);
  const requestId = useRef(0);
  const getResults = useCallback(async (query:Form)=>{
    const id = ++requestId.current;
    setLoading(true);setError('');
    try {
      const data = await api<Recommendation>('recommendations',recommendationQuery(query));
      if (id!==requestId.current) return;
      setResult(data);setAppliedForm({...query,weightLevels:[...query.weightLevels]});
      setLocation({latitude:query.latitude,longitude:query.longitude});
      setTab(data.groups.find(g=>g.category===(query.category||'cafe'))?.category||data.groups[0]?.category||'cafe');
      setSelected(null);setCompare([]);setSearch('');setFiltersOpen(false);
    } catch(e) {if(id===requestId.current){setError((e as Error).message || 'Không thể kết nối máy chủ.');setResult(null);}}
    finally {if(id===requestId.current)setLoading(false);}
  },[]);
  useEffect(()=>{
    api<typeof users>('users?limit=1500').then(setUsers).catch(()=>{});
    api<NonNullable<typeof stats>>('stats').then(setStats).catch(()=>{});
    void getResults(defaultForm);
  },[getResults]);
  useEffect(()=>{if(notice){const timer=setTimeout(()=>setNotice(''),5000);return()=>clearTimeout(timer);}},[notice]);
  const change = <K extends keyof Form>(key:K,value:Form[K])=>{setForm(prev=>({...prev,[key]:value}));setActiveScenario(null);};
  const dirty = !!result && !!appliedForm && !sameQuery(form,appliedForm);
  const applyScenario = (id:string)=>{
    const user = users.find(user=>String(user.id)===form.userId)||users.find(user=>user.id===12)||users[0];
    if(id==='personal'&&!user)return;
    const query:Form = {...defaultForm,weightLevels:[...defaultForm.weightLevels],
      latitude:form.latitude,longitude:form.longitude,dayOfWeek:form.dayOfWeek,
      ...(id==='morning'?{hour:8,category:'cafe',maxPrice:'60000',radiusKm:5,preset:'proximity'}:
        id==='evening'?{hour:19,category:'restaurant',maxPrice:'200000',radiusKm:8,preset:'balanced'}:
        {hour:form.hour,category:'cafe',userId:String(user?.id??''),preset:'ai_centric'})};
    setActiveScenario(id);setForm(query);setSection('explore');void getResults(query);
  };
  const group = result?.groups.find(g=>g.category===tab);
  const places = (group?.items||[]).filter(p=>searchText(p.name+' '+p.district).includes(searchText(search.trim())));
  const selectedPlace = places.find(p=>p.id===selected);
  const addCompare = (p:Place)=>{
    if(compare.some(x=>x.id===p.id))setCompare(compare.filter(x=>x.id!==p.id));
    else if(compare.length===3)setNotice('Bạn có thể so sánh tối đa 3 địa điểm.');
    else if(compare.length&&compare[0].category!==p.category)setNotice('Chọn các địa điểm cùng danh mục để so sánh TOPSIS.');
    else setCompare([...compare,p]);
  };
  const feedback = async (p:Place,action:'like'|'visit')=>{
    if(loading||pendingFeedback!==null)return;
    if(!appliedForm||appliedForm.userId===''){setNotice('Chọn người dùng rồi bấm Tìm địa điểm trước khi lưu phản hồi.');return;}
    const userId=appliedForm.userId;
    setPendingFeedback(p.id);
    try {await api('feedback',{userId:Number(userId),poiId:p.id,action});
      if(action==='like')setSavedPlaces(previous=>new Set(previous).add(`${userId}:${p.id}`));
      setNotice(action==='visit'?`Đã lưu lượt ghé cho người dùng #${userId}. Tìm lại để cập nhật gợi ý.`:`Đã lưu yêu thích cho người dùng #${userId}.`);}
    catch(e){setNotice((e as Error).message);}
    finally{setPendingFeedback(null);}
  };
  const selectCategory=(category:string)=>{
    setTab(category);setSelected(null);
    if(appliedForm?.category&&appliedForm.category!==category){
      const query={...form,category};setForm(query);setActiveScenario(null);void getResults(query);
    }
  };
  const selectFromMap=(id:number)=>{
    setSelected(id);
    document.getElementById(`place-${id}`)?.scrollIntoView({block:'nearest',behavior:'auto'});
  };
  const locate = ()=>{
    if(!navigator.geolocation){setNotice('Trình duyệt không hỗ trợ định vị. Bạn có thể nhập tọa độ.');return;}
    navigator.geolocation.getCurrentPosition(p=>{setForm(prev=>({...prev,latitude:Number(p.coords.latitude.toFixed(6)),longitude:Number(p.coords.longitude.toFixed(6))}));setNotice('Đã lấy vị trí. Bấm Tìm địa điểm để cập nhật.');},()=>setNotice('Chưa lấy được vị trí. Bạn có thể nhập tọa độ trong bộ lọc.'),{timeout:10000});
  };
  return <div className="app-shell">
    <aside className="sidebar">
      <a href="/" className="brand"><span className="brand-mark"><Compass size={27}/></span><span>danang<span className="brand-light">explore.</span></span></a>
      <p className="sidebar-label">KHÔNG GIAN CỦA BẠN</p>
      <nav aria-label="Điều hướng chính">
        <button className={section==='explore'?'nav-item active':'nav-item'} onClick={()=>setSection('explore')}><Compass size={20}/>Khám phá<span className="nav-dot"/></button>
        <button className={section==='compare'?'nav-item active':'nav-item'} onClick={()=>setSection('compare')}><GitCompareArrows size={20}/>So sánh địa điểm{compare.length>0&&<span className="count-badge">{compare.length}</span>}</button>
        <button className={section==='about'?'nav-item active':'nav-item'} onClick={()=>setSection('about')}><Info size={20}/>Về hệ thống</button>
      </nav>
      <div className="sidebar-trip"><span className="trip-sun">✺</span><h3>Đi một chút.<br/>Thấy nhiều hơn.</h3><p>Mỗi góc phố là một<br/>câu chuyện đang chờ bạn.</p><span className="trip-line"/></div>
      <div className="sidebar-bottom"><span className="location-dot"/>Đà Nẵng, Việt Nam<small>DỰ ÁN NGHIÊN CỨU · L-DSS</small></div>
    </aside>

    <main className="main-content">
      <header className="topbar"><span className="breadcrumb">Đà Nẵng <span>/</span> <strong>{section==='explore'?'Khám phá':section==='compare'?'So sánh':'Về hệ thống'}</strong></span><div className="topbar-right"><span className="prototype-tag">Bản nghiên cứu</span><span className="avatar">DN</span></div></header>
      {section==='explore'?<>
        <section className="intro"><div><div className="eyebrow"><span/>THÀNH PHỐ BIỂN, VÔ VÀN TRẢI NGHIỆM</div><h1>Hôm nay, bạn muốn <em>đi đâu?</em></h1><p>Tìm một nơi hợp gu, đúng lúc, gần bạn.</p></div><div className="city-stamp"><span>16.0544° N</span><Navigation size={28}/><span>108.2022° E</span></div></section>

        <section className="scenario-section" aria-label="Tình huống khám phá nhanh">
          <div className="scenario-heading"><span>BẮT ĐẦU BẰNG MỘT Ý TƯỞNG</span><p>Một chạm để thử nhu cầu khác nhau.</p></div>
          <div className="scenario-grid">{scenarios.map(scenario=><button key={scenario.id} type="button"
            className={activeScenario===scenario.id?'scenario-card active':'scenario-card'}
            aria-pressed={activeScenario===scenario.id} disabled={loading||(scenario.id==='personal'&&!users.length)}
            title={scenario.id==='personal'&&!users.length?'Cần tải danh sách người dùng để thử cá nhân hóa':undefined}
            onClick={()=>applyScenario(scenario.id)}>
            <span className="scenario-symbol" aria-hidden="true">{scenario.symbol}</span>
            <span><strong>{scenario.title}</strong><small>{scenario.description}</small></span><ArrowRight size={16}/>
          </button>)}</div>
        </section>

        <form className="filter-panel" onSubmit={e=>{e.preventDefault();void getResults(form);}}>
          <div className="filter-main">
            <label className="filter-field"><span><MapPin size={15}/>VỊ TRÍ KHÁM PHÁ</span><div className="location-value">{form.latitude.toFixed(4)}, {form.longitude.toFixed(4)}<button type="button" title="Lấy vị trí hiện tại" aria-label="Lấy vị trí hiện tại" onClick={locate}><LocateFixed size={19}/></button></div></label>
            <label className="filter-field"><span><Clock3 size={15}/>THỜI ĐIỂM</span><select value={form.hour} onChange={e=>change('hour',Number(e.target.value))} aria-label="Giờ khám phá">{Array.from({length:24},(_,i)=><option key={i} value={i}>{String(i).padStart(2,'0')}:00 · {i<11?'Buổi sáng':i<14?'Buổi trưa':i<18?'Buổi chiều':'Buổi tối'}</option>)}</select></label>
            <label className="filter-field"><span><SlidersHorizontal size={15}/>ƯU TIÊN CỦA BẠN</span><select value={form.preset} onChange={e=>{setForm(previous=>({...previous,preset:e.target.value,customWeights:false}));setActiveScenario(null);}}>{Object.entries(presets).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
            <button className="primary-button search-button" disabled={loading} type="submit">{loading?<RotateCw size={17} className="spin"/>:<Sparkles size={17}/>} {loading?'Đang tìm…':'Tìm địa điểm'}<ArrowRight size={17}/></button>
          </div>
          <div className="filter-footer"><span><span className="location-dot"/>Trong bán kính {form.radiusKm} km <span className="separator">·</span> {form.userId===''?'Dành cho khách mới':`Người dùng #${form.userId}`}</span><button type="button" className="text-button" onClick={()=>setFiltersOpen(!filtersOpen)} aria-expanded={filtersOpen}><SlidersHorizontal size={14}/>Bộ lọc chi tiết<ChevronDown size={14}/></button></div>
          {filtersOpen&&<div className="advanced-filters">
            <label>Người dùng<select value={form.userId} onChange={e=>change('userId',e.target.value)}><option value="">Khách mới (cold start)</option>{users.map(u=><option value={u.id} key={u.id}>{u.display_name}</option>)}</select></label>
            <label>Ngày trong tuần<select value={form.dayOfWeek} onChange={e=>change('dayOfWeek',Number(e.target.value))}>{weekdays.map((d,i)=><option value={i} key={d}>{d}</option>)}</select></label>
            <label>Danh mục<select value={form.category} onChange={e=>change('category',e.target.value)}><option value="">Tất cả danh mục</option>{Object.entries(categories).map(([key,c])=><option value={key} key={key}>{c.label}</option>)}</select></label>
            <label>Bán kính (km)<input type="number" min="0.1" max="100" step="0.1" value={form.radiusKm} onChange={e=>change('radiusKm',Number(e.target.value))} required/></label>
            <label>Ngân sách tối đa (đ)<input type="number" min="0" max="100000000" step="1000" placeholder="Không giới hạn" value={form.maxPrice} onChange={e=>change('maxPrice',e.target.value)}/></label>
            <label>Vĩ độ<input type="number" min="-90" max="90" step="any" value={form.latitude} onChange={e=>change('latitude',Number(e.target.value))} required/></label>
            <label>Kinh độ<input type="number" min="-180" max="180" step="any" value={form.longitude} onChange={e=>change('longitude',Number(e.target.value))} required/></label>
            <label className="check-label"><input type="checkbox" checked={form.excludeVisited} onChange={e=>change('excludeVisited',e.target.checked)}/>Ẩn địa điểm đã ghé</label>
          </div>}
          <PriorityControls enabled={form.customWeights} levels={form.weightLevels}
            onToggle={enabled=>change('customWeights',enabled)} onChange={levels=>change('weightLevels',levels)}/>
        </form>

        {dirty&&<div className="pending-query" role="status"><Info size={17}/><span>Bộ lọc đã thay đổi. Kết quả bên dưới vẫn thuộc lần tìm trước.</span><button type="button" disabled={loading} onClick={()=>void getResults(form)}>Áp dụng thay đổi<ArrowRight size={14}/></button></div>}

        <div className="result-heading"><div><h2>Một vài nơi dành cho bạn <span>✦</span></h2><p>{result?`${result.totalCandidates} địa điểm phù hợp · Xếp hạng riêng trong từng danh mục`:'Gợi ý dựa trên thời gian, vị trí và ưu tiên'}</p></div><span className="result-mode"><span className="location-dot"/>{!result?'Đang chuẩn bị gợi ý':result.source==='tas_gnn'?'TAS-GNN + TOPSIS':result.source==='lightgcn'?'LightGCN + TOPSIS':'Phổ biến theo giờ + TOPSIS'}</span></div>
        {result&&appliedForm&&<div className="result-context" aria-label="Ngữ cảnh của kết quả đang hiển thị">
          <span><Clock3 size={14}/>{String(appliedForm.hour).padStart(2,'0')}:00 · {weekdays[appliedForm.dayOfWeek]}</span>
          <span><Compass size={14}/>{appliedForm.userId===''?'Khách mới':`Người dùng #${appliedForm.userId}`}</span>
          <span><MapPin size={14}/>Trong {appliedForm.radiusKm} km</span>
          <span>{appliedForm.maxPrice!==''?`Tối đa ${money(Number(appliedForm.maxPrice))}`:'Không giới hạn ngân sách'}</span>
        </div>}
        {result?.artifact?.runId&&<div className="artifact-context"><FlaskConical size={15}/><span>Bộ model Đà Nẵng · seed {result.artifact.seed} · {result.artifact.selectedEpoch} epoch</span><button onClick={()=>setSection('about')}>Xem kết quả huấn luyện<ArrowRight size={14}/></button></div>}
        {result?.warning&&<div className="notice-bar"><Info size={16}/>{result.warning}</div>}
        {result?.smokeRun&&<div className="notice-bar">Artifact đang dùng chỉ là lượt chạy kiểm tra trên tập con, chưa phải mô hình huấn luyện đầy đủ.</div>}
        {error?<div className="error-panel" role="alert"><Info size={28}/><h3>Chưa tải được gợi ý</h3><p>{error}</p><p>Thử kết nối lại để tiếp tục tìm địa điểm.</p><button className="primary-button" disabled={loading} onClick={()=>void getResults(form)}>Thử lại<RotateCw size={16}/></button></div>:<>
          <div className="results-toolbar"><div className="category-tabs" role="tablist" aria-label="Danh mục địa điểm">{Object.entries(categories).map(([key,c])=><button role="tab" aria-selected={tab===key} key={key} disabled={loading} className={tab===key?'category-tab active':'category-tab'} onClick={()=>selectCategory(key)}><span>{c.symbol}</span>{c.label}<small>{result?.groups.find(g=>g.category===key)?.total||0}</small></button>)}</div><label className="inline-search"><Search size={16}/><input aria-label="Tìm trong kết quả" placeholder="Tìm tên hoặc khu vực…" value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
          <div className="explore-grid" aria-busy={loading}>
            <section className="place-list" aria-label="Danh sách địa điểm">
              <div className="list-meta"><span>{loading?'Đang cập nhật…':`${places.length} gợi ý hàng đầu`}</span><span><ArrowDownUp size={12}/>Điểm phù hợp</span></div>
              {loading&&!result?Array.from({length:3},(_,i)=><div key={i} className="skeleton-card"/>):places.map(p=><article key={p.id} id={`place-${p.id}`} className={selected===p.id?'place-card selected':'place-card'}>
                <button className={`place-visual ${p.category}`} onClick={()=>setSelected(p.id)} aria-label={`Xem ${p.name} trên bản đồ`}><span className="visual-window"/><span className="visual-line"/><span className="visual-symbol">{categories[p.category]?.symbol}</span><span className="rank-tag">{String(p.rank).padStart(2,'0')}</span></button>
                <div className="place-content"><div className="place-topline"><span className="place-district">{p.district}</span><button className="icon-button" disabled={loading||pendingFeedback!==null} aria-label={`${savedPlaces.has(`${appliedForm?.userId}:${p.id}`)?'Đã lưu':'Lưu'} ${p.name}`} aria-pressed={savedPlaces.has(`${appliedForm?.userId}:${p.id}`)} onClick={()=>void feedback(p,'like')}><Heart size={16} fill={savedPlaces.has(`${appliedForm?.userId}:${p.id}`)?'currentColor':'none'}/></button></div><button className="place-name" onClick={()=>setSelected(p.id)}>{p.name}</button><div className="place-facts"><span><Star size={12} fill="currentColor"/>{p.rating.toFixed(1)}</span><span>·</span><span title="Khoảng cách đường chim bay">{p.distanceKm.toFixed(1)} km</span><span>·</span><span>{money(p.price_avg)}</span></div><div className="place-bottom"><span className="score-pill" title="Điểm TOPSIS tương đối trong danh mục; không phải xác suất"><Sparkles size={11}/>{Math.round(p.topsisScore*100)} điểm</span><button className={compare.some(x=>x.id===p.id)?'compare-button checked':'compare-button'} aria-pressed={compare.some(x=>x.id===p.id)} onClick={()=>addCompare(p)}>{compare.some(x=>x.id===p.id)?<Check size={12}/>:<GitCompareArrows size={12}/>}So sánh</button></div></div>
              </article>)}
              {!loading&&!places.length&&<div className="empty-state"><Search size={28}/><h3>Chưa có địa điểm phù hợp</h3><p>Thử tăng bán kính, đổi danh mục hoặc bỏ giới hạn ngân sách.</p></div>}
            </section>
            <section className="map-panel" aria-label="Bản đồ khám phá"><PoiMap places={places} selected={selected} onSelect={selectFromMap} latitude={location.latitude} longitude={location.longitude}/><div className="map-caption"><MapPin size={14}/>{categories[tab]?.label} quanh bạn<span>ĐÀ NẴNG</span></div>
              {selectedPlace&&<div className="map-detail"><button className="detail-close icon-button" aria-label="Đóng chi tiết" onClick={()=>setSelected(null)}><X size={16}/></button><span className="eyebrow">ĐỊA ĐIỂM #{selectedPlace.rank}</span><h3>{selectedPlace.name}</h3><p>{selectedPlace.explanation}</p><div className="detail-actions"><a target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${location.latitude}%2C${location.longitude}%3B${selectedPlace.latitude}%2C${selectedPlace.longitude}`}><Navigation size={14}/>Chỉ đường</a><button disabled={loading||pendingFeedback!==null} onClick={()=>void feedback(selectedPlace,'visit')}><Check size={14}/>{pendingFeedback===selectedPlace.id?'Đang lưu…':'Đã ghé'}</button></div></div>}
            </section>
          </div>
        </>}
        <section className="explanation-strip"><span className="explanation-icon"><Sparkles size={22}/></span><div><h3>Một gợi ý, nhiều điều cân nhắc.</h3><p>Khoảng cách, đánh giá, ngân sách và sở thích — cùng tạo nên lựa chọn của bạn.</p></div><button className="text-button" onClick={()=>setSection('about')}>Cách hoạt động<ArrowRight size={15}/></button></section>
        <p className="data-caption"><Info size={14}/>Bản nghiên cứu dùng check-in, rating và giá mô phỏng. Giá và đánh giá cần được kiểm tra lại trước khi đến.</p>
        <footer className="page-footer"><span>ĐƯỢC XÂY DỰNG CHO NHỮNG CHUYẾN ĐI CÓ Ý NGHĨA</span><span>{stats?`${Number(stats.pois).toLocaleString('vi-VN')} địa điểm · ${Number(stats.checkins).toLocaleString('vi-VN')} check-in mô phỏng`:'Dữ liệu thực nghiệm Đà Nẵng'}</span></footer>
      </>:section==='compare'?<section className="secondary-page"><div className="eyebrow">CÂN NHẮC TRƯỚC KHI CHỌN</div><h1>Đặt lựa chọn <em>cạnh nhau.</em></h1><p>Chọn tối đa 3 địa điểm cùng danh mục từ trang Khám phá.</p>{compare.length?<div className="comparison-wrap"><table><thead><tr><th>Tiêu chí</th>{compare.map(p=><th key={p.id}>{p.name}<button className="icon-button" aria-label={`Bỏ ${p.name}`} onClick={()=>setCompare(compare.filter(x=>x.id!==p.id))}><X size={14}/></button></th>)}</tr></thead><tbody>{[
        ['Khoảng cách',...compare.map(p=>`${p.distanceKm.toFixed(2)} km`)],['Đánh giá',...compare.map(p=>`${p.rating} / 5`)],['Chi phí',...compare.map(p=>money(p.price_avg))],['Phù hợp tương đối',...compare.map(p=>`${Math.round(p.preference*100)} / 100`)],['Phổ biến',...compare.map(p=>`${p.popularity} / 100`)],['TOPSIS trong danh mục',...compare.map(p=>`${Math.round(p.topsisScore*100)} / 100`)],
      ].map(row=><tr key={row[0]}>{row.map((cell,i)=>i===0?<th key={i}>{cell}</th>:<td key={i}>{cell}</td>)}</tr>)}</tbody></table><p className="muted">Điểm TOPSIS phụ thuộc tập ứng viên và trọng số tại lần tìm kiếm; điểm phù hợp không phải xác suất.</p></div>:<div className="empty-state"><GitCompareArrows size={36}/><h3>Chưa có địa điểm để so sánh</h3><button className="primary-button" onClick={()=>setSection('explore')}>Khám phá địa điểm<ArrowRight size={16}/></button></div>}</section>:<section className="secondary-page"><div className="eyebrow">HIỂU VỀ GỢI Ý</div><h1>Đúng nơi. Đúng lúc.<br/><em>Đúng với bạn.</em></h1><p>Hệ hỗ trợ ra quyết định địa điểm cho Đà Nẵng.</p><div className="about-grid"><article><span>01 / MÔ HÌNH</span><h3>Học từ ngữ cảnh</h3><p>TAS-GNN kết hợp đồ thị người dùng – địa điểm, thời gian tuần hoàn và vị trí. Người dùng mới sử dụng độ phổ biến theo giờ.</p></article><article><span>02 / ƯU TIÊN</span><h3>Bạn quyết định điều quan trọng</h3><p>Các bộ trọng số cân bằng, gần nhất, tiết kiệm và hợp sở thích giúp lựa chọn theo nhu cầu. API hỗ trợ ma trận AHP 5×5 và kiểm tra độ nhất quán CR &lt; 0,1.</p></article><article><span>03 / XẾP HẠNG</span><h3>Cân nhắc nhiều tiêu chí</h3><p>TOPSIS xét 5 tiêu chí và xếp hạng riêng theo danh mục. Địa điểm gần, giá thấp là tiêu chí chi phí; đánh giá, phù hợp và phổ biến là tiêu chí lợi ích.</p></article></div><TrainingArtifacts activeRunId={result?.artifact?.runId}/><div className="method-panel"><h3>Trọng số của lần tìm kiếm gần nhất</h3>{criterionLabels.map((label,i)=><div className="weight-row" key={label}><span>{label}</span><div><span style={{width:`${(result?.weights[i]||0)*100}%`}}/></div><strong>{Math.round((result?.weights[i]||0)*100)}%</strong></div>)}<p>CR = {(result?.consistencyRatio||0).toFixed(3)}</p></div><div className="provenance-note"><Info size={21}/><div><h3>Dữ liệu và giới hạn nghiên cứu</h3><p>Địa điểm lấy từ OpenStreetMap. Check-in, đánh giá, giá và độ phổ biến được mô phỏng; kết quả chưa chứng minh hiệu quả với hành vi người dùng thực. Giá hiển thị dùng cho thực nghiệm, cần kiểm tra lại trước khi đến.</p><p>Huấn luyện chạy riêng trên Colab. Khi thiếu artifact hoặc dịch vụ AI, hệ thống hiển thị rõ phương án dự phòng theo giờ.</p></div></div></section>}
    </main>
    {compare.length>0&&section==='explore'&&<button className="compare-tray" onClick={()=>setSection('compare')}><GitCompareArrows size={18}/>So sánh {compare.length} địa điểm<ArrowRight size={17}/></button>}
    {notice&&<div className="toast" role="status">{notice}<button aria-label="Đóng thông báo" onClick={()=>setNotice('')}><X size={16}/></button></div>}
  </div>;
}
