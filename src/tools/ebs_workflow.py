"""
Tool: Oracle Workflow & Approvals Inspector
Inspects live workflow item statuses, active activities, pending approvals, and notifications.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import InputValidationError


def get_workflow_status_tool(item_type: str, item_key: str) -> Dict[str, Any]:
    """
    Retrieve real-time status, activity execution history, error messages,
    and open notifications for an Oracle Workflow item.
    """
    if not item_type or not item_key:
        raise InputValidationError("Both 'item_type' and 'item_key' are required.")

    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Workflow Item Details
            item_sql = """
            SELECT 
                wi.item_type,
                wit.display_name AS item_type_display,
                wi.item_key,
                wi.root_activity,
                TO_CHAR(wi.begin_date, 'YYYY-MM-DD HH24:MI:SS') AS begin_date,
                TO_CHAR(wi.end_date, 'YYYY-MM-DD HH24:MI:SS') AS end_date,
                wi.user_key,
                wi.owner_role
            FROM 
                apps.wf_items wi
                JOIN apps.wf_item_types_tl wit 
                    ON wi.item_type = wit.name 
                    AND wit.language = 'US'
            WHERE 
                wi.item_type = :item_type
                AND wi.item_key = :item_key
            """
            cursor.execute(item_sql, {"item_type": item_type.upper(), "item_key": str(item_key)})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "item_type": item_type,
                    "item_key": item_key,
                    "message": f"Workflow item {item_type}/{item_key} not found in WF_ITEMS.",
                }

            cols = [col[0].lower() for col in cursor.description]
            item_data = dict(zip(cols, row))

            # 2. Activity Statuses & Current State
            act_sql = """
            SELECT 
                wias.activity_label,
                wa.display_name AS activity_display_name,
                wias.activity_status_code,
                wias.activity_result_code,
                wias.assigned_user,
                wias.notification_id,
                TO_CHAR(wias.begin_date, 'YYYY-MM-DD HH24:MI:SS') AS activity_begin_date,
                TO_CHAR(wias.execution_time, 'YYYY-MM-DD HH24:MI:SS') AS execution_time,
                wias.error_name,
                wias.error_message,
                wias.error_stack
            FROM 
                apps.wf_item_activity_statuses_v wias
                LEFT JOIN apps.wf_activities_tl wa 
                    ON wias.activity_id = wa.activity_id 
                    AND wa.language = 'US'
            WHERE 
                wias.item_type = :item_type
                AND wias.item_key = :item_key
            ORDER BY wias.activity_begin_date DESC
            """
            cursor.execute(act_sql, {"item_type": item_type.upper(), "item_key": str(item_key)})
            act_cols = [col[0].lower() for col in cursor.description]
            activities = [dict(zip(act_cols, r)) for r in cursor.fetchall()[:20]]

            # 3. Open Notifications
            notif_sql = """
            SELECT 
                wn.notification_id,
                wn.recipient_role,
                wn.subject,
                wn.status,
                TO_CHAR(wn.begin_date, 'YYYY-MM-DD HH24:MI:SS') AS begin_date,
                TO_CHAR(wn.due_date, 'YYYY-MM-DD HH24:MI:SS') AS due_date
            FROM 
                apps.wf_notifications wn
            WHERE 
                wn.item_type = :item_type
                AND wn.item_key = :item_key
            ORDER BY wn.notification_id DESC
            """
            cursor.execute(notif_sql, {"item_type": item_type.upper(), "item_key": str(item_key)})
            notif_cols = [col[0].lower() for col in cursor.description]
            notifications = [dict(zip(notif_cols, r)) for r in cursor.fetchall()]

            has_error = any(a.get("activity_status_code") == "ERROR" for a in activities)

            return {
                "status": "success",
                "item": item_data,
                "workflow_state": "ERROR" if has_error else ("COMPLETED" if item_data.get("end_date") else "ACTIVE"),
                "activities_count": len(activities),
                "activities": activities,
                "notifications_count": len(notifications),
                "notifications": notifications,
            }


def get_workflow_notifications_tool(
    recipient_role: Optional[str] = None,
    status: str = "OPEN",
) -> Dict[str, Any]:
    """
    Retrieve open or closed workflow notifications/worklist for a user or role.
    """
    cfg = get_config()
    target_role = (recipient_role or cfg.ebs_username).upper()
    target_status = status.upper()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            sql = """
            SELECT 
                wn.notification_id,
                wn.item_type,
                wit.display_name AS item_type_name,
                wn.item_key,
                wn.recipient_role,
                wn.subject,
                wn.status,
                wn.message_type,
                TO_CHAR(wn.begin_date, 'YYYY-MM-DD HH24:MI:SS') AS sent_date,
                TO_CHAR(wn.due_date, 'YYYY-MM-DD HH24:MI:SS') AS due_date
            FROM 
                apps.wf_notifications wn
                LEFT JOIN apps.wf_item_types_tl wit 
                    ON wn.item_type = wit.name 
                    AND wit.language = 'US'
            WHERE 
                (wn.recipient_role = :role OR :role IS NULL)
                AND (:status = 'ALL' OR wn.status = :status)
            ORDER BY wn.notification_id DESC
            """
            cursor.execute(sql, {"role": target_role, "status": target_status})
            cols = [col[0].lower() for col in cursor.description]
            notifs = [dict(zip(cols, r)) for r in cursor.fetchall()[:50]]

            return {
                "status": "success",
                "recipient_role": target_role,
                "filter_status": target_status,
                "count": len(notifs),
                "notifications": notifs,
            }
