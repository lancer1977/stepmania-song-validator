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

    def test_three_row_measure_is_engine_supported(self):
        song_dir = FIXTURES / "valid_library" / "GroupA" / "ThreeRowMeasure"
        findings, _ = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertEqual(findings, [])

    def test_supported_subdivision_measures_validate(self):
        song_dir = FIXTURES / "valid_library" / "GroupA" / "Subdivisions"
        findings, charts_scanned = check_song_folder(song_dir)
        self.assertEqual(findings, [])
        self.assertEqual(charts_scanned, 1)

    def test_ssc_chart_music_and_timing_are_checked_per_chart(self):
        song_dir = FIXTURES / "valid_library" / "GroupA" / "SscCharts"
        findings, charts_scanned = check_song_folder(song_dir)
        self.assertEqual(charts_scanned, 2)
        self.assertEqual(
            [f.code for f in findings], ["unsupported_timing_feature"]
        )
        self.assertEqual(findings[0].severity.value, "warning")
        self.assertIn("DELAYS", findings[0].message)

    def test_ssc_invalid_symbol_missing_music_and_bad_timing_fail(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "BadSscStructure"
        findings, charts_scanned = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertEqual(charts_scanned, 1)
        self.assertIn("invalid_note_characters", codes)
        self.assertIn("missing_music_file", codes)
        self.assertIn("malformed_bpms", codes)
        self.assertIn("malformed_offset", codes)

    def test_unparseable_chart_flagged(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "UnparseableChart"
        findings, charts_scanned = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("unparseable_simfile", codes)
        self.assertEqual(charts_scanned, 0)


if __name__ == "__main__":
    unittest.main()
