import asyncio
from bot.services.db_service import db
from bot.config import config
from datetime import datetime

async def verify():
    print(f"Current Config TZ: {config.TIMEZONE}")
    now = datetime.now(config.tz)
    print(f"Current Local Time (Tashkent): {now.isoformat()}")
    
    # Check a lead's updated_at
    res = db.client.table("leads").select("telegram_id, last_activity_at").limit(5).execute()
    for row in res.data:
        print(f"Lead {row['telegram_id']} last_activity_at: {row['last_activity_at']}")

if __name__ == "__main__":
    asyncio.run(verify())
