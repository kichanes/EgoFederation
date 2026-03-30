const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: Number(process.env.PGPORT || 5432),
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || '',
  database: process.env.PGDATABASE || 'egofederation_bot',
  ssl: process.env.PGSSL === 'true' ? { rejectUnauthorized: false } : false,
});

async function initDatabase() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      telegram_id BIGINT PRIMARY KEY,
      full_name TEXT NOT NULL,
      username TEXT NOT NULL,
      cash BIGINT NOT NULL DEFAULT 1000,
      level INTEGER NOT NULL DEFAULT 1,
      exp INTEGER NOT NULL DEFAULT 0,
      last_exp_time BIGINT NOT NULL DEFAULT 0,
      custom_role TEXT,
      custom_level INTEGER
    )
  `);
}

module.exports = {
  pool,
  initDatabase,
};
