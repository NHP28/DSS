import { Injectable } from '@nestjs/common';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';

export type GooglePlace =
  | { available: false; reason: 'disabled' | 'unmatched' | 'limit' | 'error' }
  | { available: true; rating: number | null; ratingCount: number | null; mapsUrl: string | null;
      photoUrl: string | null; photoAuthors: { name: string; url: string | null }[] };

type Details = { rating?: number; userRatingCount?: number; googleMapsUri?: string;
  photos?: { name: string; authorAttributions?: { displayName?: string; uri?: string }[] }[] };

/**
 * Live photo and rating from Google Places for catalog POIs that tools/match_google_places.py matched.
 * Only place ids are stored on disk; everything else is fetched on demand and kept in memory for a
 * few hours, with a daily ceiling on billable lookups.
 */
@Injectable()
export class GoogleService {
  private readonly ids = new Map<number, string>();
  private readonly cache = new Map<number, { at: number; value: GooglePlace }>();
  private readonly pending = new Map<number, Promise<GooglePlace>>();
  private day = '';
  private used = 0;

  constructor() {
    const file = resolve(process.env.GOOGLE_PLACE_IDS_FILE || resolve(process.env.DATA_DIR || '../../data/danang', 'google_place_ids.csv'));
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
}
