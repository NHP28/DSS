export interface Place {
  id:number;name:string;category:string;district:string;latitude:number;longitude:number;
  rating:number;price_avg:number;popularity:number;distanceKm:number;preference:number;
  topsisScore:number;rank:number;explanation:string;
}
export interface Recommendation {
  artifact?:{runId?:string;seed?:number;selectedEpoch?:number;trainedUsers?:number;pois?:number}|null;
  source:string;warning:string|null;smokeRun:boolean;weights:number[];consistencyRatio:number;
  groups:{category:string;total:number;items:Place[]}[];totalCandidates:number;elapsedMs:number;
}
export const categories:Record<string,{label:string;short:string;symbol:string}> = {
  cafe:{label:'Cà phê',short:'Cà phê',symbol:'☕'},
  restaurant:{label:'Nhà hàng',short:'Ăn uống',symbol:'♨'},
  hotel:{label:'Khách sạn',short:'Lưu trú',symbol:'⌂'},
  tourist_spot:{label:'Tham quan',short:'Khám phá',symbol:'✦'},
};
export const money = (v:number)=>new Intl.NumberFormat('vi-VN').format(v)+' đ';
export async function api<T>(path:string,body?:unknown):Promise<T> {
  const res = await fetch(`/api/${path}`,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
  if (!res.ok) {
    const data = await res.json().catch(()=>({}));
    throw new Error(Array.isArray(data.message)?data.message.join(', '):data.message || `API lỗi ${res.status}`);
  }
  return res.json();
}
