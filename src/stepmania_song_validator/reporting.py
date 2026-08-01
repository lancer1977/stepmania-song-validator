"""Human-readable and JSON report rendering."""

from __future__ import annotations

import json

from .models import Report, Severity


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)


def render_human(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"stepmania-song-validator report for: {report.library_path}")
    lines.append(f"  songs scanned:  {report.songs_scanned}")
    lines.append(f"  charts scanned: {report.charts_scanned}")
    lines.append("")

    if not report.findings:
        lines.append("No issues found.")
        return "\n".join(lines)

    by_category: dict[str, list] = {}
    for finding in report.findings:
        by_category.setdefault(finding.category, []).append(finding)

    category_labels = {
        "chart_integrity": "Chart Integrity",
        "duplicate": "Duplicate Detection",
        "batocera_layout": "Batocera Song-Discovery Compatibility",
    }

    for category in ("batocera_layout", "chart_integrity", "duplicate"):
        findings = by_category.get(category)
        if not findings:
            continue
        lines.append(f"== {category_labels.get(category, category)} ==")
        for finding in findings:
            marker = "ERROR" if finding.severity == Severity.ERROR else "WARN "
            lines.append(f"  [{marker}] {finding.code}: {finding.message}")
            lines.append(f"          -> {finding.path}")
        lines.append("")

    lines.append(
        f"Summary: {report.error_count} error(s), {report.warning_count} warning(s)"
    )
    lines.append("Result: FAIL" if not report.ok else "Result: PASS")
    return "\n".join(lines)
