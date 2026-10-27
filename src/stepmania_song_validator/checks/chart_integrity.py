"""Chart integrity checks for .sm / .ssc files.

Flags:
  - unparseable / malformed directive syntax
  - #MUSIC: reference pointing at a missing audio file
  - malformed #BPMS: / #STOPS: timing data (non-numeric, negative where
    invalid, unsorted beat positions)
  - note rows containing symbols outside the source-confirmed engine vocabulary
  - unsupported SSC chart-local playback tags, reported as warnings
"""

from __future__ import annotations

import math
from pathlib import Path

from ..models import Finding, Severity
from ..simfile_parser import Simfile, SimfileParseError, parse_simfile

SIMFILE_EXTENSIONS = (".sm", ".ssc")

# StepMania/ITGmania NoteDataUtil recognizes these note-data symbols. Unknown
# symbols are silently converted to empty notes by the engines, so this
# validator reports them to avoid claiming that their note content was checked.
_VALID_NOTE_CHARS = set("01234MKLF")
_UNSUPPORTED_TIMING_TAGS = {
    "ATTACKS",
    "COMBOS",
    "DELAYS",
    "FAKES",
    "LABELS",
    "SCROLLS",
    "SPEEDS",
    "TICKCOUNTS",
    "TIMESIGNATURES",
    "WARPS",
}


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

        findings.extend(_check_music_references(simfile, song_dir))
        findings.extend(_check_timing(simfile))
        findings.extend(_check_unsupported_chart_features(simfile))
        findings.extend(_check_notes_structure(simfile))

        charts_scanned += len(simfile.notes)

    return findings, charts_scanned


def _check_music_references(simfile: Simfile, song_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    music = simfile.get("MUSIC")
    chart_music = {block.tags.get("MUSIC") for block in simfile.notes}
    chart_music.discard(None)

    if not music and (
        not simfile.notes or any("MUSIC" not in block.tags for block in simfile.notes)
    ):
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.WARNING,
                code="missing_music_tag",
                message="No #MUSIC: tag found",
                path=simfile.path,
            )
        )
    references = set(chart_music)
    if music:
        references.add(music)
    for reference in sorted(references):
        music_path = song_dir / reference
        if not music_path.exists():
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="missing_music_file",
                    message=f"#MUSIC: references '{reference}', which does not exist in {song_dir}",
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


def _check_timing(simfile: Simfile) -> list[Finding]:
    findings: list[Finding] = []
    global_bpms = simfile.get("BPMS")
    global_stops = simfile.get("STOPS")
    charts = simfile.notes

    # Validate song timing once. A missing song BPMS is only an error when
    # there is no chart-local BPMS to supply timing for one or more charts.
    if global_bpms is not None:
        findings.extend(_check_bpms_value(global_bpms, simfile))
    elif not charts:
        findings.extend(_check_bpms_value(None, simfile))

    if global_stops is not None:
        findings.extend(_check_stops_value(global_stops, simfile))
    global_offset = simfile.get("OFFSET")
    if global_offset is not None:
        findings.extend(_check_offset_value(global_offset, simfile))

    for idx, chart in enumerate(charts):
        label = chart.difficulty or chart.description or f"chart #{idx}"
        if "BPMS" in chart.tags:
            findings.extend(_check_bpms_value(chart.tags["BPMS"], simfile, label))
        elif global_bpms is None:
            # Report one missing timing source per chart to identify precisely
            # which SSC chart lacks both song and chart timing.
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.ERROR,
                    code="missing_bpms",
                    message=f"Chart '{label}' has no chart-local or song-level #BPMS: tag",
                    path=simfile.path,
                )
            )

        if "STOPS" in chart.tags:
            findings.extend(_check_stops_value(chart.tags["STOPS"], simfile, label))
        if "OFFSET" in chart.tags:
            findings.extend(_check_offset_value(chart.tags["OFFSET"], simfile, label))

    return findings


def _check_bpms_value(
    raw: str | None, simfile: Simfile, chart_label: str | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    scope = f" in chart '{chart_label}'" if chart_label else ""
    if raw is None:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="missing_bpms",
                message=f"No #BPMS: tag found{scope}",
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
                message=f"#BPMS:{scope} {err}",
                path=simfile.path,
            )
        )

    if not pairs and not errors:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="empty_bpms",
                message=f"#BPMS:{scope} has no timing entries",
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
                    message=(
                        f"#BPMS:{scope} BPM value {bpm} at beat {beat} must be positive"
                    ),
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
                message=f"#BPMS:{scope} beat positions are not in ascending order",
                path=simfile.path,
            )
        )

    return findings


def _check_stops_value(
    raw: str, simfile: Simfile, chart_label: str | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    scope = f" in chart '{chart_label}'" if chart_label else ""

    pairs, errors = _parse_timing_pairs(raw)
    for err in errors:
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.ERROR,
                code="malformed_stops",
                message=f"#STOPS:{scope} {err}",
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
                    message=(
                        f"#STOPS:{scope} negative stop duration {duration} at beat {beat}"
                    ),
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
                message=f"#STOPS:{scope} beat positions are not in ascending order",
                path=simfile.path,
            )
        )

    return findings


def _check_offset_value(
    raw: str, simfile: Simfile, chart_label: str | None = None
) -> list[Finding]:
    try:
        value = float(raw)
    except ValueError:
        valid = False
    else:
        valid = math.isfinite(value)
    if valid:
        return []

    scope = f" in chart '{chart_label}'" if chart_label else ""
    return [
        Finding(
            category="chart_integrity",
            severity=Severity.ERROR,
            code="malformed_offset",
            message=f"#OFFSET:{scope} must be a finite numeric value",
            path=simfile.path,
        )
    ]


def _check_unsupported_chart_features(simfile: Simfile) -> list[Finding]:
    findings: list[Finding] = []
    for tag in sorted(_UNSUPPORTED_TIMING_TAGS.intersection(simfile.tags)):
        findings.append(
            Finding(
                category="chart_integrity",
                severity=Severity.WARNING,
                code="unsupported_timing_feature",
                message=(
                    f"Song-level #{tag}: is not checked by this validator's "
                    "supported subset"
                ),
                path=simfile.path,
            )
        )
    for idx, chart in enumerate(simfile.notes):
        label = chart.difficulty or chart.description or f"chart #{idx}"
        for tag in sorted(_UNSUPPORTED_TIMING_TAGS.intersection(chart.tags)):
            findings.append(
                Finding(
                    category="chart_integrity",
                    severity=Severity.WARNING,
                    code="unsupported_timing_feature",
                    message=(
                        f"Chart '{label}' uses SSC #{tag}:, which is not checked "
                        "by this validator's supported subset"
                    ),
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
