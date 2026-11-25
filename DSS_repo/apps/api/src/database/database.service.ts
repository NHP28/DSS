import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { createPool, Pool, RowDataPacket } from 'mysql2/promise';

export function databaseOptions() {
  return {host: process.env.DB_HOST || '127.0.0.1', port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || 'dss', password: process.env.DB_PASSWORD ?? 'dss_local_password',
    database: process.env.DB_NAME || 'danang_dss', connectionLimit: 10,
    charset: 'utf8mb4', decimalNumbers: true, connectTimeout: 5000};
}

@Injectable()
export class DatabaseService implements OnModuleDestroy {
  readonly pool: Pool = createPool(databaseOptions());
  async query<T extends RowDataPacket = RowDataPacket>(sql: string, args: (string | number | boolean | null)[] = []): Promise<T[]> {
    const [rows] = await this.pool.execute<T[]>(sql, args);
    return rows;
  }
  async execute(sql: string, args: (string | number | boolean | null)[] = []) { await this.pool.execute(sql, args); }
  async onModuleDestroy() { await this.pool.end(); }
}
