import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';
import { hashPassword } from './auth/password';
import { isJunkPoiName, normalizeDistrict } from './database/display';
import { demoUsers } from './database/init';
import { ModelSettings } from './settings/settings';
import { AccountRow, FeedbackAction, Poi } from './store';

type Csv = Record<string, string>;

/**
 * Store without MySQL (STORE=memory): the catalog comes straight from the CSV files and accounts,
 * settings and feedback live in memory until the API restarts. For demos on a machine without Docker.
 */
export class MemoryStore {
  private readonly catalog: Poi[];
  private readonly hourly = new Map<number, Map<number, number>>();
  private readonly visits = new Map<number, Set<number>>();
  private readonly sha: string;
  private readonly users: number;
  private readonly checkins: number;
  private readonly accounts: AccountRow[] = [];
  private readonly accountSettings = new Map<number, ModelSettings>();
  private feedbackRows: { accountId: number; poiId: number; action: FeedbackAction }[] = [];
  private readonly ready: Promise<void>;
  // Ids differ on every start, so a cookie from before a restart cannot match a new account.
  private nextId = Math.floor(Date.now() / 1000);

  constructor() {
    const dataDir = resolve(process.env.DATA_DIR || '../../data/danang');
    const poiBytes = readFileSync(resolve(dataDir, 'danang_pois_full.csv'));
    const eventBytes = readFileSync(resolve(dataDir, 'danang_checkins_full.csv'));
    const pois = parse(poiBytes, { columns: true, skip_empty_lines: true, bom: true }) as Csv[];
    const events = parse(eventBytes, { columns: true, skip_empty_lines: true, bom: true }) as Csv[];
    this.sha = createHash('sha256').update(poiBytes).update(eventBytes).digest('hex');
    this.catalog = pois.map(p => ({ id: Number(p.l), name: p.name, category: p.category, district: normalizeDistrict(p.district),
      latitude: Number(p.lat), longitude: Number(p.lon), rating: Number(p.rating), price_avg: Number(p.price_avg),
      popularity: Number(p.popularity), hidden: isJunkPoiName(p.name, p.category) })).sort((a, b) => a.id - b.id);
    for (const e of events) {
      const hour = Number(e.hour), poi = Number(e.l), user = Number(e.u);
      const byPoi = this.hourly.get(hour) || new Map<number, number>();
      byPoi.set(poi, (byPoi.get(poi) || 0) + 1);
      this.hourly.set(hour, byPoi);
      this.visits.set(user, (this.visits.get(user) || new Set<number>()).add(poi));
    }
    this.users = this.visits.size;
    this.checkins = events.length;
    this.ready = this.seedDemo(pois, events);
  }

  private async seedDemo(pois: Csv[], events: Csv[]) {
    const password = process.env.DEMO_PASSWORD;
    if (!password || password.length < 8) return;
    for (const demo of demoUsers(pois, events)) {
      this.accounts.push({ id: this.nextId++, username: demo.username, displayName: demo.displayName,
        passwordHash: await hashPassword(password), datasetUserId: demo.datasetUserId, interests: [...demo.interests].sort() });
    }
  }

  async ping() { await this.ready; }
  async pois() { return this.catalog; }
  async stats() { return { pois: this.catalog.length, users: this.users, checkins: this.checkins, accounts: this.accounts.length }; }
  async datasetSha() { return this.sha; }
  async hourlyCounts(hour: number) { return this.hourly.get(hour) || new Map<number, number>(); }
  async visitedByDatasetUser(userId: number) { return [...(this.visits.get(userId) || [])]; }
  async accountByUsername(username: string) { await this.ready; return this.accounts.find(a => a.username === username) || null; }
  async accountById(id: number) { await this.ready; return this.accounts.find(a => a.id === id) || null; }
  async createAccount(input: { username: string; displayName: string; passwordHash: string; interests: string[] }) {
    await this.ready;
    if (this.accounts.some(a => a.username === input.username)) return null;
    const account: AccountRow = { id: this.nextId++, datasetUserId: null, ...input, interests: [...input.interests].sort() };
    this.accounts.push(account);
    return account;
  }
  async demoAccounts() { await this.ready; return this.accounts.filter(a => a.datasetUserId !== null).map(a => ({ username: a.username, displayName: a.displayName })); }
  async settings(accountId: number) { return this.accountSettings.get(accountId) || null; }
  async saveSettings(accountId: number, settings: ModelSettings) { this.accountSettings.set(accountId, settings); }
  async deleteSettings(accountId: number) { this.accountSettings.delete(accountId); }
  async feedback(accountId: number) {
    return this.feedbackRows.filter(f => f.accountId === accountId).map(({ poiId, action }) => ({ poiId, action })).reverse();
  }
  async addFeedback(accountId: number, poiId: number, action: FeedbackAction) {
    if (!this.feedbackRows.some(f => f.accountId === accountId && f.poiId === poiId && f.action === action)) this.feedbackRows.push({ accountId, poiId, action });
  }
  async removeFeedback(accountId: number, poiId: number, action: FeedbackAction) {
    this.feedbackRows = this.feedbackRows.filter(f => !(f.accountId === accountId && f.poiId === poiId && f.action === action));
  }
}
