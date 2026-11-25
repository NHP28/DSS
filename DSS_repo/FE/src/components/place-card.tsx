'use client';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronLeft, ChevronRight, ExternalLink, Heart, HelpCircle, MapPin, Navigation, Sparkles, Star, Wallet, X, ZoomIn } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { categories, money, type Place } from '@/lib/types';
import { useGooglePlace } from '@/lib/use-google-place';

type Reason = { kind: string; text: string };
type Props = {
  place: Place; selected?: boolean; showCategory?: boolean; hour: number; origin: { latitude: number; longitude: number };
  onSelect?: () => void; onFeedback?: (action: 'like' | 'unlike' | 'visit' | 'unvisit') => void; busy?: boolean;
};

function describePlace(place: Place, hour: number): { tag: string; caption: string; queryHint: string } {
  const text = `${place.name} ${place.district}`.toLocaleLowerCase('vi');
  if (/chay|vegan|vegetarian/.test(text)) return { tag: '🌱 Ẩm thực chay thanh đạm', caption: 'Món chay · Đà Nẵng', queryHint: 'nhà hàng chay' };
  if (/indian|maharaja|curry|halal|ấn độ|an do/.test(text)) return { tag: '🍛 Hương vị Ấn Độ đặc sắc', caption: 'Ẩm thực Ấn Độ', queryHint: 'Indian restaurant' };
  if (/bar|pub|lounge|club|sky|beer|bia|cocktail/.test(text)) return { tag: '🍸 Không gian chill & đồ uống', caption: 'Bar & Lounge', queryHint: 'bar restaurant' };
  if (/hải sản|hai san|seafood|cá|ốc|oc|tôm|cua|bé mặn|be man/.test(text)) return { tag: '🦞 Hải sản tươi sống biển Đà Nẵng', caption: 'Hải sản địa phương', queryHint: 'hải sản' };
  if (/mì quảng|mi quang|bún|bun|phở|pho|bánh xèo|banh xeo|bánh tráng|banh trang|cơm|com/.test(text)) return { tag: '🍜 Hương vị truyền thống bản địa', caption: 'Đặc sản miền Trung', queryHint: 'ẩm thực đặc sản' };
  if (/bbq|nướng|nuong|lẩu|lau|grill|steak|bò|bo/.test(text)) return { tag: '🔥 Đồ nướng & bàn tiệc ấm cúng', caption: 'Nướng & Lẩu', queryHint: 'BBQ grill restaurant' };
  if (/pizza|pasta|italian|burger|bistro|âu|french/.test(text)) return { tag: '🍕 Phong cách ẩm thực Âu', caption: 'Nhà hàng Âu', queryHint: 'western restaurant' };
  if (/nhật|nhat|sushi|ramen|izakaya|japan/.test(text)) return { tag: '🍣 Tinh hoa ẩm thực Nhật Bản', caption: 'Ẩm thực Nhật', queryHint: 'Japanese restaurant' };
  if (/hàn|han|korea|kimchi|tokbokki|k-food/.test(text)) return { tag: '🥘 Ẩm thực Hàn Quốc trẻ trung', caption: 'Ẩm thực Hàn', queryHint: 'Korean restaurant' };
  if (/roaster|factory|specialty|espresso|arabica/.test(text)) return { tag: '☕ Cà phê rang xay thủ công', caption: 'Specialty Coffee', queryHint: 'specialty coffee' };
  if (/trà|tra|tea|bánh|banh|bakery|cake|kem|ice cream|sweet/.test(text)) return { tag: '🧋 Trà thơm & bánh ngọt thư giãn', caption: 'Trà & Bánh ngọt', queryHint: 'cafe bakery' };
  if (/garden|vườn|vuon|xanh|tree|acoustic|lake/.test(text)) return { tag: '🌿 Không gian thoáng đãng, xanh mát', caption: 'Không gian mở', queryHint: 'garden cafe' };
  if (/resort|villa|spa|boutique/.test(text)) return { tag: '🏖️ Nghỉ dưỡng tiện nghi cao cấp', caption: 'Resort & Nghỉ dưỡng', queryHint: 'resort hotel' };
  if (/homestay|hostel|appart|studio/.test(text)) return { tag: '🏡 Lưu trú ấm cúng, gần gũi', caption: 'Homestay & Lưu trú', queryHint: 'homestay hotel' };
  if (/biển|bien|beach|mỹ khê|my khe|sơn trà|son tra/.test(text)) return { tag: '🌊 Điểm dạo biển & ngắm cảnh', caption: 'Cảnh biển Đà Nẵng', queryHint: 'beach attraction' };
  if (/chùa|chua|linh ứng|linh ung|nhà thờ|nha tho|bảo tàng|bao tang|museum|pagoda/.test(text)) return { tag: '🏛️ Điểm văn hóa & kiến trúc', caption: 'Văn hóa & Di sản', queryHint: 'điểm tham quan' };
  if (/cầu|cau|bridge|rồng|rong|bà nà|ba na|núi|nui|ngũ hành|ngu hanh/.test(text)) return { tag: '📸 Tọa độ check-in biểu tượng', caption: 'Thắng cảnh nổi bật', queryHint: 'thắng cảnh du lịch' };

  if (place.category === 'cafe') {
    return {
      tag: hour < 11 ? '☕ Góc cà phê sáng lý tưởng' : hour < 17 ? '☕ Không gian làm việc & trò chuyện' : '✨ Quán cà phê tối thư giãn',
      caption: `Quán cà phê · ${place.district}`,
      queryHint: 'quán cà phê',
    };
  }
  if (place.category === 'restaurant') {
    return {
      tag: hour < 10 ? '🥢 Điểm ăn sáng được yêu thích' : hour < 15 ? '🍽️ Bữa trưa ngon miệng, đậm vị' : '🍲 Điểm hẹn ẩm thực buổi tối',
      caption: `Ẩm thực · ${place.district}`,
      queryHint: 'nhà hàng quán ăn',
    };
  }
  if (place.category === 'hotel') {
    return { tag: '🛏️ Điểm lưu trú thuận tiện di chuyển', caption: `Lưu trú · ${place.district}`, queryHint: 'khách sạn hotel' };
  }
  return { tag: '🧭 Điểm khám phá & trải nghiệm', caption: `Tham quan · ${place.district}`, queryHint: 'địa điểm du lịch' };
}

