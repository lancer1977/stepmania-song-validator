"""Chart integrity checks for .sm / .ssc files.

Flags:
  - unparseable / malformed directive syntax
  - #MUSIC: reference pointing at a missing audio file
  - malformed #BPMS: / #STOPS: timing data (non-numeric, negative where
    invalid, unsorted beat positions)
  - a #NOTES: measure whose note-line count doesn't divide evenly by 4
    (structurally corrupt step data — StepMania measures are always a
    multiple of 4 rows: quarter notes at minimum resolution)
"""

from __future__ import annotations

from pathlib import Path

from ..models import Finding, Severity
from ..simfile_parser import Simfile, SimfileParseError, parse_simfile

SIMFILE_EXTENSIONS = (".sm", ".ssc")

# Valid characters on a StepMania note-data row: 0-3 (or more for ssc "extra"
# note types), plus M for mines and hold/roll markers used by some formats.
_VALID_NOTE_CHARS = set("0123456789MLFmlf")


def find_simfiles(song_dir: Path) -> list[Path]:
    return sorted(
        p for p in song_dir.iterdir() if p.is_file() and p.suffix.lower() in SIMFILE_EXTENSIONS
    )


def check_song_folder(song_dir: Path) -> tuple[list[Finding], int]:
    """Run all chart-integrity checks for every simfile in a song folder.

    Returns (findings, charts_scanned).
    """
    findings: list[Finding] = []
    charts_scanned = 0

    for simfile_path in find_simfiles(song_dir):
        try:
            simfile = parse_simfile(simfile_path)
        except SimfileParseError as exc:
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="unparseable_simfile",
                    message=f"Could not parse simfile: {exc}",
                    path=simfile_path,
                )
            )
            continue

        for warning in simfile.parse_warnings:
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="malformed_syntax",
                    message=warning,
                    path=simfile_path,
                )
            )

        findings.extend(_check_music_reference(simfile, song_dir))
        findings.extend(_check_bpms(simfile))
        findings.extend(_check_stops(simfile))
        findings.extend(_check_notes_structure(simfile))

        charts_scanned += len(simfile.notes)

    return findings, charts_scanned


def _check_music_reference(simfile: Simfile, song_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    music = simfile.get("MUSIC")
    if not music:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.WARNING,
                code="missing_music_tag",
                message="No #MUSIC: tag found",
                path=simfile.path,
            )
        )
        return findings

    music_path = song_dir / music
    if not music_path.exists():
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="missing_music_file",
                message=f"#MUSIC: references '{music}', which does not exist in {song_dir}",
                path=simfile.path,
            )
        )
    return findings


def _parse_timing_pairs(raw: str) -> tuple[list[tuple[float, float]], list[str]]:
    """Parse a beat=value,beat=value,... timing string.

    Returns (pairs, errors). Pairs that fail to parse as floats are skipped
    and reported as errors rather than raising, so the rest of the string
    can still be checked (e.g. for sort order among the parseable entries).
    """
    pairs: list[tuple[float, float]] = []
    errors: list[str] = []
    raw = raw.strip()
    if not raw:
        return pairs, errors

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            errors.append(f"Malformed timing entry (missing '='): '{entry}'")
            continue
        beat_str, value_str = entry.split("=", 1)
        try:
            beat = float(beat_str.strip())
        except ValueError:
            errors.append(f"Non-numeric beat position: '{beat_str.strip()}'")
            continue
        try:
            value = float(value_str.strip())
        except ValueError:
            errors.append(f"Non-numeric value: '{value_str.strip()}'")
            continue
        pairs.append((beat, value))

    return pairs, errors


def _check_bpms(simfile: Simfile) -> list[Finding]:
    findings: list[Finding] = []
    raw = simfile.get("BPMS")
    if raw is None:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="missing_bpms",
                message="No #BPMS: tag found",
                path=simfile.path,
            )
        )
        return findings

    pairs, errors = _parse_timing_pairs(raw)
    for err in errors:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="malformed_bpms",
                message=f"#BPMS: {err}",
                path=simfile.path,
            )
        )

    if not pairs and not errors:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="empty_bpms",
                message="#BPMS: has no timing entries",
                path=simfile.path,
            )
        )
        return findings

    for beat, bpm in pairs:
        if bpm <= 0:
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="invalid_bpm_value",
                    message=f"#BPMS: BPM value {bpm} at beat {beat} must be positive",
                    path=simfile.path,
                )
            )

    beats = [b for b, _ in pairs]
    if beats != sorted(beats):
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="unsorted_bpms",
                message="#BPMS: beat positions are not in ascending order",
                path=simfile.path,
            )
        )

    return findings


def _check_stops(simfile: Simfile) -> list[Finding]:
    findings: list[Finding] = []
    raw = simfile.get("STOPS")
    if raw is None:
        return findings  # #STOPS: is optional

    pairs, errors = _parse_timing_pairs(raw)
    for err in errors:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="malformed_stops",
                message=f"#STOPS: {err}",
                path=simfile.path,
            )
        )

    for beat, duration in pairs:
        if duration < 0:
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="negative_stop_duration",
                    message=f"#STOPS: negative stop duration {duration} at beat {beat}",
                    path=simfile.path,
                )
            )

    beats = [b for b, _ in pairs]
    if beats != sorted(beats):
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="unsorted_stops",
                message="#STOPS: beat positions are not in ascending order",
                path=simfile.path,
            )
        )

    return findings


def _check_notes_structure(simfile: Simfile) -> list[Finding]:
    findings: list[Finding] = []
    if not simfile.notes:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="no_notes_block",
                message="No #NOTES: chart data found",
                path=simfile.path,
            )
        )
        return findings

    for idx, block in enumerate(simfile.notes):
        chart_label = block.difficulty or block.description or f"chart #{idx}"

        if not block.measures:
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="empty_notes_block",
                    message=f"Chart '{chart_label}' has no measure data",
                    path=simfile.path,
                )
            )
            continue

        for m_idx, measure in enumerate(block.measures):
            if len(measure) % 4 != 0:
                findings.append(
                    Finding(
                        category="chart_integrity",
                        severity=Severity.ERROR,
                        code="malformed_measure_length",
                        message=(
                            f"Chart '{chart_label}' measure {m_idx} has "
                            f"{len(measure)} note lines, which is not evenly "
                            "divisible by 4 (structurally corrupt)"
                        ),
                        path=simfile.path,
                    )
                )

            for line in measure:
                if any(ch not in _VALID_NOTE_CHARS for ch in line):
                    findings.append(
                        Finding(
                            category="chart_integrity",
                            severity=Severity.ERROR,
                            code="invalid_note_characters",
                            message=(
                                f"Chart '{chart_label}' measure {m_idx} has "
                                f"an invalid note line: '{line}'"
                            ),
                            path=simfile.path,
                        )
                    )
                    break  # one report per measure is enough

    return findings
