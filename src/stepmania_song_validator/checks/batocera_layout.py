"""Batocera song-discovery compatibility checks.

Grounded in how batocera-services' launcher bundles actually wire song
discovery (see repo docs referenced below, not guessed from the StepMania
manual alone):

- Both the `stepmania-flatpak-launcher` and `itgmania-portable-launcher`
  bundles point StepMania's `AdditionalSongFoldersReadOnly` preference at a
  single `Songs/` root directory
  (`~/code/batocera-services/bundles/itgmania-portable-launcher/service.sh`,
  function `configure_song_directory`).
- `~/code/batocera-services/docs/host-proofs/2026-07-26-rhythm-dual-runtime-len1.md`
  confirms a real discovered song lived at `Songs/Sidecar Smoke/Quick Proof`
  -- i.e. exactly two directory levels below the configured songs root:
  `<GroupFolder>/<SongFolder>/`. A song folder directly under the library
  root (no group folder) or nested a third level deep will not be discovered
  the same way.
- Neither launcher script itself sanitizes or quotes song/group folder names
  beyond normal shell double-quoting of `$ITGMANIA_SONGS_DIR` /
  `$STEPMANIA_SONGS_DIR` as a whole path; there is no evidence in either
  `service.sh` that individual song folder names are shell-escaped when the
  engine scans them. Filenames containing shell-metacharacters or control
  characters are therefore flagged defensively here as a portability risk
  for any future scripts (e.g. `apply-controller-map.sh`-style helpers) that
  might glob over song folder names, even though StepMania's own internal
  scanner (a compiled C++ directory walk, not shell) would likely tolerate
  most of them. This is the one place in this tool where we extrapolate
  beyond what the launcher scripts explicitly prove.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Finding, Severity

# Characters known to require special handling in POSIX shells or that are
# disallowed/problematic on common filesystems Batocera images might use
# (exFAT/FAT32 on the SD card, in particular, forbids several of these
# outright).
_RISKY_CHARS = set('*?"<>|;&$`\\\'')
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f]")

SIMFILE_EXTENSIONS = (".sm", ".ssc")


def _has_simfile(folder: Path) -> bool:
    try:
        return any(p.suffix.lower() in SIMFILE_EXTENSIONS for p in folder.iterdir() if p.is_file())
    except OSError:
        return False


def _flag_risky_name(name: str, path: Path, findings: list[Finding]) -> None:
    risky_found = sorted({ch for ch in name if ch in _RISKY_CHARS})
    if risky_found:
        findings.append(
            Finding(
                category="batocera_layout",
                severity=Severity.WARNING,
                code="risky_filename_characters",
                message=(
                    f"Name '{name}' contains shell/filesystem-risky characters "
                    f"{risky_found}; may break scripts or FAT32/exFAT SD-card "
                    "storage used on Batocera devices"
                ),
                path=path,
            )
        )
    if _CONTROL_CHAR_RE.search(name):
        findings.append(
            Finding(
                category="batocera_layout",
                severity=Severity.ERROR,
                code="control_characters_in_filename",
                message=f"Name '{name}' contains control characters",
                path=path,
            )
        )
    if name != name.strip():
        findings.append(
            Finding(
                category="batocera_layout",
                severity=Severity.WARNING,
                code="leading_or_trailing_whitespace",
                message=f"Name '{name}' has leading/trailing whitespace",
                path=path,
            )
        )


def check_library_layout(library_root: Path) -> tuple[list[Finding], list[Path]]:
    """Validate the library follows Songs/<Group>/<Song>/ layout.

    Returns (findings, valid_song_dirs) where valid_song_dirs is the list of
    folders that look like legitimate two-level song folders (used by other
    checks, e.g. duplicate detection and chart integrity, so they only walk
    folders that Batocera would actually discover).
    """
    findings: list[Finding] = []
    valid_song_dirs: list[Path] = []

    if not library_root.is_dir():
        findings.append(
            Finding(
                category="batocera_layout",
                severity=Severity.ERROR,
                code="library_root_missing",
                message=f"Library path does not exist or is not a directory: {library_root}",
                path=library_root,
            )
        )
        return findings, valid_song_dirs

    top_level = sorted(p for p in library_root.iterdir() if p.is_dir())

    if not top_level:
        findings.append(
            Finding(
                category="batocera_layout",
                severity=Severity.WARNING,
                code="empty_library",
                message=f"No group folders found under {library_root}",
                path=library_root,
            )
        )
        return findings, valid_song_dirs

    for group_dir in top_level:
        _flag_risky_name(group_dir.name, group_dir, findings)

        if _has_simfile(group_dir):
            # A simfile directly under the group folder means this is
            # actually a song folder sitting one level too shallow --
            # Songs/<SongFolder>/ instead of Songs/<Group>/<Song>/.
            findings.append(
                Finding(
                    category="batocera_layout",
                    severity=Severity.ERROR,
                    code="song_missing_group_folder",
                    message=(
                        f"'{group_dir.name}' contains chart files directly; "
                        "Batocera/StepMania expects Songs/<Group>/<Song>/ "
                        "(two levels), so this song folder needs a parent "
                        "group folder to be discovered"
                    ),
                    path=group_dir,
                )
            )
            continue

        song_dirs = sorted(p for p in group_dir.iterdir() if p.is_dir())
        if not song_dirs:
            findings.append(
                Finding(
                    category="batocera_layout",
                    severity=Severity.WARNING,
                    code="empty_group_folder",
                    message=f"Group folder '{group_dir.name}' has no song subfolders",
                    path=group_dir,
                )
            )
            continue

        for song_dir in song_dirs:
            _flag_risky_name(song_dir.name, song_dir, findings)

            if not _has_simfile(song_dir):
                # Could be a third-level-deep nesting problem or just an
                # empty/incomplete song folder either way, Batocera's
                # scanner will not find playable charts here.
                nested_simfiles = list(song_dir.rglob("*.sm")) + list(song_dir.rglob("*.ssc"))
                if nested_simfiles:
                    findings.append(
                        Finding(
                            category="batocera_layout",
                            severity=Severity.ERROR,
                            code="chart_nested_too_deep",
                            message=(
                                f"'{song_dir}' has no chart files directly inside it, "
                                "but chart files exist in a deeper subfolder "
                                f"({nested_simfiles[0].relative_to(song_dir)}); "
                                "Batocera expects charts directly in "
                                "Songs/<Group>/<Song>/, not a third level deep"
                            ),
                            path=song_dir,
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            category="batocera_layout",
                            severity=Severity.WARNING,
                            code="song_folder_missing_chart",
                            message=f"'{song_dir}' has no .sm/.ssc chart file",
                            path=song_dir,
                        )
                    )
                continue

            valid_song_dirs.append(song_dir)

    return findings, valid_song_dirs
