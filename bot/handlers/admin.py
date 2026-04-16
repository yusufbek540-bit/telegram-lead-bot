"""
Admin handler — commands for your team to manage leads.
Only accessible by Telegram IDs listed in ADMIN_IDS.
"""

import csv
import io
from datetime import datetime, timezone as tz
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.texts import t
from bot.services.db_service import db

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.message(Command("leads"))
async def cmd_leads(message: Message):
    """Show recent leads."""
    if not is_admin(message.from_user.id):
        await message.answer(t("admin_no_access", "ru"))
        return

    leads = await db.get_recent_leads(limit=15)

    if not leads:
        await message.answer("📭 Лидов пока нет.")
        return

    text = "📊 <b>Последние лиды:</b>\n\n"
    for lead in leads:
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        phone = lead.get("phone") or "—"
        source = lead.get("source", "organic")
        score = lead.get("lead_score", 0)
        status = lead.get("status", "new")
        date = lead.get("created_at", "")[:10]

        text += (
            f"👤 <b>{name}</b> @{lead.get('username', '—')}\n"
            f"   📱 {phone} | 📊 {source}\n"
            f"   🏷 {status} | ⭐ {score} pts | 📅 {date}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show lead statistics."""
    if not is_admin(message.from_user.id):
        await message.answer(t("admin_no_access", "ru"))
        return

    # Get all leads for stats
    all_leads = await db.get_recent_leads(limit=1000)

    total = len(all_leads)
    with_phone = sum(1 for l in all_leads if l.get("phone"))
    from_ads = sum(1 for l in all_leads if l.get("source", "") != "organic")

    # Status breakdown
    statuses = {}
    for lead in all_leads:
        s = lead.get("status", "new")
        statuses[s] = statuses.get(s, 0) + 1

    # Source breakdown
    sources = {}
    for lead in all_leads:
        src = lead.get("source", "organic")
        sources[src] = sources.get(src, 0) + 1

    text = (
        "📊 <b>Статистика:</b>\n\n"
        f"👥 Всего лидов: <b>{total}</b>\n"
        f"📱 С телефоном: <b>{with_phone}</b> "
        f"({round(with_phone / total * 100) if total else 0}%)\n"
        f"📣 Из рекламы: <b>{from_ads}</b>\n\n"
        "<b>По статусу:</b>\n"
    )
    for status, count in sorted(statuses.items()):
        text += f"  • {status}: {count}\n"

    text += "\n<b>По источнику:</b>\n"
    for source, count in sorted(sources.items(), key=lambda x: -x[1]):
        text += f"  • {source}: {count}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("export"))
async def cmd_export(message: Message):
    """Export all leads as CSV file."""
    if not is_admin(message.from_user.id):
        await message.answer(t("admin_no_access", "ru"))
        return

    leads = await db.get_recent_leads(limit=10000)

    if not leads:
        await message.answer("📭 Лидов для экспорта нет.")
        return

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "telegram_id", "first_name", "last_name", "username",
        "phone", "email", "source", "status", "lead_score",
        "language", "created_at",
    ])

    for lead in leads:
        writer.writerow([
            lead.get("telegram_id"),
            lead.get("first_name", ""),
            lead.get("last_name", ""),
            lead.get("username", ""),
            lead.get("phone", ""),
            lead.get("email", ""),
            lead.get("source", ""),
            lead.get("status", ""),
            lead.get("lead_score", 0),
            lead.get("preferred_lang", ""),
            lead.get("created_at", "")[:19],
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")  # BOM for Excel
    file = BufferedInputFile(csv_bytes, filename="leads_export.csv")

    await message.answer_document(file, caption=f"📊 Экспорт: {len(leads)} лидов")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Broadcast a message to all leads. Usage: /broadcast <text>"""
    if not is_admin(message.from_user.id):
        await message.answer(t("admin_no_access", "ru"))
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: /broadcast <текст сообщения>")
        return

    import asyncio, logging
    leads = await db.get_all_leads()
    sent = failed = 0
    status_msg = await message.answer(f"📤 Отправка {len(leads)} пользователям...")

    for lead in leads:
        tid = lead.get("telegram_id")
        if not tid:
            failed += 1
            continue
        try:
            await message.bot.send_message(tid, text, parse_mode="HTML")
            sent += 1
        except Exception as e:
            logging.getLogger(__name__).warning(f"Broadcast failed for {tid}: {e}")
            failed += 1
        await asyncio.sleep(0.05)  # stay under Telegram rate limit

    await status_msg.edit_text(
        f"✅ Рассылка завершена\n\n"
        f"📨 Доставлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )


@router.message(Command("lead"))
async def cmd_lead_detail(message: Message):
    """View detailed info about a specific lead. Usage: /lead <telegram_id>"""
    if not is_admin(message.from_user.id):
        await message.answer(t("admin_no_access", "ru"))
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /lead <telegram_id>")
        return

    try:
        telegram_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный ID. Используйте число.")
        return

    lead = await db.get_lead(telegram_id)
    if not lead:
        await message.answer("❌ Лид не найден.")
        return

    # Get conversation
    convos = await db.get_conversation(telegram_id, limit=10)

    name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
    text = (
        f"👤 <b>{name}</b>\n"
        f"🆔 @{lead.get('username', '—')}\n"
        f"📱 {lead.get('phone') or '—'}\n"
        f"📧 {lead.get('email') or '—'}\n"
        f"📊 Источник: {lead.get('source', 'organic')}\n"
        f"🏷 Статус: {lead.get('status', 'new')}\n"
        f"⭐ Баллы: {lead.get('lead_score', 0)}\n"
        f"🌐 Язык: {lead.get('preferred_lang', '—')}\n"
        f"📅 Создан: {lead.get('created_at', '')[:19]}\n\n"
    )

    if convos:
        text += "<b>Последние сообщения:</b>\n\n"
        for msg in convos[-10:]:
            role = "👤" if msg["role"] == "user" else "🤖"
            content = msg["message"][:100]
            text += f"{role} {content}\n\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("crm"))
async def cmd_crm(message: Message):
    """Open the CRM dashboard as a Telegram Web App."""
    if not is_admin(message.from_user.id):
        return  # silently ignore for non-admins

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📊 Открыть CRM",
            web_app=WebAppInfo(url="https://twa-jet.vercel.app/admin.html"),
        )
    ]])
    await message.answer("🗂 CRM — управление лидами", reply_markup=keyboard)


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
            next_time = job.next_run_time
            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=tz.utc)
            delta = next_time.astimezone(tz.utc) - now
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


@router.message(Command("ask"))
async def cmd_ask(message: Message):
    """/ask <question> — ask a natural language question about your CRM leads."""
    if not is_admin(message.from_user.id):
        return

    question = message.text.removeprefix("/ask").strip()
    if not question:
        await message.answer(
            "💬 <b>Использование:</b> /ask &lt;вопрос&gt;\n\n"
            "<b>Примеры:</b>\n"
            "• /ask Какие лиды из meta не связались?\n"
            "• /ask Топ 5 лидов по баллам\n"
            "• /ask Что сказал Jasur в последнем чате?\n"
            "• /ask Сколько лидов конвертировалось?\n"
            "• /ask Покажи лиды без телефона с 5+ сообщениями",
            parse_mode="HTML",
        )
        return

    thinking = await message.answer("🤔 Анализирую...")
    try:
        from bot.services.crm_ai import answer_crm_question
        answer = await answer_crm_question(question)
    except Exception as e:
        await thinking.delete()
        await message.answer(f"❌ Ошибка: {e}")
        return

    await thinking.delete()

    # Telegram message limit is 4096 chars — split at paragraph boundaries
    if len(answer) <= 4096:
        await message.answer(answer, parse_mode="HTML")
        return

    chunks = []
    current = ""
    for paragraph in answer.split("\n\n"):
        if len(current) + len(paragraph) + 2 <= 4096:
            current += ("" if not current else "\n\n") + paragraph
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")