function buildFallbackPhotoUrl(place: Place, queryHint: string): string {
  const q = `${place.name} ${queryHint} ${place.district} Đà Nẵng`;
  return `https://tse1.mm.bing.net/th?q=${encodeURIComponent(q)}&w=320&h=240&c=7&rs=1&p=0`;
}

export default function PlaceCard({ place, selected, showCategory, hour, origin, onSelect, onFeedback, busy }: Props) {
  const [why, setWhy] = useState<{ state: 'closed' | 'loading' | 'ready' | 'error'; reasons?: Reason[]; message?: string }>({ state: 'closed' });
  const [activeIdx, setActiveIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [failedUrls, setFailedUrls] = useState<Record<string, boolean>>({});
  const trackRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setActiveIdx(0); setLightboxOpen(false); setFailedUrls({}); }, [place.id]);

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
  const { ref, place: google, preview } = useGooglePlace<HTMLElement>(place.id);
  const info = describePlace(place, hour);
  const mapsSearchUrl = google?.mapsUrl || preview?.externalUrl || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${place.name} ${place.district} Đà Nẵng`)}`;

  const gallery = (preview?.photos || []).filter(p => !failedUrls[p.url]);
  if (google?.photoUrl && !failedUrls[google.photoUrl] && !gallery.some(p => p.url === google.photoUrl)) {
    gallery.unshift({
      url: google.photoUrl,
      caption: google.photoAuthors.map(a => a.name).join(', ') || 'Google Maps',
      sourceUrl: google.mapsUrl,
      sourceHost: 'Google Maps',
    });
  }
  if (!gallery.length) {
    const fallbackUrl = buildFallbackPhotoUrl(place, info.queryHint);
    if (!failedUrls[fallbackUrl]) {
      gallery.push({ url: fallbackUrl, caption: info.caption, sourceUrl: mapsSearchUrl, sourceHost: info.caption });
    }
  }

  const slideTo = (index: number) => {
    if (!gallery.length) return;
    const clamped = (index + gallery.length) % gallery.length;
    setActiveIdx(clamped);
    const track = trackRef.current;
    const item = track?.children[clamped] as HTMLElement | undefined;
    if (track && item) {
      track.scrollTo({ left: item.offsetLeft - 4, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    if (!lightboxOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightboxOpen(false);
      else if (e.key === 'ArrowLeft') slideTo(activeIdx - 1);
      else if (e.key === 'ArrowRight') slideTo(activeIdx + 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const currentPhoto = gallery[Math.min(activeIdx, Math.max(0, gallery.length - 1))] || null;
  const reviews = preview?.reviews || [];
  const score = Math.round(place.topsisScore * 100);
  const highlights: string[] = [info.tag];
  if (place.distanceKm <= 0.8) highlights.push('📍 Rất gần bạn');
  else if (place.rating >= 4.6) highlights.push('⭐ Đánh giá nổi bật');
  else if (place.price_avg > 0 && place.price_avg <= 45000) highlights.push('💸 Giá hợp lý');

  return <article ref={ref} id={`place-${place.id}`} className={`place${selected ? ' selected' : ''}`} style={{ ['--cat' as string]: `var(--${place.category})` }}>
    <div className="place-rank" title={`Hạng ${place.rank} trong ${categories[place.category]?.label}`}>{place.rank}</div>
    <div>
      <h3><button type="button" onClick={onSelect}>{place.name}</button></h3>
      <div className="place-meta">
        {showCategory && <span>{categories[place.category]?.symbol} {categories[place.category]?.label}</span>}
        <span><MapPin size={14} />{preview?.address ? `${preview.address} · ${place.distanceKm.toFixed(1)} km` : `${place.district} · ${place.distanceKm.toFixed(1)} km`}</span>
        {google?.rating != null
          ? <a className="star google" href={google.mapsUrl || undefined} target="_blank" rel="noreferrer" title="Điểm đánh giá thật trên Google Maps. Thứ hạng gợi ý vẫn tính trên dữ liệu của hệ thống.">
            <Star size={14} fill="currentColor" />{google.rating.toFixed(1)}
            {google.ratingCount != null && <span className="count">({google.ratingCount.toLocaleString('vi-VN')})</span>}<span className="src">Google</span></a>
          : preview?.externalRating != null
            ? <a className="star google" href={preview.externalUrl || undefined} target="_blank" rel="noreferrer" title="Điểm đánh giá thực tế từ bản đồ địa phương">
              <Star size={14} fill="currentColor" />{preview.externalRating.toFixed(1)}<span className="src">Thực tế</span></a>
            : <span className="star"><Star size={14} fill="currentColor" />{place.rating.toFixed(1)}</span>}
        <span><Wallet size={14} />{money(place.price_avg)}</span>
      </div>
      <div className="row" style={{ gap: '.35rem', marginTop: '.4rem' }}>
        {highlights.map(item => <span key={item} className="badge plain" style={{ fontSize: '.76rem', padding: '.15rem .55rem' }}>{item}</span>)}
      </div>
      <div className="score-bar" title="Điểm TOPSIS so với các địa điểm cùng danh mục trong lần tìm này; không phải xác suất">
        <span>Điểm tổng hợp</span><i><b style={{ width: `${score}%` }} /></i><strong className="num">{score}</strong>
        <span>· hợp sở thích {Math.round(place.preference * 100)}</span>
      </div>
      {reviews.length > 0 && <div className="place-reviews">
        {reviews.map((rev, idx) => <blockquote key={idx} className="place-review-quote">
          “{rev.text}”
          {rev.url ? <a href={rev.url} target="_blank" rel="noreferrer" className="place-review-src">— {rev.source}</a> : <span className="place-review-src">— {rev.source}</span>}
        </blockquote>)}
      </div>}
      <div className="place-tags">
        <button type="button" className="chip" style={{ padding: '.3rem .7rem', fontSize: '.85rem' }} aria-expanded={why.state !== 'closed'} onClick={toggleWhy}><HelpCircle size={14} />Vì sao gợi ý?</button>
        <a className="chip" style={{ padding: '.3rem .7rem', fontSize: '.85rem' }} target="_blank" rel="noreferrer"
          href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${origin.latitude}%2C${origin.longitude}%3B${place.latitude}%2C${place.longitude}`}><Navigation size={14} />Chỉ đường</a>
        <a className="chip" style={{ padding: '.3rem .7rem', fontSize: '.85rem' }} target="_blank" rel="noreferrer"
          href={mapsSearchUrl} title="Xem thêm hình ảnh và đánh giá thực tế"><ExternalLink size={14} />Ảnh & Review</a>
      </div>
      {why.state !== 'closed' && <div className="why" role="status">
        {why.state === 'loading' ? 'Đang hỏi đồ thị tri thức…' : why.state === 'error' ? why.message : <>
          <strong><Sparkles size={14} style={{ display: 'inline', verticalAlign: '-2px', marginRight: 4 }} />Theo đồ thị tri thức</strong>
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
    {gallery.length > 0 && <div className="place-slider-wrap">
      {gallery.length > 1 && <button type="button" className="place-slide-nav prev" onClick={() => slideTo(activeIdx - 1)} aria-label="Ảnh trước">
        <ChevronLeft size={16} />
      </button>}
      <div className="place-slider" ref={trackRef}>
        {gallery.map((img, idx) => <figure key={img.url} className={`place-slide${idx === activeIdx ? ' active' : ''}`}
          onClick={() => { setActiveIdx(idx); setLightboxOpen(true); }} title="Bấm để phóng to ảnh">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.url} alt={img.caption || `${place.name} - ảnh ${idx + 1}`} loading="lazy" referrerPolicy="no-referrer"
            onError={() => setFailedUrls(prev => ({ ...prev, [img.url]: true }))} />
          <span className="slide-zoom" aria-hidden="true"><ZoomIn size={13} /></span>
          <figcaption>
            <span className="slide-caption">{img.caption || place.name}</span>
          </figcaption>
        </figure>)}
      </div>
      {gallery.length > 1 && <button type="button" className="place-slide-nav next" onClick={() => slideTo(activeIdx + 1)} aria-label="Ảnh tiếp theo">
        <ChevronRight size={16} />
      </button>}
    </div>}
    {lightboxOpen && currentPhoto && typeof document !== 'undefined' && createPortal(
      <div className="place-lightbox" role="dialog" aria-modal="true" aria-label={`Ảnh ${place.name}`} onClick={() => setLightboxOpen(false)}>
        <div className="place-lightbox-content" onClick={e => e.stopPropagation()}>
          <div className="place-lightbox-header">
            <div>
              <strong>{place.name}</strong>
              <span className="place-lightbox-count">Ảnh {Math.min(activeIdx + 1, gallery.length)} / {gallery.length}</span>
            </div>
            <button type="button" className="place-lightbox-close" onClick={() => setLightboxOpen(false)} aria-label="Đóng ảnh">
              <X size={20} />
            </button>
          </div>
          <div className="place-lightbox-stage">
            {gallery.length > 1 && <button type="button" className="place-lightbox-nav prev" onClick={() => slideTo(activeIdx - 1)} aria-label="Ảnh trước">
              <ChevronLeft size={24} />
            </button>}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={currentPhoto.url.includes('bing.net/th?') ? `${currentPhoto.url.replace(/&w=\d+&h=\d+/, '')}&w=900&h=650` : currentPhoto.url}
              alt={currentPhoto.caption || place.name} referrerPolicy="no-referrer" />
            {gallery.length > 1 && <button type="button" className="place-lightbox-nav next" onClick={() => slideTo(activeIdx + 1)} aria-label="Ảnh tiếp theo">
              <ChevronRight size={24} />
            </button>}
          </div>
          <div className="place-lightbox-caption">
            <p>{currentPhoto.caption || place.name}</p>
            {currentPhoto.sourceUrl && <a href={currentPhoto.sourceUrl} target="_blank" rel="noreferrer" className="chip" style={{ padding: '.25rem .65rem', fontSize: '.8rem' }}>
              <ExternalLink size={13} />Xem bài gốc ({currentPhoto.sourceHost})
            </a>}
          </div>
          {gallery.length > 1 && <div className="place-lightbox-thumbs">
            {gallery.map((img, idx) => <button type="button" key={img.url} className={`place-lightbox-thumb${idx === activeIdx ? ' active' : ''}`}
              onClick={() => slideTo(idx)} title={img.caption || `Ảnh ${idx + 1}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.url} alt="" referrerPolicy="no-referrer" />
            </button>)}
          </div>}
        </div>
      </div>,
      document.body
    )}
  </article>;
}
