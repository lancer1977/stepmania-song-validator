import unittest
from pathlib import Path

from stepmania_song_validator.simfile_parser import SimfileParseError, parse_simfile

FIXTURES = Path(__file__).parent / "fixtures"


class TestSimfileParser(unittest.TestCase):
    def test_parses_valid_sm(self):
        path = FIXTURES / "valid_library" / "GroupA" / "GoodSong" / "song.sm"
        simfile = parse_simfile(path)
        self.assertEqual(simfile.get("TITLE"), "Good Song")
        self.assertEqual(simfile.get("ARTIST"), "Test Artist")
        self.assertEqual(simfile.get("MUSIC"), "song.mp3")
        self.assertEqual(len(simfile.notes), 1)
        self.assertEqual(simfile.notes[0].difficulty, "Easy")
        self.assertEqual(len(simfile.notes[0].measures), 2)
        self.assertEqual(len(simfile.notes[0].measures[0]), 4)

    def test_unparseable_file_raises(self):
        path = FIXTURES / "broken_library" / "GroupB" / "UnparseableChart" / "song.sm"
        with self.assertRaises(SimfileParseError):
            parse_simfile(path)

    def test_missing_file_raises(self):
        with self.assertRaises(SimfileParseError):
            parse_simfile(FIXTURES / "does" / "not" / "exist.sm")

    def test_unterminated_directive_produces_warning(self):
        path = FIXTURES / "_scratch_unterminated.sm"
        path.write_text("#TITLE:Oops\n#ARTIST:Foo;\n")
        try:
            simfile = parse_simfile(path)
            self.assertTrue(any("Unterminated" in w for w in simfile.parse_warnings))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
