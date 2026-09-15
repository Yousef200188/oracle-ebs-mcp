"""
Tool: wait_for_concurrent_request
Polls an Oracle EBS concurrent request until it transitions to a terminal state
(COMPLETED, ERROR, WARNING, CANCELLED) or hits a configurable timeout.
"""

import time
import logging
from typing import Any, Dict, Optional
from ..config import get_config
from ..security import sanitize_integer
from .concurrent_status import get_concurrent_request_status_tool

logger = logging.getLogger("oracle_ebs_mcp.concurrent_wait")

TERMINAL_PHASE_CODES = {"C"}  # 'C' = Completed in FND_CONCURRENT_REQUESTS


def wait_for_concurrent_request_tool(
    request_id: int,
    poll_interval_seconds: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Wait for an Oracle EBS Concurrent Request to complete by polling its status.

    Args:
        request_id: Concurrent Request ID.
        poll_interval_seconds: Delay between checks in seconds (default: 5s, min: 2s, max: 60s).
        timeout_seconds: Maximum total wait time in seconds (default: 180s, max: 600s).

    Returns:
        Dictionary containing final lifecycle status, duration, and completion details.
    """
    clean_req_id = sanitize_integer(request_id, param_name="request_id", allow_none=False)
    cfg = get_config()

    interval = poll_interval_seconds or cfg.poll_interval_seconds
    interval = max(2, min(interval, 60))

    timeout = timeout_seconds or cfg.poll_timeout_seconds
    timeout = max(5, min(timeout, 600))

    start_time = time.time()
    logger.info("Polling request #%d (interval=%ds, timeout=%ds)...", clean_req_id, interval, timeout)

    attempts = 0
    last_status_data: Optional[Dict[str, Any]] = None

    while True:
        elapsed = round(time.time() - start_time, 1)
        attempts += 1

        last_status_data = get_concurrent_request_status_tool(request_id=clean_req_id)

        if last_status_data.get("status") == "not_found":
            return {
                "status": "not_found",
                "request_id": clean_req_id,
                "message": f"Concurrent request #{clean_req_id} does not exist in Oracle EBS.",
            }

        phase_code = (last_status_data.get("phase_code") or "").upper()
        status_code = (last_status_data.get("status_code") or "").upper()
        phase_name = last_status_data.get("phase")
        status_name = last_status_data.get("request_status")

        # Check if terminal phase reached ('C' = Completed)
        if phase_code in TERMINAL_PHASE_CODES:
            # Map EBS status codes: 'C' (Normal), 'E' (Error), 'G' (Warning), 'X' (Terminated/Cancelled)
            terminal_status = "COMPLETED"
            if status_code == "E":
                terminal_status = "ERROR"
            elif status_code == "G":
                terminal_status = "WARNING"
            elif status_code in ("X", "D"):
                terminal_status = "CANCELLED"
            elif status_code == "C":
                terminal_status = "COMPLETED_NORMAL"

            logger.info("Request #%d finished with status '%s' after %.1fs", clean_req_id, terminal_status, elapsed)

            return {
                "status": "success",
                "request_id": clean_req_id,
                "terminal_state": terminal_status,
                "phase": phase_name,
                "request_status": status_name,
                "phase_code": phase_code,
                "status_code": status_code,
                "program_name": last_status_data.get("program_name"),
                "completion_text": last_status_data.get("completion_text"),
                "completion_date": last_status_data.get("completion_date"),
                "total_wait_seconds": elapsed,
                "attempts": attempts,
                "is_completed": True,
            }

        if elapsed >= timeout:
            logger.warning("Timed out waiting for request #%d after %.1fs", clean_req_id, elapsed)
            return {
                "status": "timeout",
                "request_id": clean_req_id,
                "terminal_state": "TIMED_OUT",
                "phase": phase_name,
                "request_status": status_name,
                "total_wait_seconds": elapsed,
                "attempts": attempts,
                "is_completed": False,
                "message": f"Request #{clean_req_id} is still running/pending after {timeout} seconds. Current phase: {phase_name}.",
            }

        time.sleep(interval)
