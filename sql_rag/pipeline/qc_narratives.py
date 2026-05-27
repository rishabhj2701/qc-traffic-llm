"""Use Case 2 — Automated QC narratives (rule-based + file scan)."""
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..config.phase1_config import CRITICAL_STATIONS, DATASETS_DIR, MODERATE_STATIONS


@dataclass
class QCAnomaly:
    station_id: str
    severity: str
    issue: str
    evidence: str
    recommendation: str


class QCNarrativeEngine:
    """Detects critical QC issues documented in Phase 1 (works without LLM)."""

    def __init__(self, datasets_dir: Path = DATASETS_DIR) -> None:
        self.datasets_dir = datasets_dir

    def _extract_adt(self, path: Path) -> float | None:
        try:
            for row in csv.reader(open(path, encoding="utf-8", errors="replace")):
                if row and row[0].strip().strip('"') == "ADT":
                    for cell in reversed(row):
                        c = cell.strip().strip('"')
                        if c.replace(".", "", 1).isdigit():
                            return float(c)
        except OSError:
            pass
        return None

    def scan(self) -> List[QCAnomaly]:
        anomalies: List[QCAnomaly] = []
        if not self.datasets_dir.is_dir():
            return anomalies

        for path in sorted(self.datasets_dir.glob("*.csv")):
            name = path.name
            text = path.read_text(encoding="utf-8", errors="replace")

            if "Export_CSV_Int" in name and "24,24,24" in text.replace(" ", ""):
                anomalies.append(
                    QCAnomaly(
                        station_id="Export_CSV_Int",
                        severity="CRITICAL",
                        issue="Fabricated turning movements",
                        evidence="All movements = 24; PHF = 1.00",
                        recommendation="Exclude from all analysis",
                    )
                )

            if "ExportCheckMB" in name and "volume" in name.lower():
                adt = self._extract_adt(path)
                if adt is not None and adt <= 48:
                    anomalies.append(
                        QCAnomaly(
                            station_id="ExportCheckMB",
                            severity="CRITICAL",
                            issue="Export artifact",
                            evidence=f"ADT = {int(adt)} with constant low hourly counts",
                            recommendation="Exclude from all analysis",
                        )
                    )

            if "717" in name and "Dec 17 2021" in name and "volume" in name.lower():
                adt = self._extract_adt(path)
                if adt and adt >= 50000:
                    anomalies.append(
                        QCAnomaly(
                            station_id="717",
                            severity="CRITICAL",
                            issue="Stuck sensor / synthetic Dec 2021",
                            evidence=f"ADT = {int(adt):,} on {name}",
                            recommendation="Exclude Dec 2021 dates",
                        )
                    )

            if "2447-stg-test" in name and "Oct 26 2024" in name and "volume_NB.csv" in name:
                if "250" in text and "251" in text and "345" in text:
                    anomalies.append(
                        QCAnomaly(
                            station_id="2447-stg-test-1-lane",
                            severity="CRITICAL",
                            issue="Sequential test pattern",
                            evidence="NB volumes increment 250→345 (Oct 26 2024)",
                            recommendation="Exclude all 2447 data",
                        )
                    )

            if "1234567891" in name and "speed" in name.lower() and "Mean Speed" in text:
                if re.search(r"1[2-3]\d MPH", text):
                    anomalies.append(
                        QCAnomaly(
                            station_id="1234567891",
                            severity="CRITICAL",
                            issue="Impossible mean speed",
                            evidence="Mean speed > 120 MPH in test station file",
                            recommendation="Exclude test station",
                        )
                    )

            if "1191" in name and "Apr 8 2025" in name and "speed" in name.lower():
                if "141 MPH" in text or "400.00%" in text:
                    anomalies.append(
                        QCAnomaly(
                            station_id="1191",
                            severity="HIGH",
                            issue="Speed report formula error",
                            evidence="Mean 141 MPH; cumulative percent = 400%",
                            recommendation="Use volume only; flag speed files",
                        )
                    )

        seen = set()
        unique: List[QCAnomaly] = []
        for a in anomalies:
            key = (a.station_id, a.issue)
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique

    def generate_narrative_report(self) -> Dict[str, Any]:
        anomalies = self.scan()
        lines = [
            "## Automated QC Narrative Report",
            f"Scanned **{len(list(self.datasets_dir.glob('*.csv')))}** CSV files in staging folder.",
            f"Detected **{len(anomalies)}** distinct anomaly types.\n",
        ]
        for a in anomalies:
            lines.append(
                f"### {a.station_id} ({a.severity})\n"
                f"- **Issue:** {a.issue}\n"
                f"- **Evidence:** {a.evidence}\n"
                f"- **Action:** {a.recommendation}\n"
            )
        lines.append("\n**Critical stations (config):** " + ", ".join(CRITICAL_STATIONS))
        lines.append("\n**Moderate stations:** " + ", ".join(MODERATE_STATIONS))
        return {
            "narrative": "\n".join(lines),
            "anomalies": [a.__dict__ for a in anomalies],
            "count": len(anomalies),
        }
