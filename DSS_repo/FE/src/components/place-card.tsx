'use client';
import { useState } from 'react';
import { Check, Heart, HelpCircle, MapPin, Navigation, Star, Wallet } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { categories, money, type Place } from '@/lib/types';
import { useGooglePlace } from '@/lib/use-google-place';

type Reason = { kind: string; text: string };
type Props = {
  place: Place; selected?: boolean; showCategory?: boolean; hour: number; origin: { latitude: number; longitude: number };
  onSelect?: () => void; onFeedback?: (action: 'like' | 'unlike' | 'visit' | 'unvisit') => void; busy?: boolean;
};

export default function PlaceCard({ place, selected, showCategory, hour, origin, onSelect, onFeedback, busy }: Props) {
  const [why, setWhy] = useState<{ state: 'closed' | 'loading' | 'ready' | 'error'; reasons?: Reason[]; message?: string }>({ state: 'closed' });
  const toggleWhy = async () => {
    if (why.state !== 'closed') return setWhy({ state: 'closed' });
    setWhy({ state: 'loading' });
    try {
      const data = await api<{ reasons: Reason[] }>(`kg/explain?poiId=${place.id}&hour=${hour}`);
      setWhy({ state: 'ready', reasons: data.reasons });
    } catch (error) {
      setWhy({ state: 'error', message: error instanceof ApiError && error.status === 503
        ? 'Đồ thị tri thức (Neo4j) chưa bật, nên chưa có lý do theo đồ thị.' : (error as Error).message });
    }
  };
  const { ref, place: google } = useGooglePlace<HTMLElement>(place.id);
  const photo = google?.photoUrl;
  const score = Math.round(place.topsisScore * 100);
  return <article ref={ref} id={`place-${place.id}`} className={`place${selected ? ' selected' : ''}${photo ? ' has-photo' : ''}`} style={{ ['--cat' as string]: `var(--${place.category})` }}>
    {photo ? <figure className="place-photo">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={photo} alt={`Ảnh ${place.name} trên Google Maps`} loading="lazy" referrerPolicy="no-referrer" />
      <span className="place-rank" title={`Hạng ${place.rank} trong ${categories[place.category]?.label}`}>{place.rank}</span>
      <figcaption>Ảnh: {google.photoAuthors.length ? google.photoAuthors.map((author, index) => <span key={index}>{index > 0 && ', '}
        {author.url ? <a href={author.url} target="_blank" rel="noreferrer">{author.name}</a> : author.name}</span>) : 'Google Maps'}</figcaption>
    </figure> : <div className="place-rank" title={`Hạng ${place.rank} trong ${categories[place.category]?.label}`}>{place.rank}</div>}
    <div>
      <h3><button type="button" onClick={onSelect}>{place.name}</button></h3>
      <div className="place-meta">
        {showCategory && <span>{categories[place.category]?.symbol} {categories[place.category]?.label}</span>}
        <span><MapPin size={14} />{place.district} · {place.distanceKm.toFixed(1)} km</span>
        {google?.rating != null
          ? <a className="star google" href={google.mapsUrl || undefined} target="_blank" rel="noreferrer" title="Điểm đánh giá thật trên Google Maps. Thứ hạng gợi ý vẫn tính trên dữ liệu của hệ thống.">
            <Star size={14} fill="currentColor" />{google.rating.toFixed(1)}
            {google.ratingCount != null && <span className="count">({google.ratingCount.toLocaleString('vi-VN')})</span>}<span className="src">Google</span></a>
          : <span className="star"><Star size={14} fill="currentColor" />{place.rating.toFixed(1)}</span>}
        <span><Wallet size={14} />{money(place.price_avg)}</span>
      </div>
      <div className="score-bar" title="Điểm TOPSIS so với các địa điểm cùng danh mục trong lần tìm này; không phải xác suất">
        <span>Điểm tổng hợp</span><i><b style={{ width: `${score}%` }} /></i><strong className="num">{score}</strong>
        <span>· hợp sở thích {Math.round(place.preference * 100)}</span>
      </div>
      <div className="place-tags">
        <button type="button" className="chip" style={{ padding: '.3rem .7rem', fontSize: '.85rem' }} aria-expanded={why.state !== 'closed'} onClick={toggleWhy}><HelpCircle size={14} />Vì sao gợi ý?</button>
        <a className="chip" style={{ padding: '.3rem .7rem', fontSize: '.85rem' }} target="_blank" rel="noreferrer"
          href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${origin.latitude}%2C${origin.longitude}%3B${place.latitude}%2C${place.longitude}`}><Navigation size={14} />Chỉ đường</a>
      </div>
      {why.state !== 'closed' && <div className="why" role="status">
        {why.state === 'loading' ? 'Đang hỏi đồ thị tri thức…' : why.state === 'error' ? why.message : <>
          <strong>Theo đồ thị tri thức</strong>
          {why.reasons?.length ? <ul>{why.reasons.map(reason => <li key={reason.kind}>{reason.text}</li>)}</ul> : <p>Chưa có liên kết đáng chú ý cho địa điểm này.</p>}
        </>}
      </div>}
    </div>
    {onFeedback && <div className="place-actions">
      <button type="button" className="icon-btn" disabled={busy} aria-pressed={!!place.saved} aria-label={`${place.saved ? 'Bỏ thích' : 'Thích'} ${place.name}`} title={place.saved ? 'Bỏ thích' : 'Thích'}
        onClick={() => onFeedback(place.saved ? 'unlike' : 'like')}><Heart size={17} fill={place.saved ? 'currentColor' : 'none'} /></button>
      <button type="button" className="icon-btn visit" disabled={busy} aria-pressed={!!place.visited} aria-label={`${place.visited ? 'Bỏ đánh dấu đã ghé' : 'Đánh dấu đã ghé'} ${place.name}`} title={place.visited ? 'Bỏ đánh dấu đã ghé' : 'Đã ghé'}
        onClick={() => onFeedback(place.visited ? 'unvisit' : 'visit')}><Check size={17} /></button>
    </div>}
  </article>;
}
