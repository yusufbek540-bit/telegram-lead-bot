/**
 * Vercel serverless function — Telegram Bot API proxy for CRM notifications.
 *
 * The bot token lives in Vercel environment variables (server-side only).
 * The CRM browser calls POST /api/notify instead of Telegram directly.
 *
 * Set in Vercel dashboard: Settings → Environment Variables → BOT_TOKEN
 */
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const token = process.env.BOT_TOKEN;
  if (!token) {
    return res.status(500).json({ error: 'BOT_TOKEN not configured on server' });
  }

  const { chat_id, text } = req.body;
  if (!chat_id || !text) {
    return res.status(400).json({ error: 'chat_id and text are required' });
  }

  try {
    const response = await fetch(
      `https://api.telegram.org/bot${token}/sendMessage`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id, text, parse_mode: 'HTML' }),
      }
    );
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
