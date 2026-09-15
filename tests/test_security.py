"""
Unit tests for security, allowlists, and parameter sanitization.
"""

import unittest
from src.security import (
    validate_program_allowlist,
    sanitize_program_name,
    sanitize_parameter,
    sanitize_integer,
    mask_secrets,
    SecurityViolationError,
    InputValidationError,
)


class TestSecurity(unittest.TestCase):

    def test_allowlist_allowed_program(self):
        """Allowed program names should succeed (case-insensitive)."""
        allowed = ["PERRPPSM", "PERRPRAA", "XX_EMPLOYEE_REPORT"]
        self.assertEqual(validate_program_allowlist("PERRPPSM", allowed), "PERRPPSM")
        self.assertEqual(validate_program_allowlist("perrpraa", allowed), "PERRPRAA")
        self.assertEqual(validate_program_allowlist("xx_employee_report", allowed), "XX_EMPLOYEE_REPORT")

    def test_allowlist_rejects_unauthorized_program(self):
        """Unauthorized program names must raise SecurityViolationError."""
        allowed = ["PERRPPSM", "PERRPRAA"]
        with self.assertRaises(SecurityViolationError):
            validate_program_allowlist("UNAUTHORIZED_PROG", allowed)
        with self.assertRaises(SecurityViolationError):
            validate_program_allowlist("DROP_DATABASE", allowed)

    def test_sanitize_program_name_rejection(self):
        """Invalid or malformed program names should be rejected."""
        with self.assertRaises(InputValidationError):
            sanitize_program_name("PROG; DROP TABLE")
        with self.assertRaises(InputValidationError):
            sanitize_program_name("PROG WITH SPACES")
        with self.assertRaises(InputValidationError):
            sanitize_program_name("")

    def test_parameter_sanitization(self):
        """Valid parameters pass, while shell injection characters are blocked."""
        self.assertEqual(sanitize_parameter("1001"), "1001")
        self.assertEqual(sanitize_parameter("Normal Text Parameter"), "Normal Text Parameter")
        self.assertIsNone(sanitize_parameter(None))
        self.assertIsNone(sanitize_parameter("   "))

        # Block shell metacharacters
        with self.assertRaises(InputValidationError):
            sanitize_parameter("1001; rm -rf /")
        with self.assertRaises(InputValidationError):
            sanitize_parameter("arg & echo hacked")
        with self.assertRaises(InputValidationError):
            sanitize_parameter("val | cat /etc/passwd")
        with self.assertRaises(InputValidationError):
            sanitize_parameter("`id`")

    def test_parameter_length_limit(self):
        """Parameters exceeding 240 chars should be rejected."""
        long_param = "A" * 250
        with self.assertRaises(InputValidationError):
            sanitize_parameter(long_param)

    def test_sanitize_integer(self):
        """Valid integer checks."""
        self.assertEqual(sanitize_integer(10124), 10124)
        self.assertEqual(sanitize_integer("10124"), 10124)
        with self.assertRaises(InputValidationError):
            sanitize_integer("abc")
        with self.assertRaises(InputValidationError):
            sanitize_integer(-1)

    def test_mask_secrets(self):
        """Verify sensitive credentials are masked in logs."""
        raw = "Connection failed: password=SuperSecret123, user=apps"
        masked = mask_secrets(raw)
        self.assertNotIn("SuperSecret123", masked)
        self.assertIn("******", masked)


if __name__ == "__main__":
    unittest.main()
