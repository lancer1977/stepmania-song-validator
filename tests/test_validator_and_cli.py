import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from stepmania_song_validator.cli import main
from stepmania_song_validator.validator import validate_library

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidator(unittest.TestCase):
    def test_valid_library_passes(self):
        report = validate_library(FIXTURES / "valid_library")
        self.assertEqual(report.songs_scanned, 3)
        self.assertGreaterEqual(report.charts_scanned, 3)
        # DuplicateSong1/2 still produce warnings, but no errors.
        self.assertEqual(report.error_count, 0)
        self.assertFalse(report.ok is False and report.error_count == 0)

    def test_broken_library_has_errors(self):
        report = validate_library(FIXTURES / "broken_library")
        self.assertFalse(report.ok)
        self.assertGreater(report.error_count, 0)


class TestCli(unittest.TestCase):
    def test_cli_human_output_valid_library(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = main([str(FIXTURES / "valid_library")])
        output = buf.getvalue()
        self.assertIn("stepmania-song-validator report", output)
        self.assertEqual(exit_code, 0)

    def test_cli_json_output_broken_library(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = main([str(FIXTURES / "broken_library"), "--json"])
        output = buf.getvalue()
        self.assertIn('"ok": false', output)
        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
