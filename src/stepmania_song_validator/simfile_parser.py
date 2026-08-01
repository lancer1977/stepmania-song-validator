"""Minimal parser for StepMania's plain-text simfile formats (.sm and .ssc).

Both formats are a sequence of ``#TAG:value;`` directives. ``.sm`` packs an
entire chart (steps + metadata) into a single ``#NOTES:`` block with
colon-separated fields. ``.ssc`` splits charts into their own
``#NOTEDATA:`` ... ``#NOTES:`` blocks but uses the same ``#TAG:value;``
directive syntax for everything else. This parser is intentionally forgiving
about *unknown* tags (StepMania has dozens) but strict about structural
well-formedness: unterminated directives, unbalanced values, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class SimfileParseError(Exception):
    """Raised when a simfile is too malformed to extract any structure from."""


@dataclass
class NotesBlock:
    """One difficulty chart's #NOTES data (from .sm or .ssc)."""

    raw_header: str  # the colon-separated fields before the note data
    step_type: str | None
    description: str | None
    difficulty: str | None
    meter: str | None
    measures: list[list[str]] = field(default_factory=list)  # measures -> note lines


@dataclass
class Simfile:
    path: Path
    tags: dict[str, str]
    notes: list[NotesBlock]
    parse_warnings: list[str] = field(default_factory=list)

    def get(self, tag: str) -> str | None:
        return self.tags.get(tag.upper())


def _strip_comments(text: str) -> str:
    """Strip //-style line comments, respecting that ; and : can appear in them."""
    lines = []
    for line in text.splitlines():
        idx = line.find("//")
        lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(lines)


def parse_simfile(path: Path) -> Simfile:
    """Parse a .sm or .ssc file into tags + notes blocks.

    Raises SimfileParseError if the file cannot be read or contains no
    recognizable #TAG: directives at all.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SimfileParseError(f"Could not read file: {exc}") from exc

    text = _strip_comments(raw)

    # Split on '#' directive starts. Each directive runs until the next
    # unescaped ';'. StepMania simfiles do not use ';' inside values except
    # within note data, which we handle separately.
    if "#" not in text:
        raise SimfileParseError("No '#TAG:' directives found in file")

    tags: dict[str, str] = {}
    notes: list[NotesBlock] = []
    warnings: list[str] = []

    # Walk directive by directive.
    pos = 0
    length = len(text)
    found_any = False
    while True:
        hash_idx = text.find("#", pos)
        if hash_idx == -1:
            break
        semi_idx = text.find(";", hash_idx)

        # A directive value should never legitimately contain another '#'
        # that starts a new line (StepMania directives always begin at the
        # start of a line). If the next '#'-starting-a-line comes before the
        # next ';', the current directive is missing its terminator -- don't
        # let the search silently swallow the following directive.
        next_hash_idx = hash_idx
        while True:
            next_hash_idx = text.find("#", next_hash_idx + 1)
            if next_hash_idx == -1:
                break
            if next_hash_idx == 0 or text[next_hash_idx - 1] == "\n":
                break

        if semi_idx == -1 or (next_hash_idx != -1 and next_hash_idx < semi_idx):
            warnings.append(
                f"Unterminated directive starting at offset {hash_idx} "
                "(missing trailing ';')"
            )
            end = next_hash_idx if next_hash_idx != -1 else length
            body = text[hash_idx + 1 : end]
            pos = end
        else:
            body = text[hash_idx + 1 : semi_idx]
            pos = semi_idx + 1

        colon_idx = body.find(":")
        if colon_idx == -1:
            warnings.append(f"Malformed directive with no ':' separator: '#{body[:40]}'")
            continue

        found_any = True
        tag = body[:colon_idx].strip().upper()
        value = body[colon_idx + 1 :]

        if tag == "NOTES":
            notes.append(_parse_notes_value(value, warnings))
        else:
            # First occurrence wins (matches StepMania's own behavior for
            # simple metadata tags); later duplicates are not an error.
            tags.setdefault(tag, value.strip())

    if not found_any:
        raise SimfileParseError("No well-formed '#TAG:value;' directives found in file")

    return Simfile(path=path, tags=tags, notes=notes, parse_warnings=warnings)


def _parse_notes_value(value: str, warnings: list[str]) -> NotesBlock:
    """Parse the colon-separated body of a #NOTES: directive.

    Layout (both .sm inline notes and .ssc chart-local notes share this once
    the leading '#NOTES:' has been stripped):

        StepsType:
        Description:
        Difficulty:
        Meter:
        Radar/Groove values:
        note data (measures separated by ',')
    """
    fields = value.split(":")
    # Pad defensively; a well-formed block has at least 6 fields.
    while len(fields) < 6:
        fields.append("")

    step_type = fields[0].strip() or None
    description = fields[1].strip() or None
    difficulty = fields[2].strip() or None
    meter = fields[3].strip() or None
    note_data = fields[5] if len(fields) > 5 else ""

    if len(fields) < 6:
        warnings.append("NOTES block has fewer fields than expected (malformed header)")

    measures: list[list[str]] = []
    for measure_text in note_data.split(","):
        lines = [ln.strip() for ln in measure_text.strip().splitlines() if ln.strip()]
        measures.append(lines)

    # Drop a single trailing empty measure produced by a trailing comma with
    # nothing after it (not itself an error).
    if measures and not measures[-1]:
        measures.pop()

    return NotesBlock(
        raw_header=value,
        step_type=step_type,
        description=description,
        difficulty=difficulty,
        meter=meter,
        measures=measures,
    )
