import { defineConfig } from 'drizzle-kit';
import * as dotenv from 'dotenv';

dotenv.config({ path: '.env' });

const DB_CONFIG = {
  user: process.env.DB_USER || process.env.MYSQL_USER || 'root',
  password: process.env.DB_PASSWORD || process.env.MYSQL_PASSWORD || '',
  host: process.env.DB_HOST || process.env.MYSQL_HOST || '127.0.0.1',
  port: Number(process.env.DB_PORT || process.env.MYSQL_PORT || 3306),
  database: process.env.DB_NAME || process.env.MYSQL_DB || 'danang_dss_db',
};

const databaseUrl =
  process.env.DATABASE_URL ||
  `mysql://${DB_CONFIG.user}:${DB_CONFIG.password}@${DB_CONFIG.host}:${DB_CONFIG.port}/${DB_CONFIG.database}`;

export default defineConfig({
  schema: './src/drizzle/schema.ts',
  out: './drizzle',
  dialect: 'mysql',
  dbCredentials: {
    url: databaseUrl,
  },
});
