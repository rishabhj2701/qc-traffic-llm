"""Use Case 3 — Contextual pattern detection (verified Phase 1 patterns)."""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TrafficPattern:
    station_id: str
    pattern_name: str
    key_metric: str
    hypothesis: str
    confidence: float
    evidence: str


class PatternDetectionEngine:
    """Pre-validated patterns from CSV analysis — extensible with SQL in Phase 2."""

    VERIFIED_PATTERNS: List[TrafficPattern] = [
        TrafficPattern(
            station_id="725",
            pattern_name="Tidal commuter flow",
            key_metric="WB AM +35% vs EB at 8:00 AM (797 vs 588); EB PM peak 788 at 4:00 PM",
            hypothesis="Residential-to-employment corridor (I-395 / Pentagon access)",
            confidence=0.92,
            evidence="Midblock_725_Sep 27 2019_volume_WB.csv / _EB.csv",
        ),
        TrafficPattern(
            station_id="7",
            pattern_name="Weekday vs weekend divergence",
            key_metric="ADT 748 (Mar 5) vs 235 (Mar 9) — ~69% weekend drop",
            hypothesis="Low-volume residential near office core",
            confidence=0.88,
            evidence="Midblock_7_Mar 5 2019_volume_NB_SB.csv vs Mar 9",
        ),
        TrafficPattern(
            station_id="INT-0009",
            pattern_name="Multi-year intersection stability",
            key_metric="PM peak 5,708 (Oct 16, 2012); corridor TMC counts stable",
            hypothesis="Mature signals on S Patrick & Franklin",
            confidence=0.85,
            evidence="Intersection_INT-0009_Oct 16 2012_PM.csv",
        ),
        TrafficPattern(
            station_id="INT-0007",
            pattern_name="EB arterial dominance (AM)",
            key_metric="AM peak ~1,389 (May 15, 2013)",
            hypothesis="Columbus St / Franklin St eastbound priority",
            confidence=0.84,
            evidence="Intersection_INT-0007_May 15 2013_AM.csv",
        ),
        TrafficPattern(
            station_id="1191",
            pattern_name="PM-dominant balanced flow",
            key_metric="NB 396 @ 4:00 PM vs 305 @ 11:00 AM (Apr 8, 2025)",
            hypothesis="Commercial / mixed-use corridor",
            confidence=0.83,
            evidence="Midblock_1191_Apr 8 2025_volume_NB.csv",
        ),
    ]

    def list_patterns(self, station_id: str | None = None) -> List[TrafficPattern]:
        if station_id:
            return [p for p in self.VERIFIED_PATTERNS if p.station_id == station_id]
        return list(self.VERIFIED_PATTERNS)

    def summarize(self, station_id: str | None = None) -> Dict[str, Any]:
        patterns = self.list_patterns(station_id)
        narrative_lines = ["## Pattern Detection Summary\n"]
        for p in patterns:
            narrative_lines.append(
                f"**{p.station_id} — {p.pattern_name}** (confidence {p.confidence:.0%})\n"
                f"- Metric: {p.key_metric}\n"
                f"- Hypothesis: {p.hypothesis}\n"
                f"- Source: `{p.evidence}`\n"
            )
        return {
            "patterns": [p.__dict__ for p in patterns],
            "narrative": "\n".join(narrative_lines),
            "count": len(patterns),
        }
