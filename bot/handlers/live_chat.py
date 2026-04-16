from __future__ import annotations
"""
Live chat handler — lets users request a real manager and enables
two-way forwarding while the session is active.
"""
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard, back_to_menu_keyboard

router = Router()


# ── USER: request live chat ────────────────────────────────────

@router.callback_query(F.data == "live_chat_request")
async def cb_live_chat_request(callback: CallbackQuery):
    user = callback.from_user
    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Mark as requested
    await db.update_lead(user.id, live_chat=True)
    await db.track_event(user.id, "live_chat_requested", {})

    await callback.message.edit_text(
        t("live_chat_request", lang),
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()

    # Notify assigned manager or all admins
    await _notify_managers(callback.bot, lead, message_text=None)


# ── USER: end chat ─────────────────────────────────────────────

@router.message(Command("endchat"))
async def cmd_end_chat(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(message.from_user.id, live_chat=False)
    await db.track_event(message.from_user.id, "live_chat_ended_by_user", {})

    await message.answer(
        t("live_chat_ended_user", lang),
        reply_markup=main_menu_keyboard(lang),
    )


# ── HELPERS ────────────────────────────────────────────────────

async def _notify_managers(bot, lead: dict, message_text: str | None):
    """Notify assigned manager (by name lookup in DB), fall back to all admins."""
    name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—"
    username = lead.get("username") or "—"
    phone = lead.get("phone") or "—"
    assigned_to = lead.get("assigned_to") or "—"

    if message_text:
        text = t("admin_live_chat_message", "ru",
                 name=escape(name),
                 message=escape(message_text))
    else:
        text = t("admin_live_chat_request", "ru",
                 name=escape(name),
                 username=escape(username),
                 phone=escape(phone),
                 assigned_to=escape(assigned_to),
                 message="(нет сообщения)")

    # Try to notify only the assigned manager
    target_ids = []
    if lead.get("assigned_to"):
        member = await db.get_team_member_by_name(lead["assigned_to"])
        if member and member.get("telegram_id"):
            target_ids = [member["telegram_id"]]

    # Fall back to all admins if unassigned or member not found
    if not target_ids:
        target_ids = list(config.ADMIN_IDS)

    for tid in target_ids:
        try:
            await bot.send_message(tid, text, parse_mode="HTML")
        except Exception:
            pass


async def end_live_chat_for_user(bot, telegram_id: int):
    """Called from TWA-triggered bot command to end a user's live chat."""
    lead = await db.get_lead(telegram_id)
    if not lead:
        return
    lang = lead.get("preferred_lang", config.DEFAULT_LANG)
    await db.update_lead(telegram_id, live_chat=False)
    try:
        await bot.send_message(
            telegram_id,
            t("live_chat_ended_user", lang),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception:
        pass
