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
        codes = [f.code for f in findings]
        self.assertIn("unsupported_timing_feature", codes)
        self.assertIn("unsupported_note_feature", codes)
        self.assertTrue(all(f.severity.value == "warning" for f in findings))
        self.assertTrue(any("DELAYS" in f.message for f in findings))
        self.assertNotIn("missing_music_tag", codes)
        self.assertNotIn("missing_music_file", codes)

    def test_empty_chart_music_without_song_fallback_is_reported(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "MissingEffectiveMusic"
        findings, _ = check_song_folder(song_dir)
        missing_music = [f for f in findings if f.code == "missing_music_tag"]
        self.assertEqual(len(missing_music), 1)
        self.assertEqual(missing_music[0].severity.value, "warning")

    def test_music_reference_to_directory_is_not_a_music_file(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "MusicDirectory"
        findings, _ = check_song_folder(song_dir)
        self.assertIn("missing_music_file", [f.code for f in findings])

    def test_non_finite_timing_numbers_are_rejected(self):
        song_dir = FIXTURES / "broken_library" / "GroupB" / "NonFiniteTiming"
        findings, _ = check_song_folder(song_dir)
        codes = [f.code for f in findings]
        self.assertIn("malformed_bpms", codes)
        self.assertIn("malformed_stops", codes)
        self.assertIn("malformed_offset", codes)

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
