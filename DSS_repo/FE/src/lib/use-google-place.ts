'use client';
import { useEffect, useRef, useState } from 'react';
import { api } from './api';

export type GooglePlace = {
  available: true; rating: number | null; ratingCount: number | null; mapsUrl: string | null;
  photoUrl: string | null; photoAuthors: { name: string; url: string | null }[];
};
type Answer = GooglePlace | { available: false; reason: 'disabled' | 'unmatched' | 'limit' | 'error' };

// One request per place per page load, shared by every card that shows it.
const cache = new Map<number, Promise<Answer>>();
// Once the API says the feature is off (no key, or today's ceiling reached), stop asking.
let off = false;

function load(id: number): Promise<Answer> {
  let pending = cache.get(id);
  if (!pending) {
    pending = api<Answer>(`pois/${id}/google`).catch((): Answer => ({ available: false, reason: 'error' }));
    pending.then(answer => { if (!answer.available && (answer.reason === 'disabled' || answer.reason === 'limit')) off = true; });
    cache.set(id, pending);
  }
  return pending;
}

/**
 * Photo and rating from Google Maps for a place, fetched only when its card scrolls into view.
 * Returns null while loading and whenever Google has nothing for it; the card then shows what it always did.
 */
export function useGooglePlace<T extends HTMLElement>(id: number) {
  const ref = useRef<T>(null);
  const [place, setPlace] = useState<GooglePlace | null>(null);
  useEffect(() => {
    setPlace(null);
    const node = ref.current;
    if (!node || off) return;
    let alive = true;
    const start = () => load(id).then(answer => { if (alive && answer.available) setPlace(answer); });
    if (cache.has(id) || typeof IntersectionObserver === 'undefined') { start(); return () => { alive = false; }; }
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      observer.disconnect();
      if (!off) start();
    }, { rootMargin: '200px' });
    observer.observe(node);
    return () => { alive = false; observer.disconnect(); };
  }, [id]);
  return { ref, place };
}
