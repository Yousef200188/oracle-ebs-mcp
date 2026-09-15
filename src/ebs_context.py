"""
Oracle EBS Application Context Resolution and Initialization Module.
Properly initializes session security context via FND_GLOBAL.APPS_INITIALIZE
under the 'Global HRMS Manager' responsibility.
"""

import logging
from typing import Any, Dict, Optional, Tuple
from .config import OracleEBSConfig, get_config
from .security import SecurityViolationError, mask_secrets

logger = logging.getLogger("oracle_ebs_mcp.ebs_context")


class EBSContextError(Exception):
    """Raised when EBS context resolution or initialization fails."""
    pass


def resolve_ebs_ids(cursor: Any, config: OracleEBSConfig) -> Tuple[int, int, int]:
    """
    Resolve and validate USER_ID, RESPONSIBILITY_ID, and RESPONSIBILITY_APPLICATION_ID
    from Oracle EBS foundation tables (FND_USER, FND_RESPONSIBILITY_VL).
    
    Returns:
        Tuple of (user_id, responsibility_id, responsibility_application_id)
    """
    # 1. Resolve User ID
    user_id = config.ebs_user_id
    if user_id is None:
        user_sql = """
        SELECT user_id 
        FROM apps.fnd_user 
        WHERE UPPER(user_name) = UPPER(:username)
          AND (end_date IS NULL OR end_date > SYSDATE)
        """
        cursor.execute(user_sql, {"username": config.ebs_username})
        row = cursor.fetchone()
        if not row:
            raise EBSContextError(
                f"Oracle EBS User '{config.ebs_username}' not found or has expired in FND_USER."
            )
        user_id = int(row[0])

    # 2. Resolve Responsibility ID and Application ID
    resp_id = config.ebs_responsibility_id
    resp_appl_id = config.ebs_responsibility_appl_id

    if resp_id is None or resp_appl_id is None:
        resp_sql = """
        SELECT responsibility_id, application_id 
        FROM apps.fnd_responsibility_vl 
        WHERE responsibility_name = :resp_name
          AND (end_date IS NULL OR end_date > SYSDATE)
        """
        cursor.execute(resp_sql, {"resp_name": config.ebs_responsibility_name})
        row = cursor.fetchone()
        if not row:
            raise EBSContextError(
                f"Responsibility '{config.ebs_responsibility_name}' not found or expired in FND_RESPONSIBILITY_VL."
            )
        resp_id = int(row[0])
        resp_appl_id = int(row[1])

    # 3. Security Verification: Ensure User is assigned this Responsibility
    check_assignment_sql = """
    SELECT COUNT(1)
    FROM apps.fnd_user_resp_groups_all urg
    WHERE urg.user_id = :user_id
      AND urg.responsibility_id = :resp_id
      AND urg.responsibility_application_id = :resp_appl_id
      AND (urg.start_date IS NULL OR urg.start_date <= SYSDATE)
      AND (urg.end_date IS NULL OR urg.end_date >= SYSDATE)
    """
    cursor.execute(
        check_assignment_sql,
        {"user_id": user_id, "resp_id": resp_id, "resp_appl_id": resp_appl_id},
    )
    is_assigned = cursor.fetchone()[0] > 0

    if not is_assigned:
        raise SecurityViolationError(
            f"Security Error: User #{user_id} ({config.ebs_username}) is NOT authorized "
            f"for Responsibility #{resp_id} ({config.ebs_responsibility_name}) in FND_USER_RESP_GROUPS."
        )

    return user_id, resp_id, resp_appl_id


def initialize_ebs_context(cursor: Any, config: Optional[OracleEBSConfig] = None) -> Dict[str, Any]:
    """
    Initializes the Oracle EBS session context using FND_GLOBAL.APPS_INITIALIZE.
    Must be called before any FND_REQUEST API call.
    """
    cfg = config or get_config()

    try:
        user_id, resp_id, resp_appl_id = resolve_ebs_ids(cursor, cfg)

        logger.info(
            "Initializing EBS context: User ID=%d (%s), Resp ID=%d (%s), Resp Appl ID=%d",
            user_id,
            cfg.ebs_username,
            resp_id,
            cfg.ebs_responsibility_name,
            resp_appl_id,
        )

        init_plsql = """
        BEGIN
            FND_GLOBAL.APPS_INITIALIZE(
                user_id      => :user_id,
                resp_id      => :resp_id,
                resp_appl_id => :resp_appl_id
            );
        END;
        """
        cursor.execute(
            init_plsql,
            {"user_id": user_id, "resp_id": resp_id, "resp_appl_id": resp_appl_id},
        )

        return {
            "user_id": user_id,
            "username": cfg.ebs_username,
            "responsibility_id": resp_id,
            "responsibility_name": cfg.ebs_responsibility_name,
            "responsibility_appl_id": resp_appl_id,
            "status": "INITIALIZED",
        }
    except Exception as e:
        safe_msg = mask_secrets(str(e))
        logger.error("Failed to initialize EBS context: %s", safe_msg)
        raise EBSContextError(f"EBS context initialization failed: {safe_msg}") from e
