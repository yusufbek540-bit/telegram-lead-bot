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
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from bot.config import config
from bot.services.db_service import db
from bot.services.followups import check_followup_reminders
from bot.services.stale_detector import detect_stale_leads
from bot.services.proposal_expiry import check_proposal_expiry

logger = logging.getLogger(__name__)

# Module-level singleton — imported by admin.py for /jobs command
scheduler: Optional[AsyncIOScheduler] = None


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

    scheduler.add_job(
        check_followup_reminders,
        trigger="interval",
        hours=config.JOB_INTERVALS["followup_check_hours"],
        args=[bot],
        id="check_followup_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        detect_stale_leads,
        trigger="cron",
        hour=config.JOB_INTERVALS["stale_detection_hour"],
        minute=0,
        args=[bot],
        id="detect_stale_leads",
        replace_existing=True,
    )

    scheduler.add_job(
        check_proposal_expiry,
        trigger="interval",
        hours=config.JOB_INTERVALS["proposal_expiry_hours"],
        args=[bot],
        id="check_proposal_expiry",
        replace_existing=True,
    )

    return scheduler
