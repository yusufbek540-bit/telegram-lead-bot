"""
Sentiment analysis using gpt-4o-mini.
Checks recent conversations and assigns positive/neutral/negative sentiment.
"""
import logging
import json
import time
from datetime import datetime, timedelta
from aiogram import Bot
from bot.services.db_service import db
from bot.config import config

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """You are a CRM sales analyst.
Read the conversation from this lead. Extract the overall sentiment and any key buying signals.
Buying signals include: mentions of budget, timeline, price, urgency, or comparing competitors. objections are also key signals.

Return ONLY valid JSON matching this schema:
{
  "sentiment": "positive" | "neutral" | "negative",
  "key_signals": ["signal 1", "signal 2"]
}
"""

async def run_sentiment_analysis(bot: Bot = None):
    start_time = time.monotonic()
    logger.info("run_sentiment_analysis: starting")
    try:
        from bot.services.ai_service import get_client
        client = get_client()
        if not client:
            return

        # Fetch leads active in last 24 hours
        last_24h = datetime.now() - timedelta(hours=24)
        leads_res = db.supabase.table("leads")\
            .select("telegram_id, sentiment_updated_at")\
            .gte("last_activity_at", last_24h.isoformat())\
            .execute()
            
        leads = leads_res.data or []
        processed_count = 0
        
        for lead in leads:
            tid = lead["telegram_id"]
            # Skip if sentiment updated recently (last 6 hours)
            supdated = lead.get("sentiment_updated_at")
            if supdated:
                supdated_dt = datetime.fromisoformat(supdated.replace('Z', '+00:00'))
                if (datetime.now(supdated_dt.tzinfo) - supdated_dt).total_seconds() < 6 * 3600:
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
                messages=[{"role": "system", "content": SENTIMENT_PROMPT}, {"role": "user", "content": conv_text}],
                temperature=0.1,
                max_tokens=100,
            )
            
            res_text = response.choices[0].message.content.strip()
            try:
                res_text = res_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(res_text)
                
                sentiment = data.get("sentiment", "neutral").lower()
                if sentiment not in ("positive", "neutral", "negative"):
                    sentiment = "neutral"
                    
                key_signals = [str(s)[:100] for s in data.get("key_signals", []) if isinstance(s, str)]
                
                db.supabase.table("leads").update({
                    "sentiment": sentiment,
                    "key_signals": key_signals,
                    "sentiment_updated_at": datetime.now().isoformat()
                }).eq("telegram_id", tid).execute()
                
                processed_count += 1
            except Exception as e:
                logger.warning(f"Failed to parse sentiment for {tid}: {res_text} - {e}")
                
        elapsed = time.monotonic() - start_time
        logger.info(f"run_sentiment_analysis: done in {elapsed:.2f}s, processed {processed_count} leads")
    except Exception as e:
        logger.error(f"run_sentiment_analysis: failed - {e}", exc_info=True)
