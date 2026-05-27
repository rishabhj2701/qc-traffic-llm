# PowerPoint — Exact Text Replacements

File: `QC_Traffic_LLM_Phase1_Report (1).pptx`

Copy-paste these into the matching slides.

---

## Slide 9 — Summary

**Stat cards (replace all four numbers/labels):**

```
457          31              25+ yrs           17,057
CSV Files    Primary-Scope   Temporal Span     Peak ADT
             Stations        (to Dec 2025)     (Stn 725)
```

**Key Findings bullets (replace bullet 3):**

```
• 22 of 31 primary-scope stations Pass QC; 5 Critical (16%) must be excluded from operations
```

---

## Slide 10 — Data Quality Assessment

**Tier line:**

```
22 Stations Pass (71%)  |  4 Moderate (13%)  |  5 Critical (16%)
```

**Critical issues (replace bullets):**

```
• Station 717 (Dec 2021): Constant 3,000–6,000 veh/hr → ADT up to 144,000 (synthetic)
• Station 2447-stg: Uniform/sequential test values (synthetic)
• ExportCheckMB: Constant 1 veh/hr → ADT 24 (export artifact)
• Export_CSV_Int: All movements = 24; PHF = 1.00 (test artifact)
• Station 1191: Impossible 141 MPH mean speed vs 36 MPH median; cumulative % = 400%
• Station 725 (Sep 26, 2019): WB classification file has blank count cells (flag file)
```

---

## Slide 6 — UC1 Validation Table

| Query | LLM Answer | Ground Truth | OK |
|-------|------------|--------------|-----|
| ADT 1191 Apr 9 | 8,545 | 8,545 | ✓ |
| INT-0009 PM Peak | 5,708 | 5,708 | ✓ |
| Stn 7 NB vs SB (Mar 7, 2019) | 311 / 312 | 311 / 312 | ✓ |
| Highest ADT station | 725: 17,057 | 725: 17,057 | ✓ |
| Weekday vs Weekend (Stn 7) | 748 vs 235 (−69%) | 748 vs 235 (−69%) | ✓ |

*Footnote: Weekday = Mar 5, 2019; Weekend = Mar 9, 2019 (NB_SB).*

---

## Slide 7 — UC2 footer

Replace: `across 454 files` → **`across 457 files`**

---

## Slide 11 — Inventory (top rows)

| Station | Type | Location | Peak ADT | Data Types | QC Status |
|---------|------|----------|----------|------------|-----------|
| 725 | Midblock | Martha Custis Dr | 17,057 | Vol/Spd/Cls | Moderate |
| 1191 | Midblock | Alexandria, VA | **8,545** | Vol/Spd/Cls | Moderate |
| 7 | Midblock | Timemark Test | 748 | Vol/Spd/Cls | Moderate |
| 718 | Midblock | Chelsea Ct | 1,454 (EB_WB) | Vol only | Pass |

---

## Slide 4 — Recommendation 3

```
Quarantine synthetic/test stations: 2447-stg-test-1-lane, ExportCheckMB, 1234567891, Export_CSV_Int, and Station 717 dates after Nov 2021.
```

---

## Slide 4 — Recommendation 5

```
Expand evaluation to the full staging folder (48 station IDs, 457 files) before production deployment.
```
