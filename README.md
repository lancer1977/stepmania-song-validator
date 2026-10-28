# StepMania Song Validator

CLI tool for validating StepMania/ITGmania song libraries before copying them
onto a device (e.g. a Batocera box running the StepMania Flatpak launcher or
the ITGmania portable launcher). It performs static, non-interactive analysis
of a song library folder and produces a pass/fail report.

This tool does not generate charts (see
[`stepmania-ai-songmaker`](https://github.com/lancer1977/stepmania-ai-songmaker)
for that), does not offer interactive library curation or playlists (see
`StepManiaSongManager`), and does not run StepMania/ITGmania itself. It only
reads files on disk.

## Tags

- stepmania-song-validator
- validator
- ci
- testing
- stepmania
- batocera

## Quick Start

```bash
# Setup
cd ~/code/stepmania-song-validator
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Validate a song library
stepmania-song-validator ~/Downloads/MySongPack
```

## Usage

```bash
# Human-readable summary (default)
stepmania-song-validator /path/to/Songs

# Machine-readable JSON, e.g. for CI
stepmania-song-validator /path/to/Songs --json
```

Exit code is `0` when no errors were found (warnings do not fail the run) and
`1` when at least one error was found.

## What Each Check Category Catches

### 1. Chart integrity (`.sm` / `.ssc` parsing)

- Unparseable or malformed directive syntax (missing `;` terminator, missing
  `:` separator, no recognizable `#TAG:value;` directives at all).
- `#MUSIC:` referencing a path that is not a regular audio file in the song
  folder.
- Malformed `#BPMS:` / `#STOPS:` timing data: non-numeric beat/value entries,
  non-positive BPM values, negative stop durations, and beat positions that
  are not in ascending order.
- SM and SSC chart rows using the engine's supported note symbols (`0`–`4`,
  `M`, `K`, `L`, `F`). Unknown symbols are errors in this validator because
  the engine silently turns unrecognized symbols into empty notes.
- Chart-local SSC `#MUSIC:`, `#BPMS:`, `#STOPS:` and finite numeric `#OFFSET:`
  fields, including multiple charts with different declared music/timing
  values. Song-level music and timing fields are also checked. Empty chart
  music references use a nonempty song-level path for file checking; if no
  effective path is declared, the report includes `missing_music_tag`.
- SSC `#NOTES2:` blocks and bracketed keysound indices are recognized and their
  note symbols are checked. A warning says keysound association and audio
  mapping are not validated. Known playback tags outside this subset (such as
  `#DELAYS:` or `#WARPS:`) also produce a warning and do not fail the run.

Measure row counts are not required to be divisible by four. StepMania and
ITGmania map each nonempty row's proportional position in a measure to an
engine note row; the loader does not reject a measure based on its line count.
The validator therefore checks note symbols and supported timing references,
not measure row-count divisibility. This behavior is grounded in the pinned
upstream implementations: [StepMania `NoteDataUtil.cpp` at
`825467b`](https://github.com/stepmania/stepmania/blob/825467bcd81c812b33ad684dc04dd151b2d5dec3/src/NoteDataUtil.cpp#L62-L204)
and [ITGmania `NoteDataUtil.cpp` at
`8a3bf88`](https://github.com/itgmania/itgmania/blob/8a3bf8884acdcb69363f7f0ea592138e398c71e4/src/NoteDataUtil.cpp#L127-L205).
Their SSC loaders associate music and timing tags with individual charts; see
[StepMania `NotesLoaderSSC.cpp`](https://github.com/stepmania/stepmania/blob/825467bcd81c812b33ad684dc04dd151b2d5dec3/src/NotesLoaderSSC.cpp#L391-L508)
and [ITGmania `NotesLoaderSSC.cpp`](https://github.com/itgmania/itgmania/blob/8a3bf8884acdcb69363f7f0ea592138e398c71e4/src/NotesLoaderSSC.cpp#L494-L585).
StepMania's loader also recognizes `NOTES` and `NOTES2` in chart scope, and its
note parser skips bracketed keysound indices; see [the chart handlers](https://github.com/stepmania/stepmania/blob/825467bcd81c812b33ad684dc04dd151b2d5dec3/src/NotesLoaderSSC.cpp#L632-L641),
[chart note loading](https://github.com/stepmania/stepmania/blob/825467bcd81c812b33ad684dc04dd151b2d5dec3/src/NotesLoaderSSC.cpp#L1012-L1030),
and [keysound annotations](https://github.com/stepmania/stepmania/blob/825467bcd81c812b33ad684dc04dd151b2d5dec3/src/NoteDataUtil.cpp#L206-L220).

The validator checks declared song-level and chart-local timing fields
individually. It does not merge them into an engine-effective timing map,
infer fallback or inheritance for unprovided chart fields, or prove rendered
playback. Unsupported timing and keysound details remain warnings.

Compatibility note: the validator no longer emits the `malformed_measure_length`
finding for non-multiple-of-four rows. JSON report fields, categories and CLI
exit semantics remain unchanged. Unsupported SSC chart playback tags are
reported with warning severity, separate from malformed syntax and content
errors.

### 2. Duplicate detection

Non-interactive, scriptable duplicate detection across the whole library,
suitable for a CI report (unlike StepManiaSongManager's interactive GUI
duplicate warnings). Two independent signals are checked and reported
separately, since they answer different questions:

- **Audio content hash** (SHA-256 of the file referenced by `#MUSIC:`) --
  catches the same audio file copied into multiple song folders.
- **Normalized title+artist+BPM fingerprint** -- catches the same song
  re-packaged or re-charted with a different audio encode.

### 3. Batocera song-discovery compatibility

Grounded in how `batocera-services`' launcher bundles actually configure
song discovery (`AdditionalSongFoldersReadOnly` pointed at a single `Songs/`
root; see that repo's `stepmania-flatpak-launcher` and
`itgmania-portable-launcher` bundles) and in a physical-host proof that
confirmed real song discovery at exactly two directory levels
(`Songs/<Group>/<Song>/`):

- Song folders that don't sit at the expected two-level depth: a folder with
  chart files directly under the library root (missing its group folder), or
  chart files nested a third level deep.
- Empty group/song folders and song folders with no chart file.
- Group/song folder names containing shell-metacharacter or filesystem-risky
  characters (`* ? " < > | ; & $ \` \ '`), control characters, or leading/
  trailing whitespace -- a defensive check beyond what the launcher scripts
  explicitly prove, since neither script shell-escapes individual song
  folder names when scanning them.

## Testing

Run the automated test suite with:

```bash
python -m unittest discover -s tests
```

Build package artifacts and smoke-test the CLI against the checked-in
fixture libraries with:

```bash
python -m pip install ".[build]"
scripts/validate.sh
```

Test fixtures live under `tests/fixtures/`:

- `valid_library/` -- a well-formed two-level library, including sparse and
  three-row measures, 8/12/24-row subdivisions, a multi-chart SSC with
  chart-local music/timing and a `NOTES2` keysound annotation, and a deliberate
  duplicate pair
  (`DuplicateSong1` / `DuplicateSong2`, identical audio content and matching
  title/artist/BPM).
- `broken_library/` -- deliberately broken cases: a missing `#MUSIC:`
  reference, malformed `#BPMS:`/`#STOPS:`, invalid note symbols, malformed
  SSC timing and chart-local missing music, an unparseable file, a song folder
  missing its group folder, and a song folder with a shell-risky name.

## Documentation

- [StepMania simfile format reference (`.sm`/`.ssc`)](https://github.com/stepmania/stepmania/wiki/sm)
