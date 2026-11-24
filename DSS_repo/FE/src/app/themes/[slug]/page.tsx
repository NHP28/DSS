'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Info } from 'lucide-react';
import { useAuth } from '@/components/auth-context';
import ResultsView from '@/components/results-view';
import { api } from '@/lib/api';
import { DANANG, type Theme } from '@/lib/types';
import { useRecommendations } from '@/lib/use-recommendations';

const moments = [{ label: 'Theo chủ đề', hour: undefined }, { label: 'Sáng 08:00', hour: 8 }, { label: 'Trưa 12:00', hour: 12 }, { label: 'Chiều 16:00', hour: 16 }, { label: 'Tối 20:00', hour: 20 }];

export default function ThemePage() {
  const { slug } = useParams<{ slug: string }>();
  const { account, loading: authLoading } = useAuth();
  const [themes, setThemes] = useState<Theme[]>([]);
  const [hour, setHour] = useState<number | undefined>(undefined);
  useEffect(() => { api<Theme[]>('themes').then(setThemes).catch(() => {}); }, []);
  useEffect(() => setHour(undefined), [slug]);
  const body = useMemo(() => authLoading ? null : { ...DANANG, ...(hour !== undefined ? { hour } : {}) }, [hour, authLoading]);
  const { result, loading, error, reload } = useRecommendations(`themes/${slug}/recommendations`, body, [account?.id]);
  const theme = result?.theme || themes.find(item => item.slug === slug);

  return <main className="wrap page stack" style={{ ['--gap' as string]: '1.5rem' }}>
    <nav className="tabs" aria-label="Chủ đề du lịch">
      {themes.map(item => <Link key={item.slug} href={`/themes/${item.slug}`} className={item.slug === slug ? 'chip on' : 'chip'} aria-current={item.slug === slug ? 'page' : undefined}>{item.symbol} {item.title}</Link>)}
    </nav>
    <header>
      <span className="eyebrow">Chủ đề du lịch</span>
      <h1 style={{ marginTop: '.8rem', fontSize: 'clamp(2rem,4.4vw,3.4rem)' }}>{theme ? <>{theme.symbol} {theme.title}</> : 'Chủ đề'}</h1>
      {theme && <p className="lede" style={{ marginTop: '.6rem' }}>{theme.tagline}.</p>}
    </header>
    {theme?.note && <div className="notice info"><Info size={18} /><span>{theme.note}</span></div>}
    <div className="row"><span className="small muted">Thời điểm:</span>
      {moments.map(moment => <button key={moment.label} className="chip" aria-pressed={hour === moment.hour} onClick={() => setHour(moment.hour)}>{moment.label}</button>)}
    </div>
    <ResultsView result={result} loading={loading} error={error} onRetry={() => void reload()} onChanged={() => void reload()}
      emptyHint="Chưa có địa điểm nào của chủ đề này quanh trung tâm vào thời điểm đã chọn. Thử thời điểm khác." />
  </main>;
}
