import asyncio
import os
from bot.services.db_service import db
from bot.config import config
from datetime import datetime, timezone

async def check():
    res = db.client.table("campaigns").select("*").eq("status", "scheduled").execute()
    print(f"Scheduled campaigns: {len(res.data)}")
    for camp in res.data:
        print(f"ID: {camp['id']}, Scheduled for: {camp['scheduled_for']}, Now: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    asyncio.run(check())
