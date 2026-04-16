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
        "followup_reminders_hours": 1,    # team CRM reminder notifications
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
