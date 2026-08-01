import unittest
from pathlib import Path

from stepmania_song_validator.checks.duplicates import check_duplicates

FIXTURES = Path(__file__).parent / "fixtures"


class TestDuplicates(unittest.TestCase):
    def test_detects_duplicate_pair(self):
        group_a = FIXTURES / "valid_library" / "GroupA"
        song_dirs = [
            group_a / "GoodSong",
            group_a / "DuplicateSong1",
            group_a / "DuplicateSong2",
        ]
        findings = check_duplicates(song_dirs)
        codes = {f.code for f in findings}
        self.assertIn("duplicate_audio_hash", codes)
        self.assertIn("duplicate_fingerprint", codes)

        flagged_paths = {f.path for f in findings}
        self.assertIn(group_a / "DuplicateSong1", flagged_paths)
        self.assertIn(group_a / "DuplicateSong2", flagged_paths)
        self.assertNotIn(group_a / "GoodSong", flagged_paths)

    def test_no_duplicates_among_distinct_songs(self):
        group_a = FIXTURES / "valid_library" / "GroupA"
        findings = check_duplicates([group_a / "GoodSong"])
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
