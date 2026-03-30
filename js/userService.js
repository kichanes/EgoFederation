const { pool } = require('./db');

function expNeeded(level) {
  return level * 100;
}

async function upsertUser({ telegramId, fullName, username }) {
  await pool.query(
    `
    INSERT INTO users (telegram_id, full_name, username, cash, level, exp, last_exp_time)
    VALUES ($1, $2, $3, 1000, 1, 0, 0)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
      full_name = EXCLUDED.full_name,
      username = EXCLUDED.username
    `,
    [telegramId, fullName, username]
  );
}

async function getUserById(telegramId) {
  const { rows } = await pool.query('SELECT * FROM users WHERE telegram_id = $1', [telegramId]);
  return rows[0] || null;
}

async function getUserByUsername(username) {
  const normalized = username.replace(/^@/, '').trim();
  const { rows } = await pool.query(
    'SELECT * FROM users WHERE LOWER(username) = LOWER($1) LIMIT 1',
    [normalized]
  );
  return rows[0] || null;
}

async function updateCash(telegramId, delta) {
  const user = await getUserById(telegramId);
  if (!user) return false;

  const newCash = Number(user.cash) + Number(delta);
  if (newCash < 0) return false;

  await pool.query('UPDATE users SET cash = $1 WHERE telegram_id = $2', [newCash, telegramId]);
  return true;
}

async function setCustomRole(telegramId, customRole) {
  const res = await pool.query('UPDATE users SET custom_role = $1 WHERE telegram_id = $2', [customRole, telegramId]);
  return res.rowCount > 0;
}

async function clearCustomRole(telegramId) {
  const res = await pool.query('UPDATE users SET custom_role = NULL WHERE telegram_id = $1', [telegramId]);
  return res.rowCount > 0;
}

async function setCustomLevel(telegramId, customLevel) {
  const res = await pool.query('UPDATE users SET custom_level = $1 WHERE telegram_id = $2', [customLevel, telegramId]);
  return res.rowCount > 0;
}

async function clearCustomLevel(telegramId) {
  const res = await pool.query('UPDATE users SET custom_level = NULL WHERE telegram_id = $1', [telegramId]);
  return res.rowCount > 0;
}

async function grantExpIfReady(telegramId, nowUnix, expMin = 5, expMax = 15, cooldown = 300) {
  const user = await getUserById(telegramId);
  if (!user) return null;

  if (nowUnix - Number(user.last_exp_time) < cooldown) {
    return null;
  }

  const gainedExp = Math.floor(Math.random() * (expMax - expMin + 1)) + expMin;
  let level = Number(user.level);
  let exp = Number(user.exp) + gainedExp;

  while (exp >= expNeeded(level)) {
    exp -= expNeeded(level);
    level += 1;
  }

  await pool.query(
    'UPDATE users SET exp = $1, level = $2, custom_level = NULL, last_exp_time = $3 WHERE telegram_id = $4',
    [exp, level, nowUnix, telegramId]
  );

  return { gainedExp, level, exp };
}

module.exports = {
  expNeeded,
  upsertUser,
  getUserById,
  getUserByUsername,
  updateCash,
  setCustomRole,
  clearCustomRole,
  setCustomLevel,
  clearCustomLevel,
  grantExpIfReady,
};
