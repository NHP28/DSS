export const CRITERIA = ['distance', 'rating', 'price', 'preference', 'popularity'] as const;
export const PRESETS: Record<string, number[]> = {
  balanced: [.25,.2,.15,.3,.1], proximity: [.5,.15,.1,.2,.05],
  budget: [.2,.15,.4,.2,.05], ai_centric: [.15,.15,.1,.5,.1],
};

export function ahp(matrix: number[][]) {
  const n = 5;
  if (matrix.length !== n || matrix.some(row => row.length !== n || row.some(x => !Number.isFinite(x) || x < 1/9 || x > 9))) throw new Error('Ma trận AHP phải là 5×5, giá trị trong [1/9, 9]');
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    if ((i === j && Math.abs(matrix[i][j] - 1) > 1e-6) || Math.abs(matrix[i][j] * matrix[j][i] - 1) > .01) throw new Error('Ma trận AHP phải có đường chéo 1 và tính đối ứng');
  }
  let w = Array(n).fill(1/n) as number[];
  for (let k = 0; k < 200; k++) {
    const next = matrix.map(row => row.reduce((s, x, j) => s + x * w[j], 0));
    const sum = next.reduce((s,x) => s+x,0);
    const normalized = next.map(x=>x/sum);
    const change = Math.max(...normalized.map((x,i)=>Math.abs(x-w[i])));
    w = normalized;
    if (change < 1e-12) break;
  }
  const lambda = matrix.reduce((s,row,i)=>s+row.reduce((v,x,j)=>v+x*w[j],0)/w[i],0)/n;
  const cr = Math.max(0, (lambda-n)/(n-1)/1.12);
  if (cr >= .1) throw new Error(`Ma trận thiếu nhất quán (CR=${cr.toFixed(3)} ≥ 0.1)`);
  return {weights:w, consistencyRatio:cr};
}

export function haversine(lat: number, lon: number, pLat: number, pLon: number) {
  const rad = (x:number)=>x*Math.PI/180;
  const a = Math.sin(rad(pLat-lat)/2)**2 + Math.cos(rad(lat))*Math.cos(rad(pLat))*Math.sin(rad(pLon-lon)/2)**2;
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1,Math.max(0,a))));
}

export interface Candidate {
  id: number; name: string; category: string; district: string;
  latitude: number; longitude: number; rating: number; price_avg: number; popularity: number;
  distanceKm: number; preference: number;
}

export function topsis(candidates: Candidate[], weights: number[]) {
  if (weights.length !== 5 || weights.some(w=> !Number.isFinite(w) || w<0) || weights.reduce((s,w)=>s+w,0)<=0) throw new Error('Trọng số không hợp lệ');
  if (!candidates.length) return [];
  const total = weights.reduce((s,x)=>s+x,0);
  const raw = candidates.map(p=>[p.distanceKm,p.rating,p.price_avg,p.preference,p.popularity]);
  const norms = weights.map((_,j)=>Math.hypot(...raw.map(row=>row[j])) || 1);
  const v = raw.map(row=>row.map((x,j)=>x/norms[j]*weights[j]/total));
  const positive = weights.map((_,j)=>(j===0||j===2?Math.min:Math.max)(...v.map(row=>row[j])));
  const negative = weights.map((_,j)=>(j===0||j===2?Math.max:Math.min)(...v.map(row=>row[j])));
  return candidates.map((p,i)=>{
    const dPos = Math.hypot(...v[i].map((x,j)=>x-positive[j]));
    const dNeg = Math.hypot(...v[i].map((x,j)=>x-negative[j]));
    const score = dPos+dNeg===0 ? .5 : dNeg/(dPos+dNeg);
    return {...p, topsisScore:score, explanation:`Cách bạn ${p.distanceKm.toFixed(1)} km · ${p.rating.toFixed(1)} sao · ${Math.round(p.price_avg).toLocaleString('vi-VN')} đ. Điểm phù hợp là điểm xếp hạng tương đối.`};
  }).sort((a,b)=>b.topsisScore-a.topsisScore || a.id-b.id).map((p,i)=>({...p,rank:i+1}));
}
