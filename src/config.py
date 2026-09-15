"""
Configuration module for Oracle EBS Concurrent Request MCP Server.
Manages database connection and EBS context settings (User, Global HRMS Manager, Allowlist).
"""

import os
from pathlib import Path
from typing import Any, List, Optional


def load_dotenv(dotenv_path: Optional[Path] = None) -> None:
    """Lightweight .env loader without hard external dependencies."""
    env_file = dotenv_path or (Path(__file__).parent.parent / ".env")
    if not env_file.exists():
        return

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


load_dotenv()


_UNSET = object()


class OracleEBSConfig:
    """Validated configuration for Oracle EBS MCP Server."""

    def __init__(
        self,
        ORACLE_HOST: Any = _UNSET,
        ORACLE_PORT: Any = _UNSET,
        ORACLE_SERVICE: Any = _UNSET,
        ORACLE_USER: Any = _UNSET,
        ORACLE_PASSWORD: Any = _UNSET,
        EBS_USER_ID: Any = _UNSET,
        EBS_USERNAME: Any = _UNSET,
        EBS_RESPONSIBILITY_ID: Any = _UNSET,
        EBS_RESPONSIBILITY_APPL_ID: Any = _UNSET,
        EBS_RESPONSIBILITY_NAME: Any = _UNSET,
        ALLOWED_CONCURRENT_PROGRAMS: Any = _UNSET,
        ORACLE_POOL_MIN: Any = _UNSET,
        ORACLE_POOL_MAX: Any = _UNSET,
        QUERY_TIMEOUT_SECONDS: Any = _UNSET,
        POLL_INTERVAL_SECONDS: Any = _UNSET,
        POLL_TIMEOUT_SECONDS: Any = _UNSET,
        LOG_LEVEL: Any = _UNSET,
        **kwargs: Any,
    ):
        # Database Connection
        self.oracle_host = ORACLE_HOST if ORACLE_HOST is not _UNSET else os.getenv("ORACLE_HOST", "10.100.100.104")
        raw_port = ORACLE_PORT if ORACLE_PORT is not _UNSET else os.getenv("ORACLE_PORT", "1532")
        try:
            self.oracle_port = int(raw_port)
            if not (1 <= self.oracle_port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
        except ValueError as e:
            raise ValueError(f"Invalid ORACLE_PORT: {raw_port}") from e

        self.oracle_service = ORACLE_SERVICE if ORACLE_SERVICE is not _UNSET else os.getenv("ORACLE_SERVICE", "HRVIS")
        self.oracle_user = ORACLE_USER if ORACLE_USER is not _UNSET else os.getenv("ORACLE_USER", "apps")
        self.oracle_password = (
            ORACLE_PASSWORD if ORACLE_PASSWORD is not _UNSET else os.getenv("ORACLE_PASSWORD", "apps")
        )

        # EBS Context: User
        if EBS_USER_ID is not _UNSET:
            raw_user_id = EBS_USER_ID
        else:
            raw_user_id = os.getenv("EBS_USER_ID")
        self.ebs_user_id: Optional[int] = (
            int(raw_user_id) if raw_user_id is not None and str(raw_user_id).strip().isdigit() else None
        )
        self.ebs_username: str = (
            EBS_USERNAME if EBS_USERNAME is not _UNSET else os.getenv("EBS_USERNAME", "SYSADMIN")
        )

        # EBS Context: Responsibility
        if EBS_RESPONSIBILITY_ID is not _UNSET:
            raw_resp_id = EBS_RESPONSIBILITY_ID
        else:
            raw_resp_id = os.getenv("EBS_RESPONSIBILITY_ID")
        self.ebs_responsibility_id: Optional[int] = (
            int(raw_resp_id) if raw_resp_id is not None and str(raw_resp_id).strip().isdigit() else None
        )

        if EBS_RESPONSIBILITY_APPL_ID is not _UNSET:
            raw_appl_id = EBS_RESPONSIBILITY_APPL_ID
        else:
            raw_appl_id = os.getenv("EBS_RESPONSIBILITY_APPL_ID")
        self.ebs_responsibility_appl_id: Optional[int] = (
            int(raw_appl_id) if raw_appl_id is not None and str(raw_appl_id).strip().isdigit() else None
        )

        self.ebs_responsibility_name: str = (
            EBS_RESPONSIBILITY_NAME
            if EBS_RESPONSIBILITY_NAME is not _UNSET
            else os.getenv("EBS_RESPONSIBILITY_NAME", "Global HRMS Manager")
        )

        # Allowlist of Concurrent Programs
        if ALLOWED_CONCURRENT_PROGRAMS is not _UNSET:
            raw_allowed = ALLOWED_CONCURRENT_PROGRAMS
        elif "APPROVED_PROGRAMS" in kwargs:
            raw_allowed = kwargs["APPROVED_PROGRAMS"]
        else:
            raw_allowed = os.getenv("ALLOWED_CONCURRENT_PROGRAMS") or os.getenv("APPROVED_PROGRAMS")

        self.allowed_concurrent_programs = raw_allowed or (
            "PERRPPSM,PERRPRAA,PERRPRAS,PERRPRBD,PERRPRMS,XX_EMPLOYEE_REPORT,XX_ABSENCE_REPORT,FNDCPPRT"
        )

        # Pool & Polling
        raw_pool_min = ORACLE_POOL_MIN if ORACLE_POOL_MIN is not _UNSET else os.getenv("ORACLE_POOL_MIN", "1")
        self.oracle_pool_min = int(raw_pool_min)
        raw_pool_max = ORACLE_POOL_MAX if ORACLE_POOL_MAX is not _UNSET else os.getenv("ORACLE_POOL_MAX", "5")
        self.oracle_pool_max = int(raw_pool_max)
        self.oracle_pool_increment = int(kwargs.get("ORACLE_POOL_INCREMENT") or os.getenv("ORACLE_POOL_INCREMENT", "1"))

        raw_q_timeout = (
            QUERY_TIMEOUT_SECONDS if QUERY_TIMEOUT_SECONDS is not _UNSET else os.getenv("QUERY_TIMEOUT_SECONDS", "30")
        )
        self.query_timeout_seconds = int(raw_q_timeout)

        raw_poll_int = (
            POLL_INTERVAL_SECONDS if POLL_INTERVAL_SECONDS is not _UNSET else os.getenv("POLL_INTERVAL_SECONDS", "5")
        )
        self.poll_interval_seconds = int(raw_poll_int)

        raw_poll_to = (
            POLL_TIMEOUT_SECONDS if POLL_TIMEOUT_SECONDS is not _UNSET else os.getenv("POLL_TIMEOUT_SECONDS", "180")
        )
        self.poll_timeout_seconds = int(raw_poll_to)

        self.log_level = LOG_LEVEL if LOG_LEVEL is not _UNSET else os.getenv("LOG_LEVEL", "INFO")

        # Compatibility fields
        raw_max_rows = kwargs.get("MAX_QUERY_ROWS") or os.getenv("MAX_QUERY_ROWS", "500")
        self.max_query_rows = int(raw_max_rows)

    @property
    def allowed_programs_list(self) -> List[str]:
        """Return list of allowed concurrent program short names in uppercase."""
        return [p.strip().upper() for p in self.allowed_concurrent_programs.split(",") if p.strip()]

    @property
    def approved_programs_list(self) -> List[str]:
        """Backward-compatible alias for allowed_programs_list."""
        return self.allowed_programs_list

    @property
    def dsn(self) -> str:
        """Construct standard Oracle Easy Connect DSN."""
        return f"{self.oracle_host}:{self.oracle_port}/{self.oracle_service}"

    @property
    def safe_dsn(self) -> str:
        """Return DSN with credentials stripped for safe logging."""
        return f"{self.oracle_user}@{self.oracle_host}:{self.oracle_port}/{self.oracle_service}"


_cached_config: Optional[OracleEBSConfig] = None


def get_config() -> OracleEBSConfig:
    """Factory function to return validated configuration singleton."""
    global _cached_config
    if _cached_config is None:
        _cached_config = OracleEBSConfig()
    return _cached_config
