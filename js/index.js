const db = require("./db");

// ambil user
async function getUser(userId) {
  const res = await db.query(
    "SELECT * FROM users WHERE id = $1",
    [userId]
  );
  return res.rows[0];
}

// simpan/update user
async function saveUser(userId, user) {
  await db.query(
    `INSERT INTO users (id, level, exp, data)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (id)
     DO UPDATE SET
       level = $2,
       exp = $3,
       data = $4`,
    [userId, user.level, user.exp, user.data]
  );
}

// auto create user
async function getOrCreateUser(userId) {
  let user = await getUser(userId);

  if (!user) {
    user = {
      level: 1,
      exp: 0,
      data: {},
    };

    await saveUser(userId, user);
  }

  return user;
}
