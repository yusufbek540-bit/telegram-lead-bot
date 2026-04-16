# Phase 0 — Scheduler Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing scheduler with timezone support, config-driven intervals, a heartbeat job, and a `/jobs` admin command — so all future scheduled features have a solid, observable foundation.

**Architecture:** `APScheduler 3.10.4` and `AsyncIOScheduler` already exist in `scheduler_service.py`. We expose a module-level `scheduler` singleton so `admin.py` can inspect jobs. All intervals and timezone move to `config.py`. The heartbeat job provides a cheap production health check.

**Tech Stack:** Python 3.x, aiogram 3.x, APScheduler 3.10.4, Supabase (unchanged)

**Note:** No pytest infrastructure exists in this project. Verification steps use bot commands and log inspection instead of automated tests.

---

## File Map

| File | Change |
|---|---|
| `bot/config.py` | Add `SCHEDULER_TIMEZONE` and `JOB_INTERVALS` |
| `bot/services/scheduler_service.py` | Expose `scheduler` singleton, add timezone, use config intervals, add heartbeat, wrap jobs in try/except with logging |
| `bot/handlers/admin.py` | Add `/jobs` command |
| `CLAUDE.md` | Document scheduler patterns |

---

### Task 1: Add scheduler config to `bot/config.py`

**Files:**
- Modify: `bot/config.py`

- [ ] **Step 1: Add timezone and job intervals to the Config class**

Open `bot/config.py`. Add these lines inside the `Config` class, after `HISTORY_LIMIT`:

```python
    # Scheduler
    SCHEDULER_TIMEZONE: str = "Asia/Tashkent"
    JOB_INTERVALS: dict = {
        "followup_check_hours": 1,
        "stale_detection_hour": 9,        # daily at 9 AM Tashkent time
        "ai_batch_hours": 8,              # sentiment + tagging (budget-conscious)
        "proposal_expiry_hours": 6,
        "campaign_dispatch_minutes": 5,
        "heartbeat_minutes": 30,
    }
    STALE_THRESHOLDS: dict = {
        "new": 1,          # days before "new" lead is stale
        "contacted": 3,
        "qualified": 7,
        "proposal_sent": 5,
    }
```

Full updated `bot/config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 600

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # TWA
    TWA_URL: str = os.getenv("TWA_URL", "https://your-twa.vercel.app")

    # Admin
    ADMIN_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "0").split(",")
        if x.strip().isdigit()
    ]

    # Defaults
    DEFAULT_LANG: str = os.getenv("DEFAULT_LANG", "uz")
    AGENCY_NAME: str = os.getenv("AGENCY_NAME", "YourBrand Agency")

    # Conversation history limit for AI context
    HISTORY_LIMIT: int = 20

    # Scheduler
    SCHEDULER_TIMEZONE: str = "Asia/Tashkent"
    JOB_INTERVALS: dict = {
        "followup_check_hours": 1,
        "stale_detection_hour": 9,        # daily at 9 AM Tashkent time
        "ai_batch_hours": 8,              # sentiment + tagging (budget-conscious)
        "proposal_expiry_hours": 6,
        "campaign_dispatch_minutes": 5,
        "heartbeat_minutes": 30,
    }
    STALE_THRESHOLDS: dict = {
        "new": 1,
        "contacted": 3,
        "qualified": 7,
        "proposal_sent": 5,
    }


config = Config()
```

- [ ] **Step 2: Verify the bot still starts cleanly**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

Expected log output (last lines):
```
INFO | __main__ | Bot starting...
INFO | aiogram.dispatcher | Run polling for bot @mqsd_agency_bot
```

No `ImportError` or `AttributeError`. If you see one, check indentation inside the `Config` class.

- [ ] **Step 3: Commit**

```bash
git add bot/config.py
git commit -m "feat: add scheduler timezone and job interval config"
```

---

### Task 2: Refactor `bot/services/scheduler_service.py`

