"""
Auto-tagger service using gpt-4o-mini.
Fetches untagged leads, analyzes their conversations, and assigns tags.
"""
import logging
import json
import time
from datetime import datetime, timedelta
from aiogram import Bot
from bot.services.db_service import db
from bot.config import config

logger = logging.getLogger(__name__)

TAGGER_PROMPT = """You are an expert CRM analyst.
Read the following conversation from a potential lead.
Extract 1 to 3 relevant tags that categorize their business type or service interest. 
Tags should be concise, e.g., "smm", "web_dev", "b2b_sales", "real_estate", "ai_bot".
Return ONLY a valid JSON array of strings, nothing else. Example: ["smm", "real_estate"]

Conversation:
{text}
"""

async def run_auto_tagger(bot: Bot = None):
    start_time = time.monotonic()
    logger.info("run_auto_tagger: starting")
    try:
        from bot.services.ai_service import get_client
        client = get_client() # ai_service exports get_client() which returns AsyncOpenAI client
        if not client:
            return

        since = datetime.now() - timedelta(days=7)
        leads_res = db.supabase.table("leads")\
            .select("telegram_id, last_activity_at")\
            .gte("last_activity_at", since.isoformat())\
            .execute()
            
        leads = leads_res.data or []
        tagged_count = 0
        
        for lead in leads:
            tid = lead["telegram_id"]
            
            # Check if tags already exist that are AI-generated to avoid re-tagging frequently.
            tags_res = db.supabase.table("lead_tags").select("id").eq("telegram_id", tid).eq("source", "ai").limit(1).execute()
            if tags_res.data:
                continue
                
            # Fetch conversation
            conv_res = db.supabase.table("conversations").select("role, message").eq("telegram_id", tid).order("created_at").execute()
            conv = conv_res.data or []
            if len(conv) < 2:
                continue # not enough context
                
            # Take last 10 lines
            conv_text = "\n".join([f"{c['role']}: {c['message']}" for c in conv[-10:]])
            
            response = await client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[{"role": "system", "content": TAGGER_PROMPT.replace("{text}", conv_text)}],
                temperature=0.1,
                max_tokens=60,
            )
            
            res_text = response.choices[0].message.content.strip()
            try:
                res_text = res_text.replace("```json", "").replace("```", "").strip()
                extracted_tags = json.loads(res_text)
                
                # Insert tags
                for tag in extracted_tags:
                    if not isinstance(tag, str): continue
                    cleaned_tag = str(tag).strip().lower()[:30]
                    if not cleaned_tag: continue
                    db.supabase.table("lead_tags").upsert({
                        "telegram_id": tid,
                        "tag": cleaned_tag,
                        "confidence": 85.0,
                        "source": "ai"
                    }, on_conflict="telegram_id,tag").execute()
                tagged_count += 1
            except Exception as e:
                logger.warning(f"Failed to parse tags for {tid}: {res_text} - {e}")
                
        elapsed = time.monotonic() - start_time
        logger.info(f"run_auto_tagger: done in {elapsed:.2f}s, tagged {tagged_count} leads")
    except Exception as e:
        logger.error(f"run_auto_tagger: failed - {e}", exc_info=True)
