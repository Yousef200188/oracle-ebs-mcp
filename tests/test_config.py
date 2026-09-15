"""
Unit tests for configuration settings and environment variable parsing.
Compatible with both unittest and pytest.
"""

import unittest
from src.config import OracleEBSConfig


class TestConfig(unittest.TestCase):

    def test_config_parsing(self):
        """Verify that configuration parses valid fields correctly."""
        cfg = OracleEBSConfig(
            ORACLE_HOST="ebs-db.local",
            ORACLE_PORT=1532,
            ORACLE_SERVICE="HRVIS",
            ORACLE_USER="apps",
            ORACLE_PASSWORD="secretpassword",
            MAX_QUERY_ROWS=300,
            QUERY_TIMEOUT_SECONDS=25,
            APPROVED_PROGRAMS="FNDCPPRT, XX_LETTER, FNDSCURS ",
        )

        self.assertEqual(cfg.oracle_host, "ebs-db.local")
        self.assertEqual(cfg.oracle_port, 1532)
        self.assertEqual(cfg.oracle_service, "HRVIS")
        self.assertEqual(cfg.oracle_user, "apps")
        self.assertEqual(cfg.oracle_password, "secretpassword")
        self.assertEqual(cfg.max_query_rows, 300)
        self.assertEqual(cfg.query_timeout_seconds, 25)
        self.assertEqual(cfg.dsn, "ebs-db.local:1532/HRVIS")
        self.assertEqual(cfg.safe_dsn, "apps@ebs-db.local:1532/HRVIS")
        self.assertNotIn("secretpassword", cfg.safe_dsn)
        self.assertEqual(cfg.approved_programs_list, ["FNDCPPRT", "XX_LETTER", "FNDSCURS"])

    def test_ebs_concurrent_config(self):
        """Verify parsing of EBS User, Responsibility, and Concurrent Programs allowlist."""
        cfg = OracleEBSConfig(
            EBS_USER_ID=0,
            EBS_USERNAME="SYSADMIN",
            EBS_RESPONSIBILITY_ID=21514,
            EBS_RESPONSIBILITY_APPL_ID=800,
            EBS_RESPONSIBILITY_NAME="Global HRMS Manager",
            ALLOWED_CONCURRENT_PROGRAMS="PERRPPSM, PERRPRAA, XX_EMPLOYEE_REPORT",
            POLL_INTERVAL_SECONDS=3,
            POLL_TIMEOUT_SECONDS=120,
        )
        self.assertEqual(cfg.ebs_user_id, 0)
        self.assertEqual(cfg.ebs_username, "SYSADMIN")
        self.assertEqual(cfg.ebs_responsibility_id, 21514)
        self.assertEqual(cfg.ebs_responsibility_appl_id, 800)
        self.assertEqual(cfg.ebs_responsibility_name, "Global HRMS Manager")
        self.assertEqual(cfg.allowed_programs_list, ["PERRPPSM", "PERRPRAA", "XX_EMPLOYEE_REPORT"])
        self.assertEqual(cfg.poll_interval_seconds, 3)
        self.assertEqual(cfg.poll_timeout_seconds, 120)

    def test_invalid_port(self):
        """Verify that invalid ports trigger validation error."""
        with self.assertRaises(ValueError):
            OracleEBSConfig(
                ORACLE_HOST="localhost",
                ORACLE_PORT=70000,
                ORACLE_SERVICE="ORCL",
                ORACLE_USER="apps",
                ORACLE_PASSWORD="pwd",
            )


if __name__ == "__main__":
    unittest.main()
