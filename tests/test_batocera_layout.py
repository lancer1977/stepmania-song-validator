import unittest
from pathlib import Path

from stepmania_song_validator.checks.batocera_layout import check_library_layout

FIXTURES = Path(__file__).parent / "fixtures"


class TestBatoceraLayout(unittest.TestCase):
    def test_valid_library_has_no_layout_findings(self):
        findings, valid_song_dirs = check_library_layout(FIXTURES / "valid_library")
        self.assertEqual(findings, [])
        self.assertEqual(len(valid_song_dirs), 3)

    def test_flat_song_no_group_flagged(self):
        findings, _ = check_library_layout(FIXTURES / "broken_library")
        codes = [f.code for f in findings]
        self.assertIn("song_missing_group_folder", codes)

    def test_risky_filename_flagged(self):
        findings, _ = check_library_layout(FIXTURES / "broken_library")
        codes = [f.code for f in findings]
        self.assertIn("risky_filename_characters", codes)

    def test_missing_library_root(self):
        findings, valid_song_dirs = check_library_layout(FIXTURES / "does_not_exist")
        codes = [f.code for f in findings]
        self.assertIn("library_root_missing", codes)
        self.assertEqual(valid_song_dirs, [])


if __name__ == "__main__":
    unittest.main()
