CREATE TABLE IF NOT EXISTS users (
  telegram_id BIGINT PRIMARY KEY,
  full_name TEXT NOT NULL,
  username TEXT,
  cash BIGINT DEFAULT 1000 CHECK (cash >= 0),
  bank BIGINT DEFAULT 0,
  level INT DEFAULT 1 CHECK (level >= 1),
  exp INT DEFAULT 0 CHECK (exp >= 0),
  last_exp_time BIGINT DEFAULT 0,
  last_daily BIGINT DEFAULT 0,
  last_work BIGINT DEFAULT 0,
  role TEXT DEFAULT 'User',
  custom_role TEXT,
  custom_level INT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  type TEXT,
  description TEXT,
  price BIGINT DEFAULT 0,
  max_stack INT DEFAULT 99
);

CREATE TABLE IF NOT EXISTS user_items (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
  item_id INT REFERENCES items(id) ON DELETE CASCADE,
  quantity INT DEFAULT 0 CHECK (quantity >= 0),
  UNIQUE (telegram_id, item_id)
);

CREATE TABLE IF NOT EXISTS shop (
  id SERIAL PRIMARY KEY,
  item_id INT REFERENCES items(id),
  price BIGINT,
  is_active BOOLEAN DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
  ON users (LOWER(username));

CREATE INDEX IF NOT EXISTS idx_user_items_user ON user_items (telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_level ON users (level DESC);
CREATE INDEX IF NOT EXISTS idx_users_cash ON users (cash DESC);
CREATE INDEX IF NOT EXISTS idx_user_items_telegram_id ON user_items (telegram_id);
CREATE INDEX IF NOT EXISTS idx_user_items_item_id ON user_items (item_id);
CREATE INDEX IF NOT EXISTS idx_shop_active ON shop (is_active);
