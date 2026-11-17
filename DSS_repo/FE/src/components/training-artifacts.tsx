'use client';
import { useEffect, useState } from 'react';
import { Download, FlaskConical, Info } from 'lucide-react';

type Metric = {mean:number;std:number};
type Dataset = {
  id:string;users:number;pois:number;events:number;
  split:{novel_test_events:number;test_cold_user_events_excluded:number;repeated_test_percent:number};
  models:{name:string;metrics:Record<string,Metric>}[];
};
type Summary = {
  runId:string;runMode:string;protocol:string;seeds:number[];servingSeed:number;
  assetBase:string;verifiedFiles:number;datasets:Dataset[];
};
const labels:Record<string,string> = {
  tas_gnn:'TAS-GNN',lightgcn:'LightGCN',bpr_mf:'BPR-MF',geo_hourly:'Vị trí + giờ',
  hourly_popularity:'Phổ biến theo giờ',popularity:'Phổ biến',tas_no_time:'TAS bỏ thời gian',
  tas_no_space:'TAS bỏ không gian',tas_no_category:'TAS bỏ danh mục',
};
const number = (value:number)=>value.toLocaleString('vi-VN');
const metric = (value:Metric)=>`${(value.mean*100).toFixed(2)} ± ${(value.std*100).toFixed(2)}%`;

export default function TrainingArtifacts({activeRunId}:{activeRunId?:string}) {
  const [summary,setSummary] = useState<Summary|null>(null);
  const [dataset,setDataset] = useState('danang');
  const [failed,setFailed] = useState(false);
  const [attempt,setAttempt] = useState(0);
  useEffect(()=>{
    const controller = new AbortController();
    setFailed(false);
    fetch('/artifacts/training-summary.json',{signal:controller.signal,cache:'no-store'})
      .then(response=>{if(!response.ok)throw new Error('Report unavailable');return response.json();})
      .then(setSummary).catch(()=>{if(!controller.signal.aborted)setFailed(true);});
    return ()=>controller.abort();
  },[attempt]);
  if(failed)return <div className="notice-bar"><Info size={16}/><span>Chưa tải được báo cáo huấn luyện.</span><button onClick={()=>setAttempt(value=>value+1)}>Thử lại</button></div>;
  if(!summary)return <p className="training-loading" role="status">Đang tải kết quả huấn luyện…</p>;
  const current = summary.datasets.find(item=>item.id===dataset)!;
  return <section className="training-panel" aria-labelledby="training-title">
    <div className="training-heading"><div><span className="eyebrow"><FlaskConical size={15}/>KẾT QUẢ TỪ COLAB</span><h2 id="training-title">Bộ huấn luyện đã tích hợp</h2><p>Chia theo thời gian toàn cục · {summary.seeds.length} seed ({summary.seeds.join(', ')}) · {summary.runMode==='full'?'Huấn luyện đầy đủ':'Chạy kiểm tra'}</p></div>
      <span className="training-status">{activeRunId===summary.runId?`API đã nạp model Đà Nẵng · seed ${summary.servingSeed}`:'Báo cáo artifacts đã nhập'}</span>
    </div>
    <div className="training-tabs" role="tablist" aria-label="Bộ dữ liệu huấn luyện">{summary.datasets.map(item=><button key={item.id} role="tab" aria-selected={dataset===item.id} onClick={()=>setDataset(item.id)}>{item.id==='danang'?'Đà Nẵng':'Gowalla'}</button>)}</div>
    <div className="training-stats">{[[number(current.users),'người dùng'],[number(current.pois),'địa điểm'],[number(current.events),'check-in'],[number(current.split.novel_test_events),'sự kiện test mới']].map(([value,label])=><div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
    <p className="training-description">{dataset==='danang'?'Model Đà Nẵng cung cấp điểm sở thích cho gợi ý trên bản đồ. Check-in, giá và đánh giá là dữ liệu mô phỏng.':'Gowalla là thí nghiệm trên check-in công khai thực tế với catalog độc lập. Luồng gợi ý bản đồ sử dụng model Đà Nẵng.'}</p>
    <div className="training-table"><table><caption>Trung bình ± độ lệch chuẩn qua {summary.seeds.length} seed; HR, NDCG và MRR tại top 10, tính trên sự kiện ghé POI mới.</caption><thead><tr><th scope="col">Mô hình</th><th scope="col">HR@10</th><th scope="col">NDCG@10</th><th scope="col">MRR@10</th></tr></thead><tbody>{current.models.map(model=><tr key={model.name} className={model.name==='tas_gnn'?'training-selected':''}><th scope="row">{labels[model.name]||model.name}</th>{['HR@10','NDCG@10','MRR@10'].map(key=><td key={key}>{metric(model.metrics[key])}</td>)}</tr>)}</tbody></table></div>
    <p className="training-footnote">Đã loại {number(current.split.test_cold_user_events_excluded)} sự kiện của người dùng chưa có lịch sử fit và {current.split.repeated_test_percent.toFixed(2)}% lượt ghé lặp khỏi đánh giá POI mới. Kết quả này đo mô hình gợi ý; chưa đánh giá hiệu quả AHP/TOPSIS.</p>
    {dataset==='danang'&&<div className="notice-bar"><Info size={16}/>295 khách sạn trong catalog chưa có tương tác huấn luyện; chất lượng gợi ý nhóm này chưa được kiểm chứng.</div>}
    <div className="training-figures">{[['comparison','So sánh mô hình'],['learning_curves','Diễn biến huấn luyện']].map(([file,title])=><figure key={file}><a href={`${summary.assetBase}/${dataset}_${file}.png`} target="_blank" rel="noreferrer"><img src={`${summary.assetBase}/${dataset}_${file}.png`} alt={`${title} trên ${dataset==='danang'?'Đà Nẵng':'Gowalla'}`} loading="lazy"/></a><figcaption>{title} · bấm để xem ảnh đầy đủ</figcaption></figure>)}</div>
    <div className="training-downloads"><a href={`${summary.assetBase}/all_datasets_comparison.csv`} download><Download size={15}/>Kết quả CSV</a><a href={`${summary.assetBase}/research_summary.md`} download><Download size={15}/>Báo cáo nghiên cứu</a><small>{summary.runId} · {summary.verifiedFiles} file đã xác minh SHA256</small></div>
  </section>;
}
