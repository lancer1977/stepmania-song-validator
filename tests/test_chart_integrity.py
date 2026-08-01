import unittest
from pathlib import Path

from stepmania_song_validator.checks.chart_integrity import check_song_folder

FIXTURES = Path(__file__).parent / "fixtures"


class TestChartIntegrity(unittest.TestCase):
    def test_good_song_has_no_findings(self):
        song_dir = FIXTURES / "valid_library" / "GroupA" / "GoodSong"
        findings, charts_scanned = check_song_folder(song_dir)
        self.assertEqual(findings, [])
        self.assertEqual(charts_scanned, 1)

    def test_missing_music_file_flagged(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "BadMusicRef"
        findings, _ = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("missing_music_file", codes)

    def test_malformed_bpms_and_stops_flagged(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "BadBpms"
        findings, _ = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("malformed_bpms", codes)
        self.assertIn("invalid_bpm_value", codes)
        self.assertIn("unsorted_bpms", codes)
        self.assertIn("negative_stop_duration", codes)

    def test_bad_measure_division_flagged(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "BadNotesDivision"
        findings, _ = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("malformed_measure_length", codes)

    def test_unparseable_chart_flagged(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "UnparseableChart"
        findings, charts_scanned = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("unparseable_simfile", codes)
        self.assertEqual(charts_scanned, 0)


if __name__ == "__main__":
    unittest.main()
