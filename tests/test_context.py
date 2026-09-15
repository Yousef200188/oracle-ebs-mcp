"""
Unit tests for Oracle EBS Context resolution and initialization.
"""

import unittest
from unittest.mock import MagicMock
from src.config import OracleEBSConfig
from src.ebs_context import resolve_ebs_ids, initialize_ebs_context, EBSContextError
from src.security import SecurityViolationError


class TestEBSContext(unittest.TestCase):

    def test_resolve_ids_from_config(self):
        """When IDs are provided directly in config, they should be used."""
        cfg = OracleEBSConfig(
            EBS_USER_ID=0,
            EBS_USERNAME="SYSADMIN",
            EBS_RESPONSIBILITY_ID=21514,
            EBS_RESPONSIBILITY_APPL_ID=800,
            EBS_RESPONSIBILITY_NAME="Global HRMS Manager",
        )
        mock_cursor = MagicMock()
        # Mock user-responsibility assignment check (returns count > 0)
        mock_cursor.fetchone.return_value = (1,)

        u_id, r_id, a_id = resolve_ebs_ids(mock_cursor, cfg)
        self.assertEqual(u_id, 0)
        self.assertEqual(r_id, 21514)
        self.assertEqual(a_id, 800)

    def test_resolve_ids_dynamically_from_db(self):
        """When IDs are not provided, query FND_USER and FND_RESPONSIBILITY_VL."""
        cfg = OracleEBSConfig(
            EBS_USER_ID=None,
            EBS_USERNAME="SYSADMIN",
            EBS_RESPONSIBILITY_ID=None,
            EBS_RESPONSIBILITY_APPL_ID=None,
            EBS_RESPONSIBILITY_NAME="Global HRMS Manager",
        )
        mock_cursor = MagicMock()
        # First query: fnd_user -> user_id = 0
        # Second query: fnd_responsibility_vl -> resp_id = 21514, appl_id = 800
        # Third query: fnd_user_resp_groups_all -> count = 1
        mock_cursor.fetchone.side_effect = [
            (0,),
            (21514, 800),
            (1,),
        ]

        u_id, r_id, a_id = resolve_ebs_ids(mock_cursor, cfg)
        self.assertEqual(u_id, 0)
        self.assertEqual(r_id, 21514)
        self.assertEqual(a_id, 800)

    def test_reject_unauthorized_responsibility_assignment(self):
        """If user is not assigned the responsibility in FND_USER_RESP_GROUPS, reject."""
        cfg = OracleEBSConfig(
            EBS_USER_ID=999,
            EBS_USERNAME="TEST_USER",
            EBS_RESPONSIBILITY_ID=21514,
            EBS_RESPONSIBILITY_APPL_ID=800,
            EBS_RESPONSIBILITY_NAME="Global HRMS Manager",
        )
        mock_cursor = MagicMock()
        # Mock assignment check returns 0
        mock_cursor.fetchone.return_value = (0,)

        with self.assertRaises(SecurityViolationError):
            resolve_ebs_ids(mock_cursor, cfg)

    def test_initialize_ebs_context_calls_fnd_global(self):
        """Verify initialize_ebs_context invokes FND_GLOBAL.APPS_INITIALIZE."""
        cfg = OracleEBSConfig(
            EBS_USER_ID=0,
            EBS_USERNAME="SYSADMIN",
            EBS_RESPONSIBILITY_ID=21514,
            EBS_RESPONSIBILITY_APPL_ID=800,
            EBS_RESPONSIBILITY_NAME="Global HRMS Manager",
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        res = initialize_ebs_context(mock_cursor, cfg)
        self.assertEqual(res["status"], "INITIALIZED")
        self.assertEqual(res["user_id"], 0)
        self.assertEqual(res["responsibility_id"], 21514)
        self.assertEqual(res["responsibility_name"], "Global HRMS Manager")


if __name__ == "__main__":
    unittest.main()
