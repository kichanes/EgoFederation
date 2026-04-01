const { pool } = require('./db');

function expNeeded(level) {
  return level * 100;
}

async function safeQuery(queryText, params = []) {
  try {
    return await pool.query(queryText, params);
  } catch (err) {
    console.error(err);
    return null;
  }
}

async function upsertUser({ telegramId, fullName, username }) {
  const result = await safeQuery(
    `
    INSERT INTO users (
      telegram_id,
      full_name,
      username,
      cash,
      bank,
      level,
      exp,
      last_exp_time,
      last_daily,
      last_work
    )
    VALUES ($1, $2, $3, 1000, 0, 1, 0, 0, 0, 0)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
      full_name = EXCLUDED.full_name,
      username = EXCLUDED.username
    `,
    [telegramId, fullName, username]
  );

  return Boolean(result);
}

async function getUserById(telegramId) {
  const result = await safeQuery('SELECT * FROM users WHERE telegram_id = $1', [telegramId]);
  if (!result) return null;
  return result.rows[0] || null;
}

async function getUserByUsername(username) {
  const normalized = username.replace(/^@/, '').trim();
  const result = await safeQuery(
    'SELECT * FROM users WHERE LOWER(username) = LOWER($1) LIMIT 1',
    [normalized]
  );

  if (!result) return null;
  return result.rows[0] || null;
}

async function updateCash(telegramId, delta) {
  const result = await safeQuery(
    'UPDATE users SET cash = cash + $1 WHERE telegram_id = $2 AND cash + $1 >= 0 RETURNING cash',
    [Number(delta), telegramId]
  );

  if (!result || result.rowCount === 0) {
    return null;
  }

  return Number(result.rows[0].cash);
}

async function setCustomRole(telegramId, customRole) {
  const result = await safeQuery('UPDATE users SET custom_role = $1 WHERE telegram_id = $2', [customRole, telegramId]);
  if (!result) return false;
  return result.rowCount > 0;
}

async function clearCustomRole(telegramId) {
  const result = await safeQuery('UPDATE users SET custom_role = NULL WHERE telegram_id = $1', [telegramId]);
  if (!result) return false;
  return result.rowCount > 0;
}

async function setCustomLevel(telegramId, customLevel) {
  const result = await safeQuery('UPDATE users SET custom_level = $1 WHERE telegram_id = $2', [customLevel, telegramId]);
  if (!result) return false;
  return result.rowCount > 0;
}

async function clearCustomLevel(telegramId) {
  const result = await safeQuery('UPDATE users SET custom_level = NULL WHERE telegram_id = $1', [telegramId]);
  if (!result) return false;
  return result.rowCount > 0;
}

async function setCooldown(telegramId, field, nowUnix) {
  const allowedFields = new Set(['last_daily', 'last_work', 'last_exp_time']);
  if (!allowedFields.has(field)) {
    throw new Error(`Unsupported cooldown field: ${field}`);
  }

  const result = await safeQuery(`UPDATE users SET ${field} = $1 WHERE telegram_id = $2`, [nowUnix, telegramId]);
  if (!result) return false;
  return result.rowCount > 0;
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

  const result = await safeQuery(
    'UPDATE users SET exp = $1, level = $2, custom_level = NULL, last_exp_time = $3 WHERE telegram_id = $4',
    [exp, level, nowUnix, telegramId]
  );

  if (!result) return null;
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
  setCooldown,
  grantExpIfReady,
};
