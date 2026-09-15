"""
Tool: submit_concurrent_request and list_allowed_concurrent_programs
Provides safe, allowlisted concurrent request submission under Global HRMS Manager.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection, DatabaseError
from ..ebs_context import initialize_ebs_context
from ..security import (
    validate_program_allowlist,
    sanitize_parameter,
    SecurityViolationError,
    InputValidationError,
)


def list_allowed_concurrent_programs_tool() -> List[Dict[str, Any]]:
    """
    Return list of allowed Concurrent Programs with program details and application names.
    Only programs defined in the ALLOWED_CONCURRENT_PROGRAMS allowlist can be executed.
    """
    cfg = get_config()
    allowed_names = cfg.allowed_programs_list
    if not allowed_names:
        return []

    query = """
    SELECT 
        fcp.concurrent_program_name AS short_name,
        fcp.user_concurrent_program_name AS program,
        fa.application_name AS application,
        fa.application_short_name AS application_short_name,
        fcp.description
    FROM 
        apps.fnd_concurrent_programs_vl fcp
        INNER JOIN apps.fnd_application_vl fa 
            ON fcp.application_id = fa.application_id
    WHERE 
        fcp.enabled_flag = 'Y'
        AND fcp.concurrent_program_name IN ({placeholders})
    ORDER BY fcp.concurrent_program_name
    """.format(placeholders=",".join([f"'{name}'" for name in allowed_names]))

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            cols = [col[0].lower() for col in cursor.description]
            records = []
            found_short_names = set()
            for row in cursor.fetchall():
                rec = dict(zip(cols, row))
                records.append({
                    "program": rec.get("program"),
                    "short_name": rec.get("short_name"),
                    "application": rec.get("application"),
                    "application_short_name": rec.get("application_short_name"),
                    "description": rec.get("description") or "",
                })
                found_short_names.add(rec.get("short_name"))

            # Include any allowed custom programs even if not yet created in EBS instance
            for short_name in allowed_names:
                if short_name not in found_short_names:
                    records.append({
                        "program": short_name,
                        "short_name": short_name,
                        "application": "Custom Application",
                        "application_short_name": "XX",
                        "description": "Configured in allowlist",
                    })

            return records


def submit_concurrent_request_tool(
    program_short_name: str,
    parameters: Optional[List[Any]] = None,
    application_short_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit an authorized Oracle EBS concurrent program for execution under Global HRMS Manager.

    Workflow:
    1. Validate program against explicit allowlist.
    2. Sanitize all argument parameters.
    3. Initialize EBS session context (Global HRMS Manager).
    4. Submit Concurrent Request using FND_REQUEST.SUBMIT_REQUEST.
    5. Return generated Request ID.
    """
    cfg = get_config()

    # 1. Enforce Allowlist
    clean_prog = validate_program_allowlist(program_short_name, cfg.allowed_programs_list)

    # 2. Sanitize and pad parameters (Oracle EBS supports up to 100, we support up to 20)
    raw_params = parameters or []
    if len(raw_params) > 20:
        raise InputValidationError("A maximum of 20 parameters can be supplied to a concurrent request.")

    cleaned_params: List[Optional[str]] = [sanitize_parameter(p) for p in raw_params]
    # Pad to 20 elements
    padded_params = cleaned_params + [None] * (20 - len(cleaned_params))

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 3. Resolve Application Short Name if omitted
            appl_short = application_short_name
            user_program_name = clean_prog
            if not appl_short:
                lookup_sql = """
                SELECT fa.application_short_name, fcp.user_concurrent_program_name
                FROM apps.fnd_concurrent_programs_vl fcp
                JOIN apps.fnd_application fa ON fcp.application_id = fa.application_id
                WHERE fcp.concurrent_program_name = :prog
                """
                cursor.execute(lookup_sql, {"prog": clean_prog})
                row = cursor.fetchone()
                if row:
                    appl_short = row[0]
                    user_program_name = row[1]
                else:
                    appl_short = "PER"  # Default to Human Resources

            # 4. Initialize EBS Apps Context under Global HRMS Manager
            ctx = initialize_ebs_context(cursor, cfg)

            # 5. Execute FND_REQUEST.SUBMIT_REQUEST via PL/SQL
            submit_plsql = """
            DECLARE
                l_req_id NUMBER;
                l_err_msg VARCHAR2(4000);
            BEGIN
                l_req_id := FND_REQUEST.SUBMIT_REQUEST(
                    application => :appl_short,
                    program     => :prog_short,
                    sub_request => FALSE,
                    argument1   => :arg1,
                    argument2   => :arg2,
                    argument3   => :arg3,
                    argument4   => :arg4,
                    argument5   => :arg5,
                    argument6   => :arg6,
                    argument7   => :arg7,
                    argument8   => :arg8,
                    argument9   => :arg9,
                    argument10  => :arg10,
                    argument11  => :arg11,
                    argument12  => :arg12,
                    argument13  => :arg13,
                    argument14  => :arg14,
                    argument15  => :arg15,
                    argument16  => :arg16,
                    argument17  => :arg17,
                    argument18  => :arg18,
                    argument19  => :arg19,
                    argument20  => :arg20
                );

                IF l_req_id > 0 THEN
                    COMMIT;
                    :out_req_id := l_req_id;
                    :out_status := 'PENDING';
                    :out_message := 'Concurrent Request submitted successfully.';
                ELSE
                    FND_MESSAGE.RETRIEVE;
                    l_err_msg := FND_MESSAGE.GET;
                    :out_req_id := 0;
                    :out_status := 'FAILED';
                    :out_message := NVL(l_err_msg, 'FND_REQUEST.SUBMIT_REQUEST returned 0.');
                    ROLLBACK;
                END IF;
            EXCEPTION
                WHEN OTHERS THEN
                    :out_req_id := 0;
                    :out_status := 'ERROR';
                    :out_message := 'PL/SQL Exception: ' || SQLERRM;
                    ROLLBACK;
            END;
            """

            out_req_id = cursor.var(int)
            out_status = cursor.var(str)
            out_message = cursor.var(str)

            binds = {
                "appl_short": appl_short,
                "prog_short": clean_prog,
                "out_req_id": out_req_id,
                "out_status": out_status,
                "out_message": out_message,
            }
            for i in range(1, 21):
                binds[f"arg{i}"] = padded_params[i - 1]

            cursor.execute(submit_plsql, binds)

            req_id_val = out_req_id.getvalue()
            status_val = out_status.getvalue()
            msg_val = out_message.getvalue()

            if req_id_val and req_id_val > 0:
                return {
                    "status": "success",
                    "request_id": req_id_val,
                    "program": user_program_name,
                    "short_name": clean_prog,
                    "application": appl_short,
                    "responsibility": ctx["responsibility_name"],
                    "parameters": [p for p in cleaned_params if p is not None],
                    "phase": "Pending",
                    "request_status": "Normal",
                    "message": f"Concurrent Request submitted successfully. Request ID: {req_id_val}",
                }
            else:
                return {
                    "status": "error",
                    "request_id": None,
                    "program": clean_prog,
                    "message": msg_val or "Submission failed in Oracle EBS.",
                }
