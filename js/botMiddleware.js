const { upsertUser } = require('./userService');

async function ensureUserOnMessage(ctx, next) {
  if (ctx?.from?.id) {
    await upsertUser({
      telegramId: ctx.from.id,
      fullName: ctx.from.first_name || '',
      username: ctx.from.username || null,
    });
  }

  if (typeof next === 'function') {
    return next();
  }

  return undefined;
}

module.exports = {
  ensureUserOnMessage,
};
