# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
python3 -m bot.main
```

Kill existing instances before restarting (only one polling instance allowed):
```bash
pkill -f "bot.main"; python3 -m bot.main
```

Install dependencies:
```bash
pip3 install -r requirements.txt
```

Deploy TWA to Vercel (from `twa/` directory):
```bash
npx vercel --prod --yes
```

## Architecture

This is a Telegram lead capture bot for a marketing agency. It has two parts:

**Bot** (`bot/`) — aiogram 3.x polling bot backed by Supabase:
- `main.py` — registers routers in priority order: start → admin → contact → twa → menu → ai_chat (last, catches all remaining text)
- `config.py` — all env vars as a `Config` class singleton (`config`)
- `texts.py` — all user-facing strings as `TEXTS` dict with `uz`/`ru` keys; use `t("key", lang, **kwargs)` everywhere
- `keyboards/main_menu.py` — all keyboard layouts; menu buttons use `edit_text` via `safe_edit()` in menu.py to update in place without clutter
- `services/db_service.py` — sync Supabase client wrapped in async methods; singleton `db`
- `services/ai_service.py` — OpenAI `AsyncOpenAI`, `gpt-4o-mini` by default; receives `user_info` string built from lead data so AI knows the user's name/phone
- `prompts/system_prompt.txt` — system prompt template with `{agency_name}`, `{lang}`, `{user_info}` placeholders

**TWA** (`twa/`) — single `index.html` static site deployed to Vercel. Has its own git repo inside `twa/` with remote `github.com/yusufbek540-bit/telegram-lead-twa`. Already linked to Vercel project `twa` (org `yusufs-projects-dc1d63ce`), live at `https://twa-jet.vercel.app`.

**CRM** (`crm/`) — standalone React dashboard deployed to Vercel at `https://crm-mqsd.vercel.app`. Deploy from `crm/` directory: `cd crm && npx vercel --prod --yes`. The `/crm` bot command (admin only) opens it via `WebAppInfo` in `bot/handlers/admin.py`.

## Key Patterns

**Router priority** — handlers registered in `main.py` in order; `ai_chat` router must always be last since it matches all `F.text`.

**Menu UX** — all inline button callbacks call `safe_edit()` (wraps `edit_text` with silent `TelegramBadRequest` suppression for "not modified") to keep the chat to a single updating message. Only the contact phone-share flow sends a new message (ReplyKeyboard can't be set via edit).

**AI context** — `ai_chat.py` builds a `user_info` string from the lead's DB record (name, phone, username, lang) and passes it to `ai_service.get_response()`, which injects it into the system prompt. This way the AI knows if the user already shared their phone.

**Conversation history** — stored in Supabase `conversations` table, last 20 messages fed to OpenAI per request. `/reset` has been removed — all history is permanent for tracking.

**Language** — `uz` (Uzbek Latin) and `ru` (Russian). Stored per-lead in `preferred_lang`. Auto-detected from Telegram `language_code` on `/start`.

**Lead scoring** — `db.recalculate_score()` triggered after phone share and periodically during AI chat.

**Deep link tracking** — `/start <source>` captures ad campaign source (e.g., `?start=meta_general`) into `leads.source`. Source is only written on first visit or when a real deep link is present — never overwrite an existing source with `"organic"` on re-start.

**ReplyKeyboard dismissal** — sending a message with `InlineKeyboardMarkup` does NOT dismiss an active `ReplyKeyboard`. Always send a message with `ReplyKeyboardRemove()` first, then send the inline keyboard as a second message.

**CRM dashboard Supabase selects** — always include every field used in UI logic in the `.select()` call. A missing field (e.g. `source`) causes silent fallback to defaults in charts.

**Duplicate bot instances** — double messages = two instances running. Check with `ps aux | grep bot.main`. Always restart with `pkill -f "bot.main"; python3 -m bot.main`.

## Scheduler

Background jobs live in `bot/services/scheduler_service.py`. The module-level `scheduler` singleton is created by `create_scheduler(bot)` and started in `main.py` before polling begins.

**How to add a new job:**
1. Write an `async def my_job(bot: Bot)` function in `scheduler_service.py`
2. Wrap the body in `try/except` — log ERROR on failure, never re-raise
3. Register inside `create_scheduler()` before the `return` statement:
   ```python
   scheduler.add_job(my_job, trigger="interval", hours=N, args=[bot], id="my_job", replace_existing=True)
   ```
4. Add the interval value to `JOB_INTERVALS` in `bot/config.py`

**Debugging:**
- `/jobs` (admin bot command) — lists all registered jobs with time until next run
- Logs — every job logs on start/end with elapsed time; `heartbeat` logs every 30 min as proof of life

**Rules:**
- All jobs use the `db` singleton from `services/db_service.py` — never instantiate a new Supabase client per job
- Jobs that send messages receive `bot: Bot` as an argument (passed via `args=[bot]`)
- Timezone is `Asia/Tashkent` — cron-style daily jobs fire at local time, not UTC
- A failing job must not crash the scheduler — always catch exceptions

## Environment Variables

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `OPENAI_API_KEY` | OpenAI API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |
| `TWA_URL` | Deployed TWA URL (must be `https://`, not `hhttps://`) |
| `ADMIN_IDS` | Comma-separated Telegram IDs with admin access |
| `AGENCY_NAME` | Used in welcome text and AI system prompt |

## Database (Supabase)

Three tables: `leads` (one row per user), `conversations` (AI chat history), `events` (behavioral tracking). Schema in `database/schema.sql` — run in Supabase SQL Editor to initialize.

## Admin Commands (bot)

`/leads`, `/lead <id>`, `/stats`, `/export` — restricted to `ADMIN_IDS`. All use Russian for admin-facing text.

## Customization Points

Replace all `[PRICE]`, `[X]`, and `[...]` placeholders in:
- `bot/texts.py` — menu content (services, FAQ, about)
- `bot/prompts/system_prompt.txt` — AI knowledge base
- `twa/index.html` — TWA portfolio page content and CSS variables in `:root`
