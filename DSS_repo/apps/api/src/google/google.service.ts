import { Injectable } from '@nestjs/common';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';

export type GooglePlace =
  | { available: false; reason: 'disabled' | 'unmatched' | 'limit' | 'error' }
  | { available: true; rating: number | null; ratingCount: number | null; mapsUrl: string | null;
      photoUrl: string | null; photoAuthors: { name: string; url: string | null }[] };

export type PlacePhoto = { url: string; caption: string; sourceUrl: string | null; sourceHost: string };
export type PlaceReview = { text: string; source: string; url: string | null };
export type PlacePreview =
  | { available: false }
  | {
      available: true;
      address: string | null;
      phone: string | null;
      externalRating: number | null;
      externalUrl: string | null;
      photos: PlacePhoto[];
      reviews: PlaceReview[];
    };

type PoiMeta = { id: number; name: string; category: string; district: string; lat: number; lon: number };
type Details = { rating?: number; userRatingCount?: number; googleMapsUri?: string;
  photos?: { name: string; authorAttributions?: { displayName?: string; uri?: string }[] }[] };

const STOCK_DOMAINS = /freepik\.|shutterstock\.|solidbackgrounds\.|vecteezy\.|istockphoto\.|pixabay\.|pexels\.|123rf\.|wallpapers\.|telescopictube\.|pinterest\./i;
const TRUSTED_DOMAINS = /tripadvisor\.|foody\.vn|mia\.vn|khamphadanang\.|bestnhat\.|pasgo\.|vinpearl\.|klook\.|traveloka\.|booking\.|agoda\.|archdaily\.|danang|vietnam/i;
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

function decodeHtml(raw: string): string {
  return raw
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\s+/g, ' ')
    .trim();
}

function normText(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
}

/**
 * Live photo and rating from Google Places for catalog POIs that tools/match_google_places.py matched,
 * plus keyless multi-photo and real review preview from CocCoc Map + Bing Images + review pages.
 */
@Injectable()
export class GoogleService {
  private readonly ids = new Map<number, string>();
  private readonly pois = new Map<number, PoiMeta>();
  private readonly cache = new Map<number, { at: number; value: GooglePlace }>();
  private readonly pending = new Map<number, Promise<GooglePlace>>();
  private readonly previewCache = new Map<number, { at: number; value: PlacePreview }>();
  private readonly previewPending = new Map<number, Promise<PlacePreview>>();
  private day = '';
  private used = 0;

  constructor() {
    const dataDir = resolve(process.env.DATA_DIR || '../../data/danang');
    const poiFile = resolve(dataDir, 'danang_pois_full.csv');
    if (existsSync(poiFile)) {
      const rows = parse(readFileSync(poiFile), { columns: true, bom: true, skip_empty_lines: true }) as Record<string, string>[];
      for (const r of rows) {
        const id = Number(r.l);
        if (!Number.isNaN(id) && r.name) {
          this.pois.set(id, { id, name: r.name, category: r.category || '', district: r.district || '', lat: Number(r.lat), lon: Number(r.lon) });
        }
      }
    }
    const file = resolve(process.env.GOOGLE_PLACE_IDS_FILE || resolve(dataDir, 'google_place_ids.csv'));
    if (!existsSync(file)) return;
    const rows = parse(readFileSync(file), { columns: true, bom: true, skip_empty_lines: true }) as { l: string; place_id: string }[];
    for (const row of rows) if (row.place_id) this.ids.set(Number(row.l), row.place_id);
  }

  private get key() { return process.env.GOOGLE_PLACES_API_KEY || ''; }
  get enabled() { return !!this.key && this.ids.size > 0; }
  get matched() { return this.ids.size; }

  async place(poiId: number): Promise<GooglePlace> {
    if (!this.enabled) return { available: false, reason: 'disabled' };
    const placeId = this.ids.get(poiId);
    if (!placeId) return { available: false, reason: 'unmatched' };
    const ttl = Number(process.env.GOOGLE_PLACES_CACHE_MINUTES || 360) * 60_000;
    const hit = this.cache.get(poiId);
    if (hit && Date.now() - hit.at < ttl) return hit.value;
    const running = this.pending.get(poiId);
    if (running) return running;

    const today = new Date().toISOString().slice(0, 10);
    if (today !== this.day) { this.day = today; this.used = 0; }
    if (this.used >= Number(process.env.GOOGLE_PLACES_DAILY_LIMIT || 300)) return { available: false, reason: 'limit' };
    this.used++;

    const task = this.fetchPlace(placeId)
      .then(value => { this.cache.set(poiId, { at: Date.now(), value }); return value; })
      // Failures are not cached for long: a brief outage should not blank the card for hours.
      .catch((): GooglePlace => { this.cache.set(poiId, { at: Date.now() - ttl + 60_000, value: { available: false, reason: 'error' } }); return { available: false, reason: 'error' }; })
      .finally(() => this.pending.delete(poiId));
    this.pending.set(poiId, task);
    return task;
  }

