"""
Tool: Oracle EBS Forms & OAF Personalization Inspector
Inspects active Form Personalizations and OAF MDS metadata repository customizations.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import InputValidationError


def get_form_personalizations_tool(form_name: str) -> Dict[str, Any]:
    """
    Retrieve active Form Personalizations for an Oracle Forms 10g form:
    Rules, Trigger Events (WHEN-NEW-FORM-INSTANCE, WHEN-VALIDATE-RECORD, etc.), conditions, and actions.
    """
    if not form_name or not form_name.strip():
        raise InputValidationError("Parameter 'form_name' is required.")

    clean_form = form_name.strip().upper()
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Personalization Rules
            rules_sql = """
            SELECT 
                fcr.id AS rule_id,
                fcr.function_name,
                fcr.form_name,
                fcr.sequence,
                fcr.description,
                fcr.trigger_event,
                fcr.trigger_object,
                fcr.condition,
                fcr.fire_in_enter_query,
                fcr.enabled
            FROM 
                apps.fnd_form_custom_rules fcr
            WHERE 
                UPPER(fcr.form_name) = :form_name
                OR UPPER(fcr.function_name) = :form_name
            ORDER BY fcr.sequence
            """
            cursor.execute(rules_sql, {"form_name": clean_form})
            cols = [col[0].lower() for col in cursor.description]
            rules = [dict(zip(cols, r)) for r in cursor.fetchall()]

            if not rules:
                return {
                    "status": "not_found",
                    "form_name": clean_form,
                    "message": f"No form personalizations found for '{clean_form}'.",
                }

            # 2. Rule Actions
            rule_ids = [r["rule_id"] for r in rules]
            actions_by_rule = {}
            if rule_ids:
                placeholders = ",".join(str(rid) for rid in rule_ids[:50])
                act_sql = f"""
                SELECT 
                    rule_id,
                    action_type,
                    sequence,
                    summary,
                    target_object,
                    property_name,
                    property_value,
                    message_type,
                    message_text,
                    enabled
                FROM 
                    apps.fnd_form_custom_actions
                WHERE 
                    rule_id IN ({placeholders})
                ORDER BY sequence
                """
                cursor.execute(act_sql)
                act_cols = [col[0].lower() for col in cursor.description]
                for r in cursor.fetchall():
                    act_dict = dict(zip(act_cols, r))
                    r_id = act_dict["rule_id"]
                    if r_id not in actions_by_rule:
                        actions_by_rule[r_id] = []
                    actions_by_rule[r_id].append(act_dict)

            for r in rules:
                r["actions"] = actions_by_rule.get(r["rule_id"], [])

            return {
                "status": "success",
                "form_name": clean_form,
                "rules_count": len(rules),
                "rules": rules,
            }


def get_oaf_personalizations_tool(page_path: str) -> Dict[str, Any]:
    """
    Inspect OAF MDS repository for active page personalizations and customizations.
    """
    if not page_path or not page_path.strip():
        raise InputValidationError("Parameter 'page_path' is required (e.g. /oracle/apps/per/...).")

    clean_path = page_path.strip()
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            sql = """
            SELECT 
                jp.path_name,
                jp.path_docid,
                jcp.path_name AS parent_path
            FROM 
                apps.jdr_paths jp
                LEFT JOIN apps.jdr_paths jcp ON jp.path_owner_docid = jcp.path_docid
            WHERE 
                jp.path_name LIKE '%customizations%'
                OR jp.path_name LIKE '%' || :path_pattern || '%'
            ORDER BY jp.path_docid DESC
            """
            cursor.execute(sql, {"path_pattern": clean_path.split("/")[-1]})
            cols = [col[0].lower() for col in cursor.description]
            paths = [dict(zip(cols, r)) for r in cursor.fetchall()[:30]]

            return {
                "status": "success",
                "target_page": clean_path,
                "customizations_found": len(paths),
                "customizations": paths,
            }
