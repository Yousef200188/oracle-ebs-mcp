"""
Tool: EBS Security & Responsibilities Administrator
Inspects menus, request groups, data groups, active user roles, and security profiles.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import InputValidationError


def get_responsibility_details_tool(responsibility_name: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive security architecture for an Oracle EBS Responsibility:
    Responsibility ID, Application ID, Attached Root Menu, Request Group, and Data Group.
    """
    if not responsibility_name or not responsibility_name.strip():
        raise InputValidationError("Parameter 'responsibility_name' is required.")

    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            sql = """
            SELECT 
                fr.responsibility_id,
                fr.responsibility_key,
                fr.responsibility_name,
                fa.application_short_name,
                fa.application_name,
                fm.menu_name AS root_menu_name,
                fm.user_menu_name AS root_user_menu_name,
                frg.request_group_name,
                fdg.data_group_name,
                TO_CHAR(fr.start_date, 'YYYY-MM-DD') AS start_date,
                TO_CHAR(fr.end_date, 'YYYY-MM-DD') AS end_date,
                fr.description
            FROM 
                apps.fnd_responsibility_vl fr
                JOIN apps.fnd_application_vl fa ON fr.application_id = fa.application_id
                LEFT JOIN apps.fnd_menus_vl fm ON fr.menu_id = fm.menu_id
                LEFT JOIN apps.fnd_request_groups frg ON fr.request_group_id = frg.request_group_id
                LEFT JOIN apps.fnd_data_groups fdg ON fr.data_group_id = fdg.data_group_id
            WHERE 
                UPPER(fr.responsibility_name) = UPPER(:resp_name)
                OR UPPER(fr.responsibility_key) = UPPER(:resp_name)
            """
            cursor.execute(sql, {"resp_name": responsibility_name.strip()})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "responsibility_name": responsibility_name,
                    "message": f"Responsibility '{responsibility_name}' was not found in FND_RESPONSIBILITY_VL.",
                }

            cols = [col[0].lower() for col in cursor.description]
            resp_data = dict(zip(cols, row))

            return {
                "status": "success",
                "responsibility": resp_data,
            }


def get_user_access_tool(username: str) -> Dict[str, Any]:
    """
    Inspect an Oracle EBS User's active account:
    USER_ID, assigned employee, active responsibilities with validity dates, and account status.
    """
    if not username or not username.strip():
        raise InputValidationError("Parameter 'username' is required.")

    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. User Header
            user_sql = """
            SELECT 
                fu.user_id,
                fu.user_name,
                fu.employee_id,
                papf.full_name AS employee_name,
                papf.employee_number,
                fu.email_address,
                TO_CHAR(fu.start_date, 'YYYY-MM-DD') AS start_date,
                TO_CHAR(fu.end_date, 'YYYY-MM-DD') AS end_date,
                CASE 
                    WHEN fu.end_date IS NOT NULL AND fu.end_date < SYSDATE THEN 'EXPIRED'
                    ELSE 'ACTIVE'
                END AS account_status
            FROM 
                apps.fnd_user fu
                LEFT JOIN apps.per_all_people_f papf 
                    ON fu.employee_id = papf.person_id 
                    AND TRUNC(SYSDATE) BETWEEN papf.effective_start_date AND papf.effective_end_date
            WHERE 
                UPPER(fu.user_name) = UPPER(:username)
            """
            cursor.execute(user_sql, {"username": username.strip()})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "username": username,
                    "message": f"User '{username}' was not found in FND_USER.",
                }

            cols = [col[0].lower() for col in cursor.description]
            user_data = dict(zip(cols, row))

            # 2. Assigned Responsibilities
            resp_sql = """
            SELECT 
                fr.responsibility_id,
                fr.responsibility_name,
                fa.application_short_name,
                urg.security_group_id,
                TO_CHAR(urg.start_date, 'YYYY-MM-DD') AS start_date,
                TO_CHAR(urg.end_date, 'YYYY-MM-DD') AS end_date,
                CASE 
                    WHEN (urg.start_date IS NULL OR urg.start_date <= SYSDATE)
                     AND (urg.end_date IS NULL OR urg.end_date >= SYSDATE) THEN 'ACTIVE'
                    ELSE 'INACTIVE'
                END AS assignment_status
            FROM 
                apps.fnd_user_resp_groups_all urg
                JOIN apps.fnd_responsibility_vl fr 
                    ON urg.responsibility_id = fr.responsibility_id 
                    AND urg.responsibility_application_id = fr.application_id
                JOIN apps.fnd_application fa ON fr.application_id = fa.application_id
            WHERE 
                urg.user_id = :user_id
            ORDER BY fr.responsibility_name
            """
            cursor.execute(resp_sql, {"user_id": user_data["user_id"]})
            resp_cols = [col[0].lower() for col in cursor.description]
            resps = [dict(zip(resp_cols, r)) for r in cursor.fetchall()]

            return {
                "status": "success",
                "user": user_data,
                "responsibilities_count": len(resps),
                "responsibilities": resps,
            }
