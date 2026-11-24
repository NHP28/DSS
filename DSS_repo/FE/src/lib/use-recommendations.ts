'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { Recommendation } from './types';

/** Loads recommendations for `path` + `body`; reloads when either changes or when `reload()` is called. */
export function useRecommendations(path: string, body: Record<string, unknown> | null, deps: unknown[] = []) {
  const [result, setResult] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const latest = useRef(0);
  const key = body ? JSON.stringify(body) : null;
  const reload = useCallback(async () => {
    if (!key) return;
    const id = ++latest.current;
    setLoading(true); setError('');
    try {
      const data = await api<Recommendation>(path, JSON.parse(key));
      if (id === latest.current) setResult(data);
    } catch (problem) {
      if (id === latest.current) { setError((problem as Error).message); setResult(null); }
    } finally { if (id === latest.current) setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, ...deps]);
  useEffect(() => { void reload(); }, [reload]);
  return { result, loading, error, reload };
}