  private async fetchPlace(placeId: string): Promise<GooglePlace> {
    const base = process.env.GOOGLE_PLACES_URL || 'https://places.googleapis.com/v1';
    const headers = { 'X-Goog-Api-Key': this.key };
    const res = await fetch(`${base}/places/${encodeURIComponent(placeId)}?languageCode=vi`, {
      headers: { ...headers, 'X-Goog-FieldMask': 'rating,userRatingCount,googleMapsUri,photos' }, signal: AbortSignal.timeout(6000) });
    if (!res.ok) throw new Error(`Place Details ${res.status}`);
    const details = await res.json() as Details;
    const photo = details.photos?.[0];
    let photoUrl: string | null = null;
    if (photo?.name) {
      // skipHttpRedirect returns the image address as JSON, so the browser never sees the API key.
      const media = await fetch(`${base}/${photo.name}/media?maxWidthPx=480&skipHttpRedirect=true`, { headers, signal: AbortSignal.timeout(6000) });
      if (media.ok) photoUrl = (await media.json() as { photoUri?: string }).photoUri || null;
    }
    return {
      available: true, rating: details.rating ?? null, ratingCount: details.userRatingCount ?? null, mapsUrl: details.googleMapsUri ?? null, photoUrl,
      photoAuthors: photoUrl ? (photo?.authorAttributions || []).filter(a => a.displayName).map(a => ({
        name: a.displayName as string, url: a.uri ? (a.uri.startsWith('//') ? `https:${a.uri}` : a.uri) : null })) : [],
    };
  }

  async preview(poiId: number): Promise<PlacePreview> {
    const poi = this.pois.get(poiId);
    if (!poi) return { available: false };
    const ttl = Number(process.env.GOOGLE_PLACES_CACHE_MINUTES || 360) * 60_000;
    const hit = this.previewCache.get(poiId);
    if (hit && Date.now() - hit.at < ttl) return hit.value;
    const running = this.previewPending.get(poiId);
    if (running) return running;

    const task = this.fetchPreview(poi)
      .then(value => { this.previewCache.set(poiId, { at: Date.now(), value }); return value; })
      .catch((): PlacePreview => ({ available: false }))
      .finally(() => this.previewPending.delete(poiId));
    this.previewPending.set(poiId, task);
    return task;
  }

  private async fetchPreview(poi: PoiMeta): Promise<PlacePreview> {
    const cleanName = poi.name.replace(/[()]/g, ' ').replace(/\s+/g, ' ').trim();
    const [cc, bingPhotos] = await Promise.all([
      this.fetchCocCoc(cleanName, poi),
      this.fetchBingPhotos(cleanName, poi),
    ]);

    const photos: PlacePhoto[] = [];
    const seenUrls = new Set<string>();
    if (cc?.photoUrl) {
      seenUrls.add(cc.photoUrl);
      photos.push({
        url: cc.photoUrl,
        caption: `${poi.name}${cc.address ? ` · ${cc.address}` : ''}`,
        sourceUrl: cc.sourceUrl,
        sourceHost: cc.sourceHost || 'map.coccoc.com',
      });
    }
    for (const p of bingPhotos) {
      if (!seenUrls.has(p.url) && photos.length < 5) {
        seenUrls.add(p.url);
        photos.push(p);
      }
    }

    const candidateUrls: { url: string; host: string; fallbackTitle: string }[] = [];
    const seenHosts = new Set<string>();
    if (cc?.sourceUrl && cc.sourceHost) {
      seenHosts.add(cc.sourceHost);
      candidateUrls.push({ url: cc.sourceUrl, host: cc.sourceHost, fallbackTitle: '' });
    }
    for (const p of photos) {
      if (p.sourceUrl && p.sourceHost && !seenHosts.has(p.sourceHost) && candidateUrls.length < 3) {
        seenHosts.add(p.sourceHost);
        candidateUrls.push({ url: p.sourceUrl, host: p.sourceHost, fallbackTitle: p.caption });
      }
    }

    const metaReviews = await Promise.all(candidateUrls.slice(0, 2).map(c => this.fetchMetaDescription(c.url, c.host)));
    const reviews: PlaceReview[] = [];
    if (cc?.description && cc.description.length > 20) {
      reviews.push({ text: cc.description, source: cc.sourceHost || 'Cốc Cốc Map', url: cc.sourceUrl });
    }
    for (const r of metaReviews) {
      if (r && !reviews.some(x => x.text === r.text)) reviews.push(r);
    }
    for (const p of photos) {
      if (reviews.length >= 2) break;
      if (p.caption && p.caption.length >= 28 && !reviews.some(x => x.text.includes(p.caption))) {
        reviews.push({ text: p.caption, source: p.sourceHost || 'Web Review', url: p.sourceUrl });
      }
    }

    if (!photos.length && !reviews.length && !cc?.address) return { available: false };
    return {
      available: true,
      address: cc?.address ?? null,
      phone: cc?.phone ?? null,
      externalRating: cc?.rating ?? null,
      externalUrl: cc?.sourceUrl || photos[0]?.sourceUrl || null,
      photos: photos.slice(0, 4),
      reviews: reviews.slice(0, 2),
    };
  }