**Files:**
- Modify: `bot/services/scheduler_service.py`

**What changes:**
- Expose `scheduler` as a module-level variable (so `/jobs` can inspect it)
- Pass `timezone=config.SCHEDULER_TIMEZONE` to `AsyncIOScheduler`
- Use `config.JOB_INTERVALS["followup_check_hours"]` instead of hardcoded `hours=1`
- Add `heartbeat` job
- Wrap `run_followups` body in try/except with structured logging

- [ ] **Step 1: Replace `scheduler_service.py` with the updated version**

Full replacement of `bot/services/scheduler_service.py`:

```python
"""
Scheduler service — background jobs for the bot.

Jobs registered here:
- run_followups   : every 1h — follow-up messages to silent/gone leads
- heartbeat       : every 30m — confirms scheduler is alive (check logs)

All jobs are wrapped in try/except. A failing job logs ERROR and continues;
it never crashes the scheduler or the bot.

To add a new job:
    scheduler.add_job(my_async_fn, trigger="interval", hours=N, id="my_job")
    Call this inside create_scheduler() before returning.

To inspect running jobs:
    Send /jobs in Telegram as an admin.
"""

import logging
import time
from datetime import datetime, timezone as tz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

# Module-level singleton — imported by admin.py for /jobs command
scheduler: AsyncIOScheduler | None = None


# ── MESSAGE TEMPLATES ──────────────────────────────────────

MESSAGES = {
    "silent_start": {
        "uz": (
            "🤔 Ko'pchilik botimizga kirib, biror narsa so'ramoqchi bo'ladi — "
            "lekin qayerdan boshlashni bilmay qoladi.\n\n"
            "Siz ham shundaymisiz?\n\n"
            "Ayting: <b>biznesingiz haqida bir gap</b> — qaysi sohada ishlaysiz, "
            "hozir qanday muammo bor. Qolganini biz hal qilamiz 🎯"
        ),
        "ru": (
            "🤔 Большинство людей заходят к нам с конкретной задачей — "
            "но не знают, с чего начать разговор.\n\n"
            "Может, вы тоже?\n\n"
            "Просто скажите: <b>чем занимается ваш бизнес</b> и какая сейчас "
            "главная проблема. Остальное — наша работа 🎯"
        ),
    },
    "engaged_gone": {
        "uz": (
            "💬 Siz bilan yaxshi suhbat boshlagan edik — keyin to'xtab qoldi.\n\n"
            "Ko'pincha bu shuni anglatadi: javob qoniqtirmadi yoki "
            "aniqroq narsa kerak edi.\n\n"
            "Nima to'xtatdi? Keling 15 daqiqalik bepul qo'ng'iroqda gaplashamiz 👇"
        ),
        "ru": (
            "💬 Мы хорошо начали разговор — и он оборвался на середине.\n\n"
            "Обычно это значит одно из двух: ответ не устроил "
            "или нужна была более конкретная информация.\n\n"
            "Что остановило? Давайте обсудим на 15 минутном бесплатном звонке 👇"
        ),
    },
    "no_phone": {
        "uz": (
            "⚡️ Siz bizning xizmatlarimizni o'rgandingiz, savollar berdingiz — "
            "bu shunchaki qiziqish emas, bu jiddiy niyat.\n\n"
            "Ko'p odamlar shu bosqichda oz imkoniyatini boy beradi.\n\n"
            "Biz siz uchun <b>bepul, 15 daqiqalik qo'ng'iroq</b> o'tkazmoqchimiz — "
            "loyihangizga mos aniq narx va reja aytamiz.\n\n"
            "Raqamingizni ulashing 👇"
        ),
        "ru": (
            "⚡️ Вы изучили наши услуги, задали вопросы — "
            "это не просто любопытство, это серьёзный интерес.\n\n"
            "Большинство людей упускают возможность именно здесь.\n\n"
            "Мы хотим провести для вас <b>бесплатный 15-минутный звонок</b> — "
            "расскажем конкретную цену и план под ваш проект.\n\n"
            "Поделитесь номером 👇"
        ),
    },
}


# ── SEND HELPERS ───────────────────────────────────────────

async def send_to(bot: Bot, lead: dict, message_key: str):
    """Send a follow-up message and record the event."""
    tid = lead["telegram_id"]
    lang = lead.get("preferred_lang", config.DEFAULT_LANG)
    text = MESSAGES[message_key].get(lang) or MESSAGES[message_key]["uz"]
    event_type = f"followup_{message_key}"
    try:
        await bot.send_message(tid, text)
        await db.track_event(tid, event_type, {"auto": True})
    except Exception:
        pass  # User blocked the bot or other Telegram error


# ── JOBS ───────────────────────────────────────────────────

async def run_followups(bot: Bot):
    """Every hour: send follow-up messages to leads that qualify."""
    start = time.monotonic()
    logger.info("run_followups: starting")
    try:
        for lead in await db.get_silent_starters():
            await send_to(bot, lead, "silent_start")
        for lead in await db.get_engaged_gone():
            await send_to(bot, lead, "engaged_gone")
        for lead in await db.get_no_phone_after_conversation():
            await send_to(bot, lead, "no_phone")
        elapsed = time.monotonic() - start
        logger.info(f"run_followups: done in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"run_followups: failed — {e}", exc_info=True)


async def heartbeat():
    """Every 30 min: log a heartbeat to confirm the scheduler is alive."""
    logger.info("scheduler heartbeat")


# ── SCHEDULER SETUP ────────────────────────────────────────

def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    global scheduler
    scheduler = AsyncIOScheduler(timezone=config.SCHEDULER_TIMEZONE)

    scheduler.add_job(
        run_followups,
        trigger="interval",
        hours=config.JOB_INTERVALS["followup_check_hours"],
        args=[bot],
        id="run_followups",
        replace_existing=True,
    )

    scheduler.add_job(
        heartbeat,
        trigger="interval",
        minutes=config.JOB_INTERVALS["heartbeat_minutes"],
        id="heartbeat",
        replace_existing=True,
    )

    return scheduler
```

