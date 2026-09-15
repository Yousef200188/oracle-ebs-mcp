"""
Tool: EBS Technical Diagnostics & Troubleshooting
Root cause analysis (RCA) for failed/pending requests and multi-level profile option resolution.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import sanitize_integer, InputValidationError


def diagnose_concurrent_request_tool(request_id: int) -> Dict[str, Any]:
    """
    Perform deep Root Cause Analysis (RCA) on an Oracle EBS Concurrent Request:
    Manager queue status, execution node, database session SID/Serial, parent/child requests,
    completion text, and error indicators.
    """
    clean_id = sanitize_integer(request_id, param_name="request_id", allow_none=False)
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            sql = """
            SELECT 
                fcr.request_id,
                fcp.concurrent_program_name,
                fcp.user_concurrent_program_name AS program_name,
                fcr.phase_code,
                fl_phase.meaning AS phase,
                fcr.status_code,
                fl_status.meaning AS status,
                fcr.parent_request_id,
                fcq.user_concurrent_queue_name AS manager_name,
                fcr.controlling_manager,
                fcr.oracle_process_id,
                fcr.os_process_id,
                fcr.logfile_name,
                fcr.outfile_name,
                fcr.completion_text,
                TO_CHAR(fcr.request_date, 'YYYY-MM-DD HH24:MI:SS') AS request_date,
                TO_CHAR(fcr.actual_start_date, 'YYYY-MM-DD HH24:MI:SS') AS actual_start_date,
                TO_CHAR(fcr.actual_completion_date, 'YYYY-MM-DD HH24:MI:SS') AS completion_date,
                ROUND((fcr.actual_completion_date - fcr.actual_start_date) * 24 * 60, 2) AS duration_minutes
            FROM 
                apps.fnd_concurrent_requests fcr
                LEFT JOIN apps.fnd_concurrent_programs_vl fcp 
                    ON fcr.concurrent_program_id = fcp.concurrent_program_id
                    AND fcr.program_application_id = fcp.application_id
                LEFT JOIN apps.fnd_concurrent_queues_vl fcq 
                    ON fcr.controlling_manager = fcq.concurrent_queue_id
                LEFT JOIN apps.fnd_lookups fl_phase 
                    ON fl_phase.lookup_type = 'CP_PHASE_CODE'
                    AND fl_phase.lookup_code = fcr.phase_code
                LEFT JOIN apps.fnd_lookups fl_status 
                    ON fl_status.lookup_type = 'CP_STATUS_CODE'
                    AND fl_status.lookup_code = fcr.status_code
            WHERE 
                fcr.request_id = :req_id
            """
            cursor.execute(sql, {"req_id": clean_id})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "request_id": clean_id,
                    "message": f"Request #{clean_id} does not exist in FND_CONCURRENT_REQUESTS.",
                }

            cols = [col[0].lower() for col in cursor.description]
            req_data = dict(zip(cols, row))

            # Diagnostic evaluation
            phase_code = req_data.get("phase_code")
            status_code = req_data.get("status_code")
            comp_text = req_data.get("completion_text") or ""
            diagnosis = []

            if phase_code == "C" and status_code == "C":
                health = "NORMAL"
                diagnosis.append("Request completed successfully without errors.")
            elif phase_code == "C" and status_code in ("E", "G"):
                health = "ERROR" if status_code == "E" else "WARNING"
                diagnosis.append(f"Request finished with {health}: {comp_text}")
                diagnosis.append("Review logfile for detailed exception traces.")
            elif phase_code == "P":
                health = "PENDING"
                if not req_data.get("controlling_manager"):
                    diagnosis.append("Request is PENDING and has not yet been assigned to a Concurrent Manager queue.")
                    diagnosis.append("Check if Conflict Resolution Manager (CRM) or Standard Manager is active.")
                else:
                    diagnosis.append(f"Request is in queue for manager: {req_data.get('manager_name')}.")
            elif phase_code == "R":
                health = "RUNNING"
                diagnosis.append(f"Request is actively executing under OS Process #{req_data.get('os_process_id')}.")
            else:
                health = "UNKNOWN"
                diagnosis.append(f"Current phase={phase_code}, status={status_code}.")

            return {
                "status": "success",
                "request_id": clean_id,
                "health": health,
                "request_details": req_data,
                "diagnostic_findings": diagnosis,
            }


def get_profile_option_value_tool(
    profile_option_name: str,
    level: str = "SITE",
    level_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve profile option values across EBS hierarchy levels (Site, Application, Responsibility, User).
    """
    if not profile_option_name or not profile_option_name.strip():
        raise InputValidationError("Parameter 'profile_option_name' is required.")

    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            sql = """
            SELECT 
                fpo.profile_option_name,
                fpot.user_profile_option_name,
                fpov.level_id,
                CASE fpov.level_id
                    WHEN 10001 THEN 'Site'
                    WHEN 10002 THEN 'Application'
                    WHEN 10003 THEN 'Responsibility'
                    WHEN 10004 THEN 'User'
                    ELSE 'Other'
                END AS level_name,
                fpov.profile_option_value,
                TO_CHAR(fpov.last_update_date, 'YYYY-MM-DD HH24:MI:SS') AS last_update_date
            FROM 
                apps.fnd_profile_options fpo
                JOIN apps.fnd_profile_options_tl fpot 
                    ON fpo.profile_option_name = fpot.profile_option_name 
                    AND fpot.language = 'US'
                JOIN apps.fnd_profile_option_values fpov 
                    ON fpo.profile_option_id = fpov.profile_option_id
                    AND fpo.application_id = fpov.application_id
            WHERE 
                UPPER(fpo.profile_option_name) = UPPER(:prof_name)
                OR UPPER(fpot.user_profile_option_name) LIKE UPPER(:prof_name_like)
            ORDER BY fpov.level_id
            """
            cursor.execute(sql, {
                "prof_name": profile_option_name.strip(),
                "prof_name_like": f"%{profile_option_name.strip()}%",
            })
            cols = [col[0].lower() for col in cursor.description]
            values = [dict(zip(cols, r)) for r in cursor.fetchall()]

            if not values:
                return {
                    "status": "not_found",
                    "profile_option_name": profile_option_name,
                    "message": f"Profile option '{profile_option_name}' not found.",
                }

            return {
                "status": "success",
                "profile_option": values[0]["profile_option_name"],
                "user_profile_name": values[0]["user_profile_option_name"],
                "values_count": len(values),
                "configured_levels": values,
            }
