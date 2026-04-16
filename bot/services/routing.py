"""
Smart Lead Routing — Assigns new leads to team members based on routing_rules table.
"""
import logging
import random
from bot.services.db_service import db

logger = logging.getLogger(__name__)

async def route_new_lead(telegram_id: int, source: str) -> str | None:
    """
    Assign the lead to an active team member using stored rules.
    If multiple active rules exist, evaluate them by priority.
    """
    try:
        members_res = db.supabase.table("team_members").select("*").eq("is_active", True).execute()
        members = members_res.data or []
        if not members:
            return None
            
        rules_res = db.supabase.table("routing_rules").select("*").eq("is_active", True).order("priority").execute()
        rules = rules_res.data or []
        
        assigned_name = None
        
        for rule in reversed(rules): # Process highest priority first if priority asc
            cond = rule.get("conditions", {})
            strat = rule.get("assignee_strategy")
            
            # Simple condition eval: if source matches
            if "source" in cond and source != cond["source"]:
                continue
                
            if strat == "round_robin":
                assigned_name = random.choice(members)["name"]
                break
            elif strat == "specialist":
                # Find members matching spec
                target_spec = cond.get("tag")
                specialists = [m for m in members if target_spec in (m.get("specialization") or [])]
                if specialists:
                    assigned_name = random.choice(specialists)["name"]
                    break
        
        if not assigned_name:
            # Fallback to general round robin among all active
            assigned_name = random.choice(members)["name"]
            
        # Write to DB
        db.supabase.table("leads").update({"assigned_to": assigned_name}).eq("telegram_id", telegram_id).execute()
        logger.info(f"Lead {telegram_id} assigned to {assigned_name} via routing.")
        return assigned_name

    except Exception as e:
        logger.error(f"Routing failed: {e}", exc_info=True)
        return None
