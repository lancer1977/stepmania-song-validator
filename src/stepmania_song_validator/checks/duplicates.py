"""Duplicate song detection across a library.

Two independent signals are combined:

1. Audio content hash (SHA-256 of the referenced #MUSIC: file's bytes) --
   catches exact re-encodes/copies of the same audio file placed under
   different song folders.
2. A normalized title+artist+BPM fingerprint -- catches the same song
   re-charted or re-packaged (different audio encode, same metadata) which a
   content hash alone would miss.

This is intentionally non-interactive and produces a flat list of duplicate
groups suitable for CI/report consumption, unlike StepManiaSongManager's
interactive GUI duplicate warnings.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..models import Finding, Severity
from ..simfile_parser import SimfileParseError, parse_simfile
from .chart_integrity import find_simfiles

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize(value: str) -> str:
    value = value.strip().lower()
    value = _NON_ALNUM_RE.sub(" ", value)
    value = _WHITESPACE_RE.sub(" ", value).strip()
    return value


def _hash_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


@dataclass
class SongSignature:
    song_dir: Path
    audio_hash: str | None
    fingerprint: str | None  # normalized "title|artist|bpm"


def _extract_signature(song_dir: Path) -> SongSignature | None:
    simfiles = find_simfiles(song_dir)
    if not simfiles:
        return None

    # Prefer .ssc if present (superset format), else first .sm found.
    chosen = next((p for p in simfiles if p.suffix.lower() == ".ssc"), simfiles[0])
    try:
        simfile = parse_simfile(chosen)
    except SimfileParseError:
        return None

    title = simfile.get("TITLE") or ""
    artist = simfile.get("ARTIST") or ""
    bpms = simfile.get("BPMS") or ""
    # Use just the first BPM value in the fingerprint; a full timing-map
    # comparison is brittle across re-charts of the same song.
    first_bpm = ""
    if "=" in bpms:
        first_bpm = bpms.split(",")[0].split("=")[-1].strip()

    fingerprint = None
    if title:
        fingerprint = "|".join(
            [_normalize(title), _normalize(artist), _normalize(first_bpm)]
        )

    audio_hash = None
    music = simfile.get("MUSIC")
    if music:
        music_path = song_dir / music
        if music_path.exists():
            audio_hash = _hash_file(music_path)

    if fingerprint is None and audio_hash is None:
        return None

    return SongSignature(song_dir=song_dir, audio_hash=audio_hash, fingerprint=fingerprint)


def check_duplicates(song_dirs: list[Path]) -> list[Finding]:
    """Detect duplicate songs across the given list of song folders."""
    findings: list[Finding] = []

    signatures = [s for s in (_extract_signature(d) for d in song_dirs) if s is not None]

    by_hash: dict[str, list[SongSignature]] = {}
    by_fingerprint: dict[str, list[SongSignature]] = {}
    for sig in signatures:
        if sig.audio_hash:
            by_hash.setdefault(sig.audio_hash, []).append(sig)
        if sig.fingerprint:
            by_fingerprint.setdefault(sig.fingerprint, []).append(sig)

    # Dedup within each signal type independently -- the two signals answer
    # different questions (identical audio bytes vs. matching metadata), so
    # a pair that trips both is worth reporting under both codes.
    for audio_hash, group in by_hash.items():
        if len(group) < 2:
            continue
        paths = sorted(s.song_dir for s in group)
        for p in paths:
            others = ", ".join(str(o) for o in paths if o != p)
            findings.append(
                Finding(
                    category="duplicate",
                    severity=Severity.WARNING,
                    code="duplicate_audio_hash",
                    message=(
                        f"Identical audio content (sha256={audio_hash[:12]}...) "
                        f"shared with: {others}"
                    ),
                    path=p,
                )
            )

    for fingerprint, group in by_fingerprint.items():
        if len(group) < 2:
            continue
        paths = sorted(s.song_dir for s in group)
        title, artist, bpm = fingerprint.split("|")
        for p in paths:
            others = ", ".join(str(o) for o in paths if o != p)
            findings.append(
                Finding(
                    category="duplicate",
                    severity=Severity.WARNING,
                    code="duplicate_fingerprint",
                    message=(
                        f"Matching title/artist/BPM fingerprint "
                        f"(title='{title}', artist='{artist}', bpm='{bpm}') "
                        f"shared with: {others}"
                    ),
                    path=p,
                )
            )

    return findings
