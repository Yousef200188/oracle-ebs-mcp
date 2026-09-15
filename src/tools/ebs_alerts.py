"""
Tool: Oracle EBS Alerts Inspector
Inspects Event Alerts, Periodic Alerts, SQL conditions, and triggered actions.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import InputValidationError


def get_alert_details_tool(alert_name: str) -> Dict[str, Any]:
    """
    Retrieve definition, SQL logic, triggers, and action recipients for an Oracle Alert.
    """
    if not alert_name or not alert_name.strip():
        raise InputValidationError("Parameter 'alert_name' is required.")

    clean_name = alert_name.strip().upper()
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Alert Header
            alert_sql = """
            SELECT 
                al.alert_id,
                al.alert_name,
                fa.application_short_name,
                fa.application_name,
                al.alert_condition_type,
                CASE al.alert_condition_type
                    WHEN 'E' THEN 'Event Alert'
                    WHEN 'P' THEN 'Periodic Alert'
                    ELSE 'Other'
                END AS alert_type_desc,
                al.enabled_flag,
                al.sql_statement_text,
                al.description
            FROM 
                apps.alr_alerts al
                JOIN apps.fnd_application_vl fa ON al.application_id = fa.application_id
            WHERE 
                UPPER(al.alert_name) = :alert_name
            """
            cursor.execute(alert_sql, {"alert_name": clean_name})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "alert_name": clean_name,
                    "message": f"Alert '{clean_name}' was not found in ALR_ALERTS.",
                }

            cols = [col[0].lower() for col in cursor.description]
            alert_data = dict(zip(cols, row))

            # 2. Actions
            act_sql = """
            SELECT 
                aa.action_id,
                aa.name AS action_name,
                aa.action_type,
                aa.enabled_flag,
                aa.action_level_type,
                aa.description
            FROM 
                apps.alr_actions aa
            WHERE 
                aa.alert_id = :alert_id
            ORDER BY aa.action_id
            """
            cursor.execute(act_sql, {"alert_id": alert_data["alert_id"]})
            act_cols = [col[0].lower() for col in cursor.description]
            actions = [dict(zip(act_cols, r)) for r in cursor.fetchall()]

            return {
                "status": "success",
                "alert": alert_data,
                "actions_count": len(actions),
                "actions": actions,
            }
