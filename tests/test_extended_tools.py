"""
Unit tests for extended Oracle EBS Technical Assistant tools with mocked database.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.tools.ebs_concurrent_admin import (
    get_concurrent_program_definition_tool,
    generate_concurrent_program_script_tool,
)
from src.tools.ebs_bip import (
    get_bip_template_info_tool,
    generate_bip_registration_script_tool,
)
from src.tools.ebs_workflow import (
    get_workflow_status_tool,
    get_workflow_notifications_tool,
)
from src.tools.ebs_security_admin import (
    get_responsibility_details_tool,
    get_user_access_tool,
)
from src.tools.ebs_diagnostics import (
    diagnose_concurrent_request_tool,
    get_profile_option_value_tool,
)
from src.tools.ebs_personalization import (
    get_form_personalizations_tool,
    get_oaf_personalizations_tool,
)
from src.tools.ebs_alerts import get_alert_details_tool


class TestExtendedTools(unittest.TestCase):

    @patch("src.tools.ebs_concurrent_admin.get_connection")
    def test_get_concurrent_program_definition(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.description = [
            ("concurrent_program_id",),
            ("short_name",),
            ("program_name",),
            ("application_short_name",),
            ("application_name",),
            ("description",),
            ("enabled_flag",),
            ("srs_flag",),
            ("output_file_type",),
            ("save_output_flag",),
            ("print_flag",),
            ("executable_name",),
            ("execution_method_code",),
            ("execution_method",),
            ("execution_file_name",),
            ("execution_file_path",),
        ]
        mock_cursor.fetchone.return_value = (
            101, "PERRPPSM", "Worker Summary Report", "PER", "Human Resources",
            "Report", "Y", "Y", "TEXT", "Y", "N", "PERRPPSM", "P", "Oracle Reports", "PERRPPSM", None
        )
        mock_cursor.fetchall.side_effect = [
            # Parameters
            [(10, "P_ORG_ID", "Organization", "P_ORG_ID", "HR_ORGANIZATIONS", None, None, "N", "Y", "Y", "Org")],
            # Request Groups
            [("Human Resources Reports", "PER", "Global HRMS Manager")],
        ]

        res = get_concurrent_program_definition_tool("PERRPPSM")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["program"]["short_name"], "PERRPPSM")
        self.assertEqual(res["parameters_count"], 1)

    def test_generate_concurrent_program_script(self):
        res = generate_concurrent_program_script_tool(
            program_name="Custom Employee Report",
            program_short_name="XX_EMP_REP",
            application_short_name="PER",
            executable_name="XX_EMP_REP_EXEC",
            execution_method="PL/SQL Stored Procedure",
            execution_file_name="xx_emp_pkg.run_report",
            parameters=[{"name": "P_ORG_ID", "value_set": "HR_ORGANIZATIONS", "required": True}],
            request_group_name="Human Resources Reports",
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("fnd_program.executable", res["script"])
        self.assertIn("fnd_program.register", res["script"])
        self.assertIn("fnd_program.parameter", res["script"])
        self.assertIn("fnd_program.add_to_group", res["script"])

    @patch("src.tools.ebs_bip.get_connection")
    def test_get_bip_template_info(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.description = [
            ("application_short_name",),
            ("template_code",),
            ("template_name",),
            ("data_source_code",),
            ("template_type_code",),
            ("default_output_type",),
            ("start_date",),
            ("end_date",),
            ("description",),
        ]
        mock_cursor.fetchone.return_value = (
            "PER", "XEMP", "MY FIRST REPORT", "XEMP", "RTF", "EXCEL", "2026-01-01", None, "Desc"
        )
        mock_cursor.fetchall.return_value = [
            ("TEMPLATE_SOURCE", "XEMP.rtf", "E", "en", "US", "RTF", "SYSADMIN", "2026-09-14")
        ]

        res = get_bip_template_info_tool("XEMP")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["template"]["template_code"], "XEMP")
        self.assertEqual(res["files_count"], 1)

    def test_generate_bip_registration_script(self):
        res = generate_bip_registration_script_tool(
            template_code="XX_EMP_TMPL",
            template_name="Employee Template",
            application_short_name="PER",
            data_source_code="XX_EMP_DS",
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("XDOLoader", res["xdoloader_command"])
        self.assertIn("xdo_templates_b", res["plsql_script"])

    @patch("src.tools.ebs_workflow.get_connection")
    def test_get_workflow_status(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.description = [
            ("item_type",),
            ("item_type_display",),
            ("item_key",),
            ("root_activity",),
            ("begin_date",),
            ("end_date",),
            ("user_key",),
            ("owner_role",),
        ]
        mock_cursor.fetchone.return_value = (
            "HRSSA", "HR Self Service", "1001", "ROOT", "2026-09-14 10:00:00", None, "UK-1001", "SYSADMIN"
        )
        mock_cursor.fetchall.side_effect = [
            [("START", "Start", "COMPLETE", "NULL", None, None, "2026-09-14 10:00:00", None, None, None, None)],
            [(5001, "SYSADMIN", "Please approve absence", "OPEN", "2026-09-14 10:00:00", None)],
        ]

        res = get_workflow_status_tool("HRSSA", "1001")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["workflow_state"], "ACTIVE")
        self.assertEqual(res["notifications_count"], 1)

    @patch("src.tools.ebs_diagnostics.get_connection")
    def test_diagnose_concurrent_request(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        mock_cursor.description = [
            ("request_id",),
            ("concurrent_program_name",),
            ("program_name",),
            ("phase_code",),
            ("phase",),
            ("status_code",),
            ("status",),
            ("parent_request_id",),
            ("manager_name",),
            ("controlling_manager",),
            ("oracle_process_id",),
            ("os_process_id",),
            ("logfile_name",),
            ("outfile_name",),
            ("completion_text",),
            ("request_date",),
            ("actual_start_date",),
            ("completion_date",),
            ("duration_minutes",),
        ]
        mock_cursor.fetchone.return_value = (
            10125, "PERRPPSM", "Worker Summary Report", "C", "Completed", "C", "Normal",
            None, "Standard Manager", 100, "1234", "5678", "/log", "/out", "Completed",
            "2026-09-14 15:00:00", "2026-09-14 15:00:02", "2026-09-14 15:00:45", 0.72
        )

        res = diagnose_concurrent_request_tool(10125)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["health"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
