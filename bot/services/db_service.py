"""
Database service — handles all Supabase operations.
Manages leads, conversations, and events.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from bot.config import config


class DatabaseService:
    def __init__(self):
        self.client: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    @property
    def supabase(self) -> Client:
        """Alias for self.client — used by routing, tagger, sentiment services."""
        return self.client

    # ── LEADS ──────────────────────────────────────────────────

    async def upsert_lead(
        self,
        telegram_id: int,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        language_code: str = None,
        source: str = "organic",
    ) -> dict:
        """Create or update a lead. Called on /start."""
        data = {
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "language_code": language_code,
            "source": source,
        }
        # Remove None values so we don't overwrite existing data
        data = {k: v for k, v in data.items() if v is not None}

        result = (
            self.client.table("leads")
            .upsert(data, on_conflict="telegram_id")
            .execute()
        )
        return result.data[0] if result.data else {}

    async def get_lead(self, telegram_id: int) -> dict | None:
        """Get a single lead by Telegram ID."""
        result = (
            self.client.table("leads")
            .select("*")
            .eq("telegram_id", telegram_id)
            .execute()
        )
        return result.data[0] if result.data else None

    async def update_lead(self, telegram_id: int, **kwargs) -> dict:
        """Update lead fields (phone, email, status, etc.)."""
        result = (
            self.client.table("leads")
            .update(kwargs)
            .eq("telegram_id", telegram_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    async def update_lead_phone(self, telegram_id: int, phone: str) -> dict:
        """Update lead's phone number."""
        return await self.update_lead(telegram_id, phone=phone)

    async def update_lead_lang(self, telegram_id: int, lang: str) -> dict:
        """Update lead's preferred language."""
        return await self.update_lead(telegram_id, preferred_lang=lang)

    async def get_recent_leads(self, limit: int = 20) -> list:
        """Get most recent leads (for admin)."""
        result = (
            self.client.table("leads")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data

    async def already_sent_followup(self, telegram_id: int, event_type: str) -> bool:
        """Check if a specific follow-up was already sent to this user."""
        result = (
            self.client.table("events")
            .select("id")
            .eq("telegram_id", telegram_id)
            .eq("event_type", event_type)
            .limit(1)
            .execute()
        )
        return bool(result.data)

    async def get_silent_starters(self) -> list:
        """
        Leads where created_at > 2h ago, zero rows in conversations.
        These opened the bot but never typed anything.
        """
        from datetime import timedelta
        cutoff = (datetime.now(config.tz) - timedelta(hours=2)).isoformat()
        leads = (
            self.client.table("leads")
            .select("telegram_id, preferred_lang, first_name")
            .lte("created_at", cutoff)
            .execute()
        ).data

        result = []
        for lead in leads:
            if await self.already_sent_followup(lead["telegram_id"], "followup_silent_start"):
                continue
            convo = (
                self.client.table("conversations")
                .select("id")
                .eq("telegram_id", lead["telegram_id"])
                .limit(1)
                .execute()
            )
            if not convo.data:
                result.append(lead)
        return result

    async def get_engaged_gone(self) -> list:
        """
        Leads whose most recent conversation message is older than 24 hours
        and who have NOT shared their phone (already in contact = skip).
        """
        from datetime import timedelta
        cutoff = (datetime.now(config.tz) - timedelta(hours=24)).isoformat()
        leads = (
            self.client.table("leads")
            .select("telegram_id, preferred_lang, first_name")
            .is_("phone", "null")
            .execute()
        ).data

        result = []
        for lead in leads:
            if await self.already_sent_followup(lead["telegram_id"], "followup_engaged_gone"):
                continue
            last_msg = (
                self.client.table("conversations")
                .select("created_at")
                .eq("telegram_id", lead["telegram_id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if last_msg.data and last_msg.data[0]["created_at"] <= cutoff:
                result.append(lead)
        return result

    async def get_no_phone_after_conversation(self) -> list:
        """
        Leads where phone IS NULL, 5+ messages, and last message > 48h ago.
        """
        from datetime import timedelta
        cutoff = (datetime.now(config.tz) - timedelta(hours=48)).isoformat()
        leads = (
            self.client.table("leads")
            .select("telegram_id, preferred_lang, first_name")
            .is_("phone", "null")
            .execute()
        ).data

        result = []
        for lead in leads:
            if await self.already_sent_followup(lead["telegram_id"], "followup_no_phone"):
                continue
            msgs = (
                self.client.table("conversations")
                .select("created_at")
                .eq("telegram_id", lead["telegram_id"])
                .order("created_at", desc=True)
                .execute()
            )
            if len(msgs.data) >= 5 and msgs.data[0]["created_at"] <= cutoff:
                result.append(lead)
        return result

    async def get_team_member_by_name(self, name: str) -> dict | None:
        """Look up a team member by name. Returns None if not found or table missing."""
        try:
            result = (
                self.client.table("team_members")
                .select("telegram_id, name")
                .eq("name", name)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception:
            return None

    async def get_all_leads(self) -> list:
        """Get all leads (for broadcast)."""
        result = (
            self.client.table("leads")
            .select("telegram_id, preferred_lang")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data

    async def get_lead_count_by_source(self) -> list:
        """Analytics: leads grouped by source (uses leads_by_source view)."""
        result = self.client.table("leads_by_source").select("*").execute()
        return result.data

    # ── CONVERSATIONS ──────────────────────────────────────────

    async def save_message(self, telegram_id: int, role: str, message: str,
                           is_sent: bool = True, source: str = "ai_chat"):
        """Save a conversation message and update lead's last_activity_at."""
        # Unread logic: if user sends message, mark as unread (is_read=False)
        is_read = False if role == "user" else True

        self.client.table("conversations").insert(
            {
                "telegram_id": telegram_id,
                "role": role,
                "message": message,
                "is_sent": is_sent,
                "is_read": is_read,
                "source": source,
            }
        ).execute()
        # Update last_activity_at on every user message for stale detection
        if role == "user":
            self.client.table("leads").update(
                {"last_activity_at": datetime.now(config.tz).isoformat()}
            ).eq("telegram_id", telegram_id).execute()

    async def get_pending_assistant_messages(self) -> list:
        """Fetch assistant messages that need to be delivered to users."""
        result = (
            self.client.table("conversations")
            .select("*")
            .eq("role", "assistant")
            .eq("is_sent", False)
            .order("created_at", desc=False)
            .execute()
        )
        return result.data

    async def mark_message_sent(self, msg_id: int):
        """Mark a CRM message as successfully delivered."""
        self.client.table("conversations").update({"is_sent": True}).eq("id", msg_id).execute()

    async def mark_lead_read(self, telegram_id: int):
        """Mark all messages from/to this lead as read."""
        self.client.table("conversations").update({"is_read": True}).eq("telegram_id", telegram_id).execute()

    async def get_conversation(self, telegram_id: int, limit: int = 20) -> list:
        """Get recent conversation history for AI context."""
        result = (
            self.client.table("conversations")
            .select("role, message")
            .eq("telegram_id", telegram_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data

    async def clear_conversation(self, telegram_id: int):
        """Delete all conversation history for a user."""
        self.client.table("conversations").delete().eq("telegram_id", telegram_id).execute()

    # ── EVENTS ─────────────────────────────────────────────────

    async def track_event(
        self, telegram_id: int, event_type: str, event_data: dict = None
    ):
        """Track a behavioral event."""
        self.client.table("events").insert(
            {
                "telegram_id": telegram_id,
                "event_type": event_type,
                "event_data": event_data or {},
            }
        ).execute()

    # ── LEAD SCORING ───────────────────────────────────────────

    async def recalculate_score(self, telegram_id: int) -> int:
        """Recalculate and update lead score."""
        lead = await self.get_lead(telegram_id)
        if not lead:
            return 0

        convos = await self.get_conversation(telegram_id, limit=100)
        user_msgs = [c for c in convos if c["role"] == "user"]

        events_result = (
            self.client.table("events")
            .select("event_type")
            .eq("telegram_id", telegram_id)
            .execute()
        )
        event_types = {e["event_type"] for e in events_result.data}

        score = compute_score(lead, len(user_msgs), event_types)
        await self.update_lead(telegram_id, lead_score=score)
        return score


def compute_score(lead: dict, user_msg_count: int, event_types: set) -> int:
    """Pure scoring function — no DB access, fully testable."""
    score = 0

    if lead.get("phone"):
        score += 30
    if lead.get("email"):
        score += 20

    if user_msg_count >= 10:
        score += 20
    elif user_msg_count >= 5:
        score += 15
    elif user_msg_count >= 2:
        score += 5

    if "twa_open" in event_types:
        score += 10
    if "callback_request" in event_types:
        score += 25
    if "projects" in event_types:
        score += 10
    if "services" in event_types:
        score += 5

    if lead.get("questionnaire_completed"):
        score += 15

    spend = lead.get("budget_range") or ""
    if spend == "q_spend_10k_plus":
        score += 25
    elif spend == "q_spend_3k_10k":
        score += 20
    elif spend == "q_spend_1k_3k":
        score += 10
    elif spend == "q_spend_lt1k":
        score += 5

    vertical = lead.get("business_type") or ""
    if vertical in ("q_v_realestate", "q_v_clinic", "q_v_education"):
        score += 10

    channels = lead.get("service_interest") or []
    if len(channels) >= 3:
        score += 10
    elif len(channels) >= 2:
        score += 5

    crm = lead.get("current_marketing") or ""
    if crm == "q_crm_yes":
        score += 10
    elif crm == "q_crm_sheet":
        score += 5

    if (lead.get("business_name") or "").strip():
        score += 5
    if (lead.get("website") or "").strip():
        score += 5

    return score


# Singleton instance
db = DatabaseService()
