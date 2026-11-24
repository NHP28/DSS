import { Injectable } from '@nestjs/common';
import { DatabaseService } from './database/database.service';
import { ModelSettings } from './settings/settings';

export interface Poi {
  id: number; name: string; category: string; district: string;
  latitude: number; longitude: number; rating: number; price_avg: number; popularity: number;
  hidden: boolean;
}
export interface AccountRow {
  id: number; username: string; displayName: string; passwordHash: string;
  datasetUserId: number | null; interests: string[];
}
export type FeedbackAction = 'like' | 'visit';

/** Every SQL statement of the API lives here, so services can be tested against an in-memory fake. */
@Injectable()
export class Store {
  constructor(private readonly db: DatabaseService) {}

  async ping() { await this.db.query('SELECT 1 AS ok'); }

  async pois(): Promise<Poi[]> {
    const rows = await this.db.query('SELECT p.*, COALESCE(d.hidden, 0) AS hidden FROM pois p LEFT JOIN poi_display d ON d.poi_id = p.id ORDER BY p.id');
    return rows.map(row => ({ ...row, hidden: !!row.hidden })) as unknown as Poi[];
  }

  async stats() {
    const [row] = await this.db.query('SELECT (SELECT COUNT(*) FROM pois) AS pois,(SELECT COUNT(*) FROM users) AS users,(SELECT COUNT(*) FROM checkins) AS checkins,(SELECT COUNT(*) FROM accounts) AS accounts');
    return row as unknown as { pois: number; users: number; checkins: number; accounts: number };
  }

  async datasetSha(): Promise<string | null> {
    const [row] = await this.db.query('SELECT sha256 FROM dataset_meta WHERE id=1');
    return row ? String(row.sha256) : null;
  }

  async hourlyCounts(hour: number): Promise<Map<number, number>> {
    const rows = await this.db.query('SELECT poi_id,COUNT(*) AS count FROM checkins WHERE local_hour=? GROUP BY poi_id', [hour]);
    return new Map(rows.map(row => [Number(row.poi_id), Number(row.count)]));
  }

  async visitedByDatasetUser(userId: number): Promise<number[]> {
    const rows = await this.db.query('SELECT DISTINCT poi_id FROM checkins WHERE user_id=?', [userId]);
    return rows.map(row => Number(row.poi_id));
  }

  private async account(where: string, value: string | number): Promise<AccountRow | null> {
    const [row] = await this.db.query(`SELECT id,username,display_name,password_hash,dataset_user_id FROM accounts WHERE ${where}=?`, [value]);
    if (!row) return null;
    const interests = await this.db.query('SELECT theme FROM account_interests WHERE account_id=? ORDER BY theme', [row.id]);
    return { id: Number(row.id), username: row.username, displayName: row.display_name, passwordHash: row.password_hash,
      datasetUserId: row.dataset_user_id === null ? null : Number(row.dataset_user_id), interests: interests.map(item => String(item.theme)) };
  }
  accountByUsername(username: string) { return this.account('username', username); }
  accountById(id: number) { return this.account('id', id); }

  /** Returns null when the username is taken. */
  async createAccount(input: { username: string; displayName: string; passwordHash: string; interests: string[] }): Promise<AccountRow | null> {
    try {
      await this.db.execute('INSERT INTO accounts(username,display_name,password_hash) VALUES (?,?,?)', [input.username, input.displayName, input.passwordHash]);
    } catch (error) {
      if ((error as { code?: string }).code === 'ER_DUP_ENTRY') return null;
      throw error;
    }
    const created = (await this.accountByUsername(input.username))!;
    for (const theme of input.interests) await this.db.execute('INSERT IGNORE INTO account_interests(account_id,theme) VALUES (?,?)', [created.id, theme]);
    return { ...created, interests: [...input.interests].sort() };
  }

  async demoAccounts() {
    const rows = await this.db.query('SELECT username,display_name FROM accounts WHERE dataset_user_id IS NOT NULL ORDER BY id');
    return rows.map(row => ({ username: String(row.username), displayName: String(row.display_name) }));
  }

  async settings(accountId: number): Promise<Partial<ModelSettings> | null> {
    const [row] = await this.db.query('SELECT settings FROM account_settings WHERE account_id=?', [accountId]);
    if (!row) return null;
    return typeof row.settings === 'string' ? JSON.parse(row.settings) : row.settings;
  }
  async saveSettings(accountId: number, settings: ModelSettings) {
    await this.db.execute('INSERT INTO account_settings(account_id,settings) VALUES (?,?) ON DUPLICATE KEY UPDATE settings=VALUES(settings)', [accountId, JSON.stringify(settings)]);
  }
  async deleteSettings(accountId: number) { await this.db.execute('DELETE FROM account_settings WHERE account_id=?', [accountId]); }

  async feedback(accountId: number): Promise<{ poiId: number; action: FeedbackAction }[]> {
    const rows = await this.db.query('SELECT poi_id,action FROM account_feedback WHERE account_id=? ORDER BY created_at DESC, poi_id', [accountId]);
    return rows.map(row => ({ poiId: Number(row.poi_id), action: row.action as FeedbackAction }));
  }
  async addFeedback(accountId: number, poiId: number, action: FeedbackAction) {
    await this.db.execute('INSERT IGNORE INTO account_feedback(account_id,poi_id,action) VALUES (?,?,?)', [accountId, poiId, action]);
  }
  async removeFeedback(accountId: number, poiId: number, action: FeedbackAction) {
    await this.db.execute('DELETE FROM account_feedback WHERE account_id=? AND poi_id=? AND action=?', [accountId, poiId, action]);
  }
}
