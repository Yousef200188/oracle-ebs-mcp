"""
Tool: get_concurrent_request_status
Retrieves phase, status, runtime duration, and completion details for an EBS concurrent request.
Uses Oracle EBS standard API: FND_CONCURRENT.GET_REQUEST_STATUS.
"""

from typing import Any, Dict
from ..config import get_config
from ..database import get_connection, DatabaseError
from ..security import sanitize_integer, InputValidationError


STATUS_QUERY = """
SELECT 
    fcr.request_id,
    fcp.concurrent_program_name,
    fcp.user_concurrent_program_name AS program_name,
    fcr.phase_code,
    fl_phase.meaning AS phase,
    fcr.status_code,
    fl_status.meaning AS status,
    fu.user_name AS requested_by,
    fr.responsibility_name,
    fcr.argument_text AS parameters,
    TO_CHAR(fcr.request_date, 'YYYY-MM-DD HH24:MI:SS') AS requested_start_date,
    TO_CHAR(fcr.actual_start_date, 'YYYY-MM-DD HH24:MI:SS') AS actual_start_date,
    TO_CHAR(fcr.actual_completion_date, 'YYYY-MM-DD HH24:MI:SS') AS completion_date,
    ROUND((fcr.actual_completion_date - fcr.actual_start_date) * 24 * 60, 2) AS duration_minutes,
    fcr.completion_text,
    fcr.logfile_name,
    fcr.outfile_name
FROM 
    apps.fnd_concurrent_requests fcr
    LEFT JOIN apps.fnd_concurrent_programs_vl fcp 
        ON fcr.concurrent_program_id = fcp.concurrent_program_id
        AND fcr.program_application_id = fcp.application_id
    LEFT JOIN apps.fnd_user fu 
        ON fcr.requested_by = fu.user_id
    LEFT JOIN apps.fnd_responsibility_vl fr 
        ON fcr.responsibility_id = fr.responsibility_id
        AND fcr.responsibility_application_id = fr.application_id
    LEFT JOIN apps.fnd_lookups fl_phase 
        ON fl_phase.lookup_type = 'CP_PHASE_CODE'
        AND fl_phase.lookup_code = fcr.phase_code
    LEFT JOIN apps.fnd_lookups fl_status 
        ON fl_status.lookup_type = 'CP_STATUS_CODE'
        AND fl_status.lookup_code = fcr.status_code
WHERE 
    fcr.request_id = :request_id
"""


def get_concurrent_request_status_tool(request_id: int) -> Dict[str, Any]:
    """
    Retrieve real-time status and lifecycle details for an Oracle EBS Concurrent Request.

    Args:
        request_id: Numeric Concurrent Request ID (e.g., 10124).

    Returns:
        Dictionary containing Request ID, Program Name, Phase, Status, Phase Code, Status Code,
        Requested Start Date, Actual Start Date, Completion Date, and Completion Text.
    """
    clean_req_id = sanitize_integer(request_id, param_name="request_id", allow_none=False)
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Query detailed request record
            cursor.execute(STATUS_QUERY, {"request_id": clean_req_id})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "request_id": clean_req_id,
                    "message": f"Concurrent request #{clean_req_id} was not found in Oracle EBS.",
                }

            cols = [col[0].lower() for col in cursor.description]
            req_data = dict(zip(cols, row))

            # 2. Call FND_CONCURRENT.GET_REQUEST_STATUS API for real-time developer status
            api_plsql = """
            DECLARE
                l_phase VARCHAR2(80);
                l_status VARCHAR2(80);
                l_dev_phase VARCHAR2(80);
                l_dev_status VARCHAR2(80);
                l_message VARCHAR2(4000);
                l_ret BOOLEAN;
            BEGIN
                l_ret := FND_CONCURRENT.GET_REQUEST_STATUS(
                    request_id     => :request_id,
                    appl_shortname => NULL,
                    program        => NULL,
                    phase          => l_phase,
                    status         => l_status,
                    dev_phase      => l_dev_phase,
                    dev_status     => l_dev_status,
                    message        => l_message
                );
                :out_phase := l_phase;
                :out_status := l_status;
                :out_dev_phase := l_dev_phase;
                :out_dev_status := l_dev_status;
                :out_message := l_message;
            END;
            """
            out_phase = cursor.var(str)
            out_status = cursor.var(str)
            out_dev_phase = cursor.var(str)
            out_dev_status = cursor.var(str)
            out_message = cursor.var(str)

            cursor.execute(
                api_plsql,
                {
                    "request_id": clean_req_id,
                    "out_phase": out_phase,
                    "out_status": out_status,
                    "out_dev_phase": out_dev_phase,
                    "out_dev_status": out_dev_status,
                    "out_message": out_message,
                },
            )

            dev_phase = out_dev_phase.getvalue() or req_data.get("phase_code")
            dev_status = out_dev_status.getvalue() or req_data.get("status_code")
            api_msg = out_message.getvalue()

            return {
                "status": "success",
                "request_id": clean_req_id,
                "program_name": req_data.get("program_name") or req_data.get("concurrent_program_name"),
                "program_short_name": req_data.get("concurrent_program_name"),
                "phase": req_data.get("phase"),
                "request_status": req_data.get("status"),
                "request_status_name": req_data.get("status"),
                "phase_code": req_data.get("phase_code"),
                "status_code": req_data.get("status_code"),
                "developer_phase": dev_phase,
                "developer_status": dev_status,
                "requested_start_date": req_data.get("requested_start_date"),
                "actual_start_date": req_data.get("actual_start_date"),
                "completion_date": req_data.get("completion_date"),
                "duration_minutes": req_data.get("duration_minutes"),
                "completion_text": req_data.get("completion_text") or api_msg,
                "requested_by": req_data.get("requested_by"),
                "responsibility": req_data.get("responsibility_name"),
                "parameters": req_data.get("parameters"),
            }
