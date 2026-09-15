"""
Tool: get_concurrent_request_log
Retrieves log or output text for an Oracle EBS concurrent request without exposing secrets.
"""

import os
import re
from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection, DatabaseError
from ..security import sanitize_integer, mask_secrets, InputValidationError


LOG_INFO_QUERY = """
SELECT 
    fcr.request_id,
    fcp.user_concurrent_program_name AS program_name,
    fcr.phase_code,
    fcr.status_code,
    fcr.completion_text,
    fcr.logfile_name,
    fcr.outfile_name
FROM 
    apps.fnd_concurrent_requests fcr
    LEFT JOIN apps.fnd_concurrent_programs_vl fcp 
        ON fcr.concurrent_program_id = fcp.concurrent_program_id
        AND fcr.program_application_id = fcp.application_id
WHERE 
    fcr.request_id = :request_id
"""


def sanitize_log_content(text: str) -> str:
    """Mask any passwords, session tokens, or sensitive connection strings in log text."""
    # Mask passwords
    text = mask_secrets(text)
    # Mask potential bearer/session tokens
    text = re.sub(r"(token[\s:=]+)[A-Za-z0-9_\-\.]{15,}", r"\1******", text, flags=re.IGNORECASE)
    return text


def get_concurrent_request_log_tool(
    request_id: int,
    file_type: str = "log",
    max_lines: int = 100,
) -> Dict[str, Any]:
    """
    Retrieve log or output text for an Oracle EBS Concurrent Request.

    Args:
        request_id: Concurrent Request ID.
        file_type: Either 'log' for execution log or 'out' for report output (default: 'log').
        max_lines: Maximum lines to retrieve from the file (default: 100, max: 500).

    Returns:
        Structured dictionary with sanitized log lines, file metadata, and completion status.
    """
    clean_req_id = sanitize_integer(request_id, param_name="request_id", allow_none=False)
    file_type_clean = str(file_type).strip().lower()
    if file_type_clean not in ("log", "out"):
        raise InputValidationError("Parameter 'file_type' must be either 'log' or 'out'.")

    limit_lines = max(1, min(int(max_lines), 500))
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            cursor.execute(LOG_INFO_QUERY, {"request_id": clean_req_id})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "request_id": clean_req_id,
                    "message": f"Concurrent request #{clean_req_id} was not found in Oracle EBS.",
                }

            _, prog_name, phase_code, status_code, comp_text, log_path, out_path = row
            target_path = log_path if file_type_clean == "log" else out_path

            # If the database server filesystem is directly accessible locally or via mount
            content_lines: List[str] = []
            file_found = False

            if target_path and os.path.exists(target_path) and os.path.isfile(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_lines = f.readlines()
                        file_found = True
                        # Take tail of log if too long
                        if len(raw_lines) > limit_lines:
                            raw_lines = raw_lines[-limit_lines:]
                        content_lines = [sanitize_log_content(line.rstrip("\r\n")) for line in raw_lines]
                except Exception as e:
                    content_lines = [f"[Notice: Unable to read file directly from OS: {e}]"]
            else:
                # If OS file is not directly mounted on this client host, return the completion text
                # and diagnostic metadata recorded in the EBS database tables
                fallback_msg = comp_text or "No execution errors logged in database completion text."
                content_lines = [
                    f"Program: {prog_name}",
                    f"Phase: {phase_code}, Status: {status_code}",
                    f"Remote File Path: {target_path or 'Not generated'}",
                    f"Completion Summary: {fallback_msg}",
                ]

            return {
                "status": "success",
                "request_id": clean_req_id,
                "file_type": file_type_clean,
                "file_path": target_path,
                "file_accessible_on_host": file_found,
                "line_count": len(content_lines),
                "completion_text": comp_text,
                "lines": content_lines,
            }