- [ ] **Step 2: Restart the bot and confirm no errors**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

Expected output includes:
```
INFO | apscheduler.scheduler | Added job "run_followups" to job store "default"
INFO | apscheduler.scheduler | Added job "heartbeat" to job store "default"
INFO | apscheduler.scheduler | Scheduler started
INFO | __main__ | Bot starting...
```

If you see `pytz not installed` or timezone error, run: `pip3 install pytz`

- [ ] **Step 3: Commit**

```bash
git add bot/services/scheduler_service.py
git commit -m "feat: expose scheduler singleton, add timezone and heartbeat job"
```

---

### Task 3: Add `/jobs` command to `bot/handlers/admin.py`

**Files:**
- Modify: `bot/handlers/admin.py`

- [ ] **Step 1: Add the `/jobs` handler**

Add this import at the top of `bot/handlers/admin.py`, after the existing imports:

```python
from datetime import datetime, timezone as tz
```

Then add this handler at the end of the file (before the final newline):

```python

@router.message(Command("jobs"))
async def cmd_jobs(message: Message):
    """Show all scheduled jobs and their next run time."""
    if not is_admin(message.from_user.id):
        return

    from bot.services.scheduler_service import scheduler
    if scheduler is None:
        await message.answer("⚙️ Планировщик не запущен.")
        return

    jobs = scheduler.get_jobs()
    if not jobs:
        await message.answer("⚙️ Нет запланированных задач.")
        return

    now = datetime.now(tz.utc)
    lines = ["⏰ <b>Запланированные задачи:</b>\n"]
    for job in jobs:
        if job.next_run_time:
            delta = job.next_run_time.astimezone(tz.utc) - now
            total_secs = max(0, int(delta.total_seconds()))
            mins, secs = divmod(total_secs, 60)
            hours, mins = divmod(mins, 60)
            if hours:
                time_str = f"{hours}ч {mins}м {secs}с"
            else:
                time_str = f"{mins}м {secs}с"
            lines.append(f"• <code>{job.id}</code> — через {time_str}")
        else:
            lines.append(f"• <code>{job.id}</code> — не запланирован")

    await message.answer("\n".join(lines), parse_mode="HTML")
```

