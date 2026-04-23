"""
CRM AI — answers natural language questions about leads using OpenAI function calling.

Used by the /ask bot command (admin only).

Tools available to the AI:
  - query_leads: filter leads by status, source, score, phone, date
  - find_lead_by_name: fuzzy search by first/last name
  - query_conversations: get recent messages for a specific lead
  - get_analytics: aggregate stats (counts by status/source, avg score, conversion)

Agentic loop: up to 5 tool call rounds before returning the final answer.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from openai import AsyncOpenAI

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

_SYSTEM_PROMPT = """Ты CRM-аналитик для {agency_name} — маркетингового агентства в Ташкенте.
У тебя есть инструменты для запроса базы данных лидов. Используй их, чтобы отвечать точно.

Сегодняшняя дата: {today}

Статусы лидов: new, contacted, qualified, proposal_sent, won, lost
Источники: organic, meta_general, meta_fomo, google, telegram_ads и другие
Баллы лида: 0–100+ (телефон=30, email=20, сообщения=5–20, портфолио=10, звонок=25, услуги=5)

Всегда отвечай на русском языке. Будь краток и конкретен. Включай имена и цифры в ответы."""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_leads",
            "description": "Filter leads from the database. Returns up to 20 matching leads ordered by score desc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: new/contacted/qualified/proposal_sent/won/lost",
                    },
                    "source": {
                        "type": "string",
                        "description": "Filter by traffic source (e.g. meta_general, organic)",
                    },
                    "min_score": {
                        "type": "integer",
                        "description": "Minimum lead score (inclusive)",
                    },
                    "has_phone": {
                        "type": "boolean",
                        "description": "If true, only leads with a phone number",
                    },
                    "days_old": {
                        "type": "integer",
                        "description": "Only leads created in the last N days",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_lead_by_name",
            "description": "Find leads by partial first or last name match.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name or partial name to search for",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_conversations",
            "description": "Get the last 20 conversation messages for a specific lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "telegram_id": {
                        "type": "integer",
                        "description": "The lead's Telegram ID",
                    },
                },
                "required": ["telegram_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_analytics",
            "description": "Get aggregate analytics over all leads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": [
                            "count_by_status",
                            "count_by_source",
                            "avg_score",
                            "conversion_rate",
                            "total_count",
                        ],
                        "description": "Which aggregate metric to compute",
                    },
                },
                "required": ["metric"],
            },
        },
    },
]


async def _execute_tool(tool_name: str, args: dict) -> str:
    """Execute one tool call and return a JSON string result."""
    try:
        if tool_name == "query_leads":
            query = db.client.table("leads").select(
                "telegram_id, first_name, last_name, username, phone, "
                "status, source, lead_score, created_at, first_contact_at"
            )
            if args.get("status"):
                query = query.eq("status", args["status"])
            if args.get("source"):
                query = query.eq("source", args["source"])
            if args.get("min_score") is not None:
                query = query.gte("lead_score", args["min_score"])
            if args.get("has_phone"):
                query = query.not_.is_("phone", "null")
            if args.get("days_old"):
                since = datetime.now(config.tz) - timedelta(days=int(args["days_old"]))
                query = query.gte("created_at", since.isoformat())
            result = query.order("lead_score", desc=True).limit(20).execute()
            return json.dumps(result.data or [], ensure_ascii=False)

        elif tool_name == "find_lead_by_name":
            name = args["name"]
            result = (
                db.client.table("leads")
                .select(
                    "telegram_id, first_name, last_name, username, phone, "
                    "status, source, lead_score"
                )
                .or_(f"first_name.ilike.%{name}%,last_name.ilike.%{name}%")
                .limit(10)
                .execute()
            )
            return json.dumps(result.data or [], ensure_ascii=False)

        elif tool_name == "query_conversations":
            tid = int(args["telegram_id"])
            result = (
                db.client.table("conversations")
                .select("role, message, created_at")
                .eq("telegram_id", tid)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            messages = list(reversed(result.data or []))
            return json.dumps(messages, ensure_ascii=False)

        elif tool_name == "get_analytics":
            metric = args["metric"]
            all_result = db.client.table("leads").select(
                "status, source, lead_score, phone"
            ).execute()
            leads = all_result.data or []

            if metric == "total_count":
                return json.dumps({"total": len(leads)})
            elif metric == "count_by_status":
                counts: dict = {}
                for lead in leads:
                    s = lead.get("status", "new")
                    counts[s] = counts.get(s, 0) + 1
                return json.dumps(counts)
            elif metric == "count_by_source":
                counts = {}
                for lead in leads:
                    s = lead.get("source", "organic")
                    counts[s] = counts.get(s, 0) + 1
                return json.dumps(dict(sorted(counts.items(), key=lambda x: -x[1])))
            elif metric == "avg_score":
                scores = [
                    lead.get("lead_score", 0)
                    for lead in leads
                    if lead.get("lead_score") is not None
                ]
                avg = round(sum(scores) / len(scores), 1) if scores else 0
                return json.dumps({"avg_score": avg, "sample_size": len(leads)})
            elif metric == "conversion_rate":
                won = sum(1 for lead in leads if lead.get("status") == "won")
                total = len(leads)
                rate = round(won / total * 100, 1) if total else 0
                return json.dumps({
                    "won": won,
                    "total": total,
                    "conversion_rate_pct": rate,
                })
            return json.dumps({"error": "unknown metric"})

        return json.dumps({"error": f"unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"_execute_tool {tool_name} failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


async def answer_crm_question(question: str) -> str:
    """Answer a natural language CRM question using function calling.

    Runs an agentic loop of up to 5 tool-call rounds. Returns the AI's
    plain-language answer in Russian.
    """
    today = datetime.now(config.tz).strftime("%Y-%m-%d")
    system = _SYSTEM_PROMPT.format(agency_name=config.AGENCY_NAME, today=today)

    messages: list = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]

    for _ in range(5):  # max 5 tool rounds
        response = await _client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "Не удалось получить ответ."

        # Execute every tool call in this round
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = await _execute_tool(tc.function.name, args)
            logger.info(f"CRM AI tool {tc.function.name}({args}) → {result[:120]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "Превышен лимит запросов. Попробуйте переформулировать вопрос."
