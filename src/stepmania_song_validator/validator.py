"""Top-level orchestration: run all three check categories over a library."""

from __future__ import annotations

from pathlib import Path

from .checks import batocera_layout, chart_integrity, duplicates
from .models import Report


def validate_library(library_path: Path) -> Report:
    library_path = Path(library_path)
    report = Report(library_path=library_path)

    layout_findings, valid_song_dirs = batocera_layout.check_library_layout(library_path)
    report.findings.extend(layout_findings)
    report.songs_scanned = len(valid_song_dirs)

    for song_dir in valid_song_dirs:
        chart_findings, charts_scanned = chart_integrity.check_song_folder(song_dir)
        report.findings.extend(chart_findings)
        report.charts_scanned += charts_scanned

    report.findings.extend(duplicates.check_duplicates(valid_song_dirs))

    return report