- [ ] **Step 2: Register `/jobs` in the admin commands list in `bot/main.py`**

Open `bot/main.py`. Find the `admin_commands` list and add `/jobs`:

```python
    admin_commands = [
        BotCommand(command="start", description="Boshlash / Начать"),
        BotCommand(command="crm", description="CRM Dashboard"),
        BotCommand(command="leads", description="Последние лиды"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="export", description="Экспорт CSV"),
        BotCommand(command="broadcast", description="Рассылка"),
        BotCommand(command="jobs", description="Статус планировщика"),
    ]
```

- [ ] **Step 3: Restart the bot**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

- [ ] **Step 4: Verify `/jobs` works**

Send `/jobs` to the bot from an admin account.

Expected response:
```
⏰ Запланированные задачи:

• run_followups — через 58м 43с
• heartbeat — через 29м 17с
```

If you get "Планировщик не запущен", check that `scheduler_service.py` sets `global scheduler` inside `create_scheduler()` and that `create_scheduler()` is called in `main.py` before polling starts.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/admin.py bot/main.py
git commit -m "feat: add /jobs admin command to inspect scheduler"
```

---

### Task 4: Update `CLAUDE.md` with scheduler documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add scheduler section to CLAUDE.md**

Add this section after the existing "Key Patterns" section in `CLAUDE.md`:

```markdown
## Scheduler

Background jobs live in `bot/services/scheduler_service.py`. The singleton `scheduler` is created by `create_scheduler(bot)` and started in `main.py` before polling.

**How to add a new job:**
1. Write an `async def my_job(bot: Bot)` function in `scheduler_service.py`
2. Wrap the body in `try/except` — log ERROR on failure, never re-raise
3. Register inside `create_scheduler()`:
   ```python
   scheduler.add_job(my_job, trigger="interval", hours=N, args=[bot], id="my_job", replace_existing=True)
   ```
4. Add interval to `config.JOB_INTERVALS` in `config.py`

**Debugging:**
- `/jobs` (admin bot command) — shows all jobs and seconds until next run
- Logs: every job logs on start/end with elapsed time; heartbeat logs every 30 min as proof of life

**Rules:**
- All jobs use `db` singleton from `services/db_service.py` — never instantiate a new Supabase client per job
- Jobs that send messages receive `bot: Bot` as an argument (passed via `args=[bot]`)
- Timezone is `Asia/Tashkent` — cron-style daily jobs fire at local time, not UTC
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document scheduler patterns in CLAUDE.md"
```

---

### Task 5: Verification — confirm heartbeat fires in production

- [ ] **Step 1: Restart bot and watch logs**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

- [ ] **Step 2: Send `/jobs` immediately after start**

Confirm both `run_followups` and `heartbeat` appear with countdown timers.

- [ ] **Step 3: Wait for heartbeat**

The heartbeat fires every 30 minutes. After 30 minutes, check logs for:

```
INFO | bot.services.scheduler_service | scheduler heartbeat
```

If you need to verify faster without waiting 30 min, temporarily change `heartbeat_minutes` in `config.py` to `1`, restart, wait 60 seconds, check logs, then change back to `30`.

- [ ] **Step 4: Phase 0 complete**

Phase 0 is done when:
- `/jobs` returns both jobs with countdown times
- `scheduler heartbeat` appears in logs at the expected interval
- Bot is running normally (no crashes, `/start` works)

Once verified, proceed to Phase 1 (write a new plan for it).
