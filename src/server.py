"""
Oracle E-Business Suite (EBS R12) Concurrent Request MCP Server.
Allows an AI assistant to securely submit, monitor, wait, and retrieve logs
for concurrent programs under the 'Global HRMS Manager' responsibility.
"""

import sys
import logging
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from .config import get_config
from .database import DatabaseError, QueryTimeoutError, close_pool
from .ebs_context import EBSContextError
from .security import (
    SecurityViolationError,
    InputValidationError,
    mask_secrets,
)
from .tools import (
    list_allowed_concurrent_programs_tool,
    submit_concurrent_request_tool,
    get_concurrent_request_status_tool,
    wait_for_concurrent_request_tool,
    get_concurrent_request_log_tool,
    get_concurrent_program_definition_tool,
    generate_concurrent_program_script_tool,
    get_bip_template_info_tool,
    generate_bip_registration_script_tool,
    get_workflow_status_tool,
    get_workflow_notifications_tool,
    get_responsibility_details_tool,
    get_user_access_tool,
    diagnose_concurrent_request_tool,
    get_profile_option_value_tool,
    get_form_personalizations_tool,
    get_oaf_personalizations_tool,
    get_alert_details_tool,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("oracle_ebs_concurrent_mcp")

# Initialize FastMCP Server
mcp = FastMCP("oracle-ebs-concurrent-mcp")


def handle_tool_error(e: Exception, tool_name: str) -> Dict[str, Any]:
    """Format safe error messages without exposing database internals or credentials."""
    if isinstance(e, SecurityViolationError):
        logger.warning("[%s] Security violation: %s", tool_name, e)
        return {
            "status": "error",
            "error_type": "SecurityViolation",
            "message": str(e),
        }
    elif isinstance(e, InputValidationError):
        logger.info("[%s] Validation error: %s", tool_name, e)
        return {
            "status": "error",
            "error_type": "ValidationError",
            "message": str(e),
        }
    elif isinstance(e, EBSContextError):
        logger.error("[%s] EBS Context error: %s", tool_name, e)
        return {
            "status": "error",
            "error_type": "EBSContextError",
            "message": str(e),
        }
    elif isinstance(e, QueryTimeoutError):
        logger.error("[%s] Timeout error: %s", tool_name, e)
        return {
            "status": "error",
            "error_type": "TimeoutError",
            "message": str(e),
        }
    elif isinstance(e, DatabaseError):
        safe_msg = mask_secrets(str(e))
        logger.error("[%s] Database error: %s", tool_name, safe_msg)
        return {
            "status": "error",
            "error_type": "DatabaseError",
            "message": safe_msg,
        }
    else:
        safe_msg = mask_secrets(str(e))
        logger.exception("[%s] Unexpected exception: %s", tool_name, safe_msg)
        return {
            "status": "error",
            "error_type": "InternalError",
            "message": f"An error occurred while executing {tool_name}: {safe_msg}",
        }


# ==============================================================================
# Tool 1: list_allowed_concurrent_programs
# ==============================================================================
@mcp.tool()
def list_allowed_concurrent_programs() -> List[Dict[str, Any]]:
    """
    Return the list of Concurrent Programs that the MCP Server is allowed to execute.

    Only programs explicitly configured in the ALLOWED_CONCURRENT_PROGRAMS allowlist
    may be submitted by the AI assistant.
    """
    try:
        return list_allowed_concurrent_programs_tool()
    except Exception as e:
        logger.error("Failed to list allowed programs: %s", e)
        return []


# ==============================================================================
# Tool 2: submit_concurrent_request
# ==============================================================================
@mcp.tool()
def submit_concurrent_request(
    program_short_name: str,
    parameters: Optional[List[Any]] = None,
    application_short_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submit an Oracle EBS Concurrent Request under the 'Global HRMS Manager' responsibility.

    Security & Safety Rules:
    1. Validates program name against the explicit allowlist.
    2. Validates and sanitizes all input parameters.
    3. Dynamically resolves and validates User ID, Responsibility ID, and Application ID.
    4. Initializes EBS application context via FND_GLOBAL.APPS_INITIALIZE.
    5. Submits request via standard Oracle EBS API: FND_REQUEST.SUBMIT_REQUEST.
    6. Returns the generated numeric Request ID.

    Args:
        program_short_name: Concurrent program short name (e.g., "PERRPPSM", "PERRPRAA", "XX_EMPLOYEE_REPORT").
        parameters: Optional ordered list of argument values to pass to the program (up to 20 args).
        application_short_name: Application short name (e.g., "PER", "FND", "XX"). Auto-detected if omitted.
    """
    try:
        return submit_concurrent_request_tool(
            program_short_name=program_short_name,
            parameters=parameters,
            application_short_name=application_short_name,
        )
    except Exception as e:
        return handle_tool_error(e, "submit_concurrent_request")


# ==============================================================================
# Tool 3: get_concurrent_request_status
# ==============================================================================
@mcp.tool()
def get_concurrent_request_status(request_id: int) -> Dict[str, Any]:
    """
    Retrieve real-time execution phase, status, and lifecycle timestamps for a Concurrent Request.

    Utilizes Oracle EBS standard API: FND_CONCURRENT.GET_REQUEST_STATUS and queries
    FND_CONCURRENT_REQUESTS.

    Args:
        request_id: Numeric Concurrent Request ID (e.g., 10124).

    Returns:
        Structured dictionary containing:
        - Request ID
        - Program Name
        - Phase & Phase Code (Pending, Running, Completed)
        - Status & Status Code (Normal, Error, Warning, Cancelled)
        - Requested Start Date, Actual Start Date, Completion Date
        - Duration in minutes
        - Completion Text
    """
    try:
        return get_concurrent_request_status_tool(request_id=request_id)
    except Exception as e:
        return handle_tool_error(e, "get_concurrent_request_status")


# ==============================================================================
# Tool 4: wait_for_concurrent_request
# ==============================================================================
@mcp.tool()
def wait_for_concurrent_request(
    request_id: int,
    poll_interval_seconds: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Poll an Oracle EBS Concurrent Request and wait until it completes or reaches a terminal state.

    Terminal states:
    - COMPLETED_NORMAL
    - ERROR
    - WARNING
    - CANCELLED

    Args:
        request_id: Concurrent Request ID to monitor.
        poll_interval_seconds: Interval between polling checks (default: 5 seconds).
        timeout_seconds: Maximum wait duration before returning timeout (default: 180 seconds).
    """
    try:
        return wait_for_concurrent_request_tool(
            request_id=request_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )
    except Exception as e:
        return handle_tool_error(e, "wait_for_concurrent_request")


# ==============================================================================
# Tool 5: get_concurrent_request_log
# ==============================================================================
@mcp.tool()
def get_concurrent_request_log(
    request_id: int,
    file_type: str = "log",
    max_lines: int = 100,
) -> Dict[str, Any]:
    """
    Retrieve log or output text for an Oracle EBS Concurrent Request.

    Safeguards:
    - Masks any passwords, tokens, or sensitive connection parameters.
    - Prevents directory traversal.

    Args:
        request_id: Concurrent Request ID.
        file_type: 'log' for execution log file, 'out' for report output file (default: 'log').
        max_lines: Maximum lines of output to return (default: 100).
    """
    try:
        return get_concurrent_request_log_tool(
            request_id=request_id,
            file_type=file_type,
            max_lines=max_lines,
        )
    except Exception as e:
        return handle_tool_error(e, "get_concurrent_request_log")


# ==============================================================================
# Domain 1 & 3 & 4: Concurrent Programs, Executables & Parameters Admin
# ==============================================================================
@mcp.tool()
def get_concurrent_program_definition(program_short_name: str) -> Dict[str, Any]:
    """
    Retrieve full technical metadata for an Oracle EBS Concurrent Program:
    Executable details, execution method, parameters with value sets, and assigned request groups.
    """
    try:
        return get_concurrent_program_definition_tool(program_short_name)
    except Exception as e:
        return handle_tool_error(e, "get_concurrent_program_definition")


@mcp.tool()
def generate_concurrent_program_script(
    program_name: str,
    program_short_name: str,
    application_short_name: str,
    executable_name: str,
    execution_method: str,
    execution_file_name: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    request_group_name: Optional[str] = None,
    output_format: str = "TEXT",
) -> Dict[str, Any]:
    """
    Generate an idempotent, certified PL/SQL registration script using FND_PROGRAM API
    (Executable, Program, Parameters, and Request Group Assignment).
    """
    try:
        return generate_concurrent_program_script_tool(
            program_name=program_name,
            program_short_name=program_short_name,
            application_short_name=application_short_name,
            executable_name=executable_name,
            execution_method=execution_method,
            execution_file_name=execution_file_name,
            parameters=parameters,
            request_group_name=request_group_name,
            output_format=output_format,
        )
    except Exception as e:
        return handle_tool_error(e, "generate_concurrent_program_script")


# ==============================================================================
# Domain 10: BI Publisher / XML Publisher Tools
# ==============================================================================
@mcp.tool()
def get_bip_template_info(template_code: str) -> Dict[str, Any]:
    """
    Inspect an Oracle EBS BI Publisher / XML Publisher template:
    Data Definition, files stored in XDO_LOBS (RTF, XSL, PDF, Excel), languages, and default output type.
    """
    try:
        return get_bip_template_info_tool(template_code)
    except Exception as e:
        return handle_tool_error(e, "get_bip_template_info")


@mcp.tool()
def generate_bip_registration_script(
    template_code: str,
    template_name: str,
    application_short_name: str,
    data_source_code: str,
    template_type: str = "RTF",
    default_output_type: str = "EXCEL",
    rtf_file_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate complete BI Publisher Data Definition and Template registration script,
    including the exact XDOLoader CLI commands for Linux deployment.
    """
    try:
        return generate_bip_registration_script_tool(
            template_code=template_code,
            template_name=template_name,
            application_short_name=application_short_name,
            data_source_code=data_source_code,
            template_type=template_type,
            default_output_type=default_output_type,
            rtf_file_name=rtf_file_name,
        )
    except Exception as e:
        return handle_tool_error(e, "generate_bip_registration_script")


# ==============================================================================
# Domain 8: Oracle Workflow & Approvals Tools
# ==============================================================================
@mcp.tool()
def get_workflow_status(item_type: str, item_key: str) -> Dict[str, Any]:
    """
    Retrieve real-time status, activity execution history, error messages,
    and open notifications for an Oracle Workflow item.
    """
    try:
        return get_workflow_status_tool(item_type, item_key)
    except Exception as e:
        return handle_tool_error(e, "get_workflow_status")


@mcp.tool()
def get_workflow_notifications(
    recipient_role: Optional[str] = None,
    status: str = "OPEN",
) -> Dict[str, Any]:
    """
    Retrieve open or closed workflow notifications/worklist for a user or role.
    """
    try:
        return get_workflow_notifications_tool(recipient_role, status)
    except Exception as e:
        return handle_tool_error(e, "get_workflow_notifications")


# ==============================================================================
# Domain 14: Responsibilities, Menus & Security Tools
# ==============================================================================
@mcp.tool()
def get_responsibility_details(responsibility_name: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive security architecture for an Oracle EBS Responsibility:
    Responsibility ID, Application ID, Attached Root Menu, Request Group, and Data Group.
    """
    try:
        return get_responsibility_details_tool(responsibility_name)
    except Exception as e:
        return handle_tool_error(e, "get_responsibility_details")


@mcp.tool()
def get_user_access(username: str) -> Dict[str, Any]:
    """
    Inspect an Oracle EBS User's active account:
    USER_ID, assigned employee, active responsibilities with validity dates, and account status.
    """
    try:
        return get_user_access_tool(username)
    except Exception as e:
        return handle_tool_error(e, "get_user_access")


# ==============================================================================
# Domain 17: Technical Diagnostics & RCA Tools
# ==============================================================================
@mcp.tool()
def diagnose_concurrent_request(request_id: int) -> Dict[str, Any]:
    """
    Perform deep Root Cause Analysis (RCA) on an Oracle EBS Concurrent Request:
    Manager queue status, execution node, database session SID/Serial, parent/child requests,
    completion text, and error indicators.
    """
    try:
        return diagnose_concurrent_request_tool(request_id)
    except Exception as e:
        return handle_tool_error(e, "diagnose_concurrent_request")


@mcp.tool()
def get_profile_option_value(
    profile_option_name: str,
    level: str = "SITE",
    level_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve profile option values across EBS hierarchy levels (Site, Application, Responsibility, User).
    """
    try:
        return get_profile_option_value_tool(profile_option_name, level, level_value)
    except Exception as e:
        return handle_tool_error(e, "get_profile_option_value")


# ==============================================================================
# Domain 9 & 13: Forms Personalization & OAF Customization Tools
# ==============================================================================
@mcp.tool()
def get_form_personalizations(form_name: str) -> Dict[str, Any]:
    """
    Retrieve active Form Personalizations for an Oracle Forms 10g form:
    Rules, Trigger Events (WHEN-NEW-FORM-INSTANCE, WHEN-VALIDATE-RECORD), conditions, and actions.
    """
    try:
        return get_form_personalizations_tool(form_name)
    except Exception as e:
        return handle_tool_error(e, "get_form_personalizations")


@mcp.tool()
def get_oaf_personalizations(page_path: str) -> Dict[str, Any]:
    """
    Inspect OAF MDS repository for active page personalizations and customizations.
    """
    try:
        return get_oaf_personalizations_tool(page_path)
    except Exception as e:
        return handle_tool_error(e, "get_oaf_personalizations")


# ==============================================================================
# Domain 7: Alerts Inspector Tool
# ==============================================================================
@mcp.tool()
def get_alert_details(alert_name: str) -> Dict[str, Any]:
    """
    Retrieve definition, SQL logic, triggers, and action recipients for an Oracle Alert.
    """
    try:
        return get_alert_details_tool(alert_name)
    except Exception as e:
        return handle_tool_error(e, "get_alert_details")


def main() -> None:
    """Server entry point."""
    try:
        cfg = get_config()
        logger.info("Starting Oracle EBS Concurrent Request MCP Server...")
        logger.info("Target Database: %s", cfg.safe_dsn)
        logger.info("EBS Responsibility Context: %s (User: %s)", cfg.ebs_responsibility_name, cfg.ebs_username)
        logger.info("Allowed Programs Allowlist: %s", cfg.allowed_programs_list)
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