  private async fetchCocCoc(cleanName: string, poi: PoiMeta) {
    try {
      const url = `https://map.coccoc.com/composer/vertical/poi/search?q=${encodeURIComponent(cleanName)}&borders=15.95,108.10,16.15,108.30&user_gps=${poi.lat},${poi.lon}&result_cnt=5&appid=poi-service`;
      const res = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(3500) });
      if (!res.ok) return null;
      const body = await res.json() as { result?: Record<string, unknown>[] };
      const list = Array.isArray(body?.result) ? body.result : [];
      const nameWords = normText(cleanName).split(/\s+/).filter(w => w.length >= 2);
      const match = list.find(item => {
        const inDaNang = item.region_id === 17 || String(item.address || '').includes('Đà Nẵng');
        if (!inDaNang) return false;
        const rawTitle = normText(String(item.raw_title || item.title || ''));
        const dist = typeof item.distance === 'number' ? item.distance : 99999;
        const wordHits = nameWords.filter(w => rawTitle.includes(w)).length;
        return (dist <= 900 && wordHits >= 1) || (wordHits >= Math.max(1, Math.ceil(nameWords.length * 0.6)));
      });
      if (!match) return null;
      const rawImg = String(match.img || '').trim();
      const photoUrl = rawImg ? (rawImg.startsWith('//') ? `https:${rawImg}` : rawImg) : null;
      const extUrl = String(match.url || '').trim() || (match.hash_new ? `https://map.coccoc.com/map/${match.hash_new}` : null);
      let sourceHost = 'map.coccoc.com';
      if (extUrl) {
        try { sourceHost = new URL(extUrl).hostname.replace(/^www\./, ''); } catch {}
      }
      const rating = typeof match.rating === 'number' && match.rating > 0 ? Number(match.rating.toFixed(1)) : null;
      return {
        address: String(match.address || '').trim() || null,
        phone: String(match.phone || '').trim() || null,
        description: decodeHtml(String(match.description || '')),
        rating,
        photoUrl,
        sourceUrl: extUrl,
        sourceHost,
      };
    } catch {
      return null;
    }
  }

  private async fetchBingPhotos(cleanName: string, poi: PoiMeta): Promise<PlacePhoto[]> {
    try {
      const q = `${cleanName} Đà Nẵng`;
      const url = `https://www.bing.com/images/search?q=${encodeURIComponent(q)}&form=HDRSC2`;
      const res = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8' }, signal: AbortSignal.timeout(4000) });
      if (!res.ok) return [];
      const html = await res.text();
      const nameWords = normText(cleanName).split(/\s+/).filter(w => w.length >= 3 && !['nha', 'hang', 'quan', 'cafe', 'coffee', 'restaurant', 'hotel', 'bar', 'danang'].includes(w));
      const candidates: { photo: PlacePhoto; score: number }[] = [];
      const re = /m="(\{[^"]+\})"/g;
      let m: RegExpExecArray | null;
      while ((m = re.exec(html)) !== null && candidates.length < 24) {
        try {
          const item = JSON.parse(decodeHtml(m[1])) as { turl?: string; purl?: string; t?: string };
          if (!item.turl || !item.t) continue;
          const purl = item.purl || '';
          if (purl && STOCK_DOMAINS.test(purl)) continue;
          let host = '';
          if (purl) {
            try { host = new URL(purl).hostname.replace(/^www\./, ''); } catch {}
          }
          const caption = decodeHtml(item.t).replace(/\s*\.\.\.$/, '').trim();
          const normAll = normText(`${caption} ${purl}`);
          let score = 0;
          for (const w of nameWords) if (normAll.includes(w)) score += 4;
          if (/da nang|danang/.test(normAll)) score += 3;
          if (TRUSTED_DOMAINS.test(purl)) score += 2;
          candidates.push({
            score,
            photo: { url: item.turl, caption, sourceUrl: purl || null, sourceHost: host || 'Bing Images' },
          });
        } catch {}
      }
      candidates.sort((a, b) => b.score - a.score);
      return candidates.slice(0, 5).map(c => c.photo);
    } catch {
      return [];
    }
  }

  private async fetchMetaDescription(url: string, host: string): Promise<PlaceReview | null> {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'vi-VN,vi;q=0.9' }, signal: AbortSignal.timeout(2500) });
      if (!res.ok) return null;
      const html = (await res.text()).slice(0, 45_000);
      const match =
        html.match(/<meta[^>]+(?:name=["']description["']|property=["']og:description["'])[^>]+content=["']([^"']{25,400})["']/i) ||
        html.match(/<meta[^>]+content=["']([^"']{25,400})["'][^>]+(?:name=["']description["']|property=["']og:description["'])/i);
      if (!match?.[1]) return null;
      const text = decodeHtml(match[1]);
      if (text.length < 25) return null;
      return { text, source: host, url };
    } catch {
      return null;
    }
  }
}
