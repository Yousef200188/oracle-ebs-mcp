"""
Unit tests for concurrent processing tools with mocked database.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.tools.concurrent_submit import (
    list_allowed_concurrent_programs_tool,
    submit_concurrent_request_tool,
)
from src.tools.concurrent_status import get_concurrent_request_status_tool
from src.tools.concurrent_wait import wait_for_concurrent_request_tool
from src.tools.concurrent_output import get_concurrent_request_log_tool
from src.security import SecurityViolationError, InputValidationError


class TestConcurrentTools(unittest.TestCase):

    @patch("src.tools.concurrent_submit.get_connection")
    def test_list_allowed_concurrent_programs(self, mock_get_conn):
        """Verify list_allowed_concurrent_programs returns allowed programs."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.description = [
            ("short_name",),
            ("program",),
            ("application",),
            ("application_short_name",),
            ("description",),
        ]
        mock_cursor.fetchall.return_value = [
            ("PERRPPSM", "Worker Summary Report", "Human Resources", "PER", "Worker report"),
            ("PERRPRAA", "Absences Report", "Human Resources", "PER", "Absences list"),
        ]

        progs = list_allowed_concurrent_programs_tool()
        self.assertIsInstance(progs, list)
        self.assertGreaterEqual(len(progs), 2)
        short_names = [p["short_name"] for p in progs]
        self.assertIn("PERRPPSM", short_names)

    @patch("src.tools.concurrent_submit.initialize_ebs_context")
    @patch("src.tools.concurrent_submit.get_connection")
    def test_submit_concurrent_request_success(self, mock_get_conn, mock_init_ctx):
        """Verify submit_concurrent_request validates allowlist and submits successfully."""
        mock_init_ctx.return_value = {"responsibility_name": "Global HRMS Manager"}

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock program lookup row: (appl_short, user_prog_name)
        mock_cursor.fetchone.return_value = ("PER", "Worker Summary Report")

        # Mock PL/SQL out variables
        out_req_id = MagicMock()
        out_req_id.getvalue.return_value = 10125
        out_status = MagicMock()
        out_status.getvalue.return_value = "PENDING"
        out_msg = MagicMock()
        out_msg.getvalue.return_value = "Submitted successfully."

        mock_cursor.var.side_effect = [out_req_id, out_status, out_msg]

        res = submit_concurrent_request_tool(
            program_short_name="PERRPPSM",
            parameters=["8043", "Y"],
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["request_id"], 10125)
        self.assertEqual(res["responsibility"], "Global HRMS Manager")
        self.assertIn("10125", res["message"])

    def test_submit_concurrent_request_rejects_unauthorized_prog(self):
        """Submitting an unallowed program must raise SecurityViolationError."""
        with self.assertRaises(SecurityViolationError):
            submit_concurrent_request_tool(program_short_name="UNAPPROVED_CUSTOM_PROG")

    @patch("src.tools.concurrent_status.get_connection")
    def test_get_concurrent_request_status(self, mock_get_conn):
        """Verify get_concurrent_request_status returns complete status metrics."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock SELECT row
        mock_cursor.description = [
            ("request_id",),
            ("concurrent_program_name",),
            ("program_name",),
            ("phase_code",),
            ("phase",),
            ("status_code",),
            ("status",),
            ("requested_by",),
            ("responsibility_name",),
            ("parameters",),
            ("requested_start_date",),
            ("actual_start_date",),
            ("completion_date",),
            ("duration_minutes",),
            ("completion_text",),
            ("logfile_name",),
            ("outfile_name",),
        ]
        mock_cursor.fetchone.return_value = (
            10125,
            "PERRPPSM",
            "Worker Summary Report",
            "C",
            "Completed",
            "C",
            "Normal",
            "SYSADMIN",
            "Global HRMS Manager",
            "8043, Y",
            "2026-09-14 15:00:00",
            "2026-09-14 15:00:02",
            "2026-09-14 15:00:45",
            0.72,
            "Program completed successfully.",
            "/log/l10125.req",
            "/out/o10125.out",
        )

        # Mock PL/SQL API vars
        v_phase = MagicMock()
        v_phase.getvalue.return_value = "Completed"
        v_status = MagicMock()
        v_status.getvalue.return_value = "Normal"
        v_dev_phase = MagicMock()
        v_dev_phase.getvalue.return_value = "COMPLETE"
        v_dev_status = MagicMock()
        v_dev_status.getvalue.return_value = "NORMAL"
        v_msg = MagicMock()
        v_msg.getvalue.return_value = "Normal completion"

        mock_cursor.var.side_effect = [v_phase, v_status, v_dev_phase, v_dev_status, v_msg]

        res = get_concurrent_request_status_tool(request_id=10125)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["request_id"], 10125)
        self.assertEqual(res["phase"], "Completed")
        self.assertEqual(res["request_status"], "Normal")
        self.assertEqual(res["developer_phase"], "COMPLETE")

    @patch("src.tools.concurrent_wait.get_concurrent_request_status_tool")
    def test_wait_for_concurrent_request_completes(self, mock_get_status):
        """Verify wait_for_concurrent_request detects completion and terminal state."""
        mock_get_status.side_effect = [
            # First poll: Running
            {
                "status": "success",
                "request_id": 10125,
                "phase_code": "R",
                "status_code": "R",
                "phase": "Running",
                "request_status": "Normal",
                "program_name": "Worker Summary Report",
                "completion_text": None,
            },
            # Second poll: Completed Normal
            {
                "status": "success",
                "request_id": 10125,
                "phase_code": "C",
                "status_code": "C",
                "phase": "Completed",
                "request_status": "Normal",
                "program_name": "Worker Summary Report",
                "completion_text": "Completed successfully.",
                "completion_date": "2026-09-14 15:02:00",
            },
        ]

        res = wait_for_concurrent_request_tool(
            request_id=10125,
            poll_interval_seconds=1,
            timeout_seconds=10,
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["terminal_state"], "COMPLETED_NORMAL")
        self.assertTrue(res["is_completed"])
        self.assertEqual(res["attempts"], 2)

    @patch("src.tools.concurrent_output.get_connection")
    def test_get_concurrent_request_log_metadata(self, mock_get_conn):
        """Verify get_concurrent_request_log returns sanitized log metadata."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = (
            10125,
            "Worker Summary Report",
            "C",
            "C",
            "Program completed successfully with 0 errors.",
            "/u01/logs/l10125.req",
            "/u01/out/o10125.out",
        )

        res = get_concurrent_request_log_tool(request_id=10125, file_type="log")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["request_id"], 10125)
        self.assertEqual(res["file_type"], "log")
        self.assertGreater(len(res["lines"]), 0)


if __name__ == "__main__":
    unittest.main()
