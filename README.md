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
- `#MUSIC:` referencing an audio file that does not exist in the song folder.
- Malformed `#BPMS:` / `#STOPS:` timing data: non-numeric beat/value entries,
  non-positive BPM values, negative stop durations, and beat positions that
  are not in ascending order.
- A `#NOTES:` measure whose row count isn't evenly divisible by 4 (StepMania
  measures are always a multiple of 4 rows at minimum resolution --
  anything else indicates structurally corrupt step data), and note rows
  containing characters outside the valid step/mine/hold vocabulary.

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

- `valid_library/` -- a well-formed two-level library, including a
  deliberate duplicate pair (`DuplicateSong1` / `DuplicateSong2`, identical
  audio content and matching title/artist/BPM).
- `broken_library/` -- deliberately broken cases: a missing `#MUSIC:`
  reference, malformed `#BPMS:`/`#STOPS:`, a measure with a bad row count, an
  unparseable file, a song folder missing its group folder, and a song
  folder with a shell-risky name.

## Documentation

- [StepMania simfile format reference (`.sm`/`.ssc`)](https://github.com/stepmania/stepmania/wiki/sm)
