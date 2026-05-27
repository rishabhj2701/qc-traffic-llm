# Phase 1 Submission Checklist — QC Traffic LLM Project

**Iowa State University | Anuj Sharma | May 2025**

Use this checklist before submitting the **final report**, **presentation**, **codebase**, and **proposal**.

---

## What to submit (4 items)

| # | Item | Path / file | Status |
|---|------|-------------|--------|
| 1 | Final report (Word/PDF) | `Phase1_Final_Report_QC_Traffic_LLM.docx` | ⚠️ Apply corrections below |
| 2 | Final presentation | `QC_Traffic_LLM_Phase1_Report (1).pptx` | ⚠️ Apply slide fixes below |
| 3 | Codebase | `AI4CCEE/sql_rag/` + `AI4CCEE/datasets/` (457 CSVs) | ⚠️ Rebuild DB, run setup |
| 4 | Proposal | Your original proposal PDF/DOCX | ✓ Attach unchanged unless scope changed |

---

## Verified dataset facts (use everywhere)

| Metric | Correct value |
|--------|----------------|
| CSV files | **457** (not 454) |
| Station IDs in folder | **48** |
| Phase 1 primary scope | **31 stations** (9 midblock + 20 INT-series + 2 test intersections) |
| Peak real ADT | **17,057** — Station **725**, Sep 27, 2019, EB_WB |
| Latest folder date | **Dec 3, 2025** (Station 168); latest key midblock ops data **Apr 2025** (1191) |
| Critical / exclude stations | 2447-stg-test-1-lane, ExportCheckMB, 1234567891, Export_CSV_Int, 717 (synthetic dates) |
| QC tiers (31 stations) | **22 Pass (71%)**, **4 Moderate (13%)**, **5 Critical (16%)** |

---

## Report corrections (Word doc)

Apply the replacement text from the prior review session, especially:

- [ ] 454 → **457** files (global find-replace)
- [ ] 26 stations (9+17) → **31 primary-scope** (9 midblock + 22 intersection in scope)
- [ ] QC table: **22 Pass + 4 Moderate + 5 Critical = 31** (not 22+3+5=30)
- [ ] ExportCheckMB: **1 veh/hr**, ADT **24** (not 2/hr, ADT 48)
- [ ] 1191 ADT: **8,545** (not 8,744); mean speed **141 MPH** (not 125)
- [ ] 725 Sep 26: **blank cells**, not “0 bytes”
- [ ] Add **ClassOnly** to midblock inventory
- [ ] UC1: “**5/5 benchmark queries**” not “100% on all queries”

---

## Presentation corrections (12 slides)

### Slide 9 — Summary (biggest impact)

| Was | Should be |
|-----|-----------|
| 454 CSV Files | **457** CSV Files |
| 26 Stations | **31** primary-scope (48 in folder) |
| 22 stations pass QC | **22 Pass (71%)** of 31 — **5 Critical (16%)** |
| (optional) 25 yrs | Mar 2000 – **Dec 2025** (folder); Apr 2025 for 1191 |

### Slide 10 — Data Quality

| Was | Should be |
|-----|-----------|
| 22 Pass (73%) / 3 Moderate / 5 Critical | **22 / 4 / 5** on **31 stations** |
| ExportCheckMB: constant **2** veh/hr | constant **1** veh/hr, ADT **24** |
| 1191: **125 MPH** | **141 MPH** mean (median **36 MPH**) |
| 454 files (slide 7 footer) | **457 files** |

### Slide 6 — UC1 validation table

| Query | Was | Should be |
|-------|-----|-----------|
| ADT 1191 Apr 9 | 8,744 ✓ | **8,545** ✓ |
| INT-0009 PM Peak | 5,708 @ **5:30PM** | 5,708 ✓ @ **6:15 PM** (or drop time) |
| Stn 7 NB vs SB | 311 / **313** | **311 / 312** (Mar 7, 2019) |
| Weekday vs Weekend | 624 vs 195 | **748 vs 235** (Mar 5 vs Mar 9, 2019) OR footnote dates |

### Slide 11 — Inventory table

- 1191 Peak ADT: **8,545** (not 8,744)
- Add footnote: **48 station IDs** in folder; table shows primary scope

### Slide 4 — Recommendations

- Item 3: add **Export_CSV_Int**, **1234567891**
- Item 5: “Expand to **full 48-station** staging folder” (not only 26)

---

## Codebase before submit

The repo is structured as a **Phase 1 POC** matching the presentation architecture (`sql_rag/pipeline/`).

```bash
cd /path/to/AI4CCEE
source .venv/bin/activate
pip install -r sql_rag/requirements.txt

python sql_rag/setup_database.py
ls -lh sql_rag/traffic_data.db          # ~12MB+, 457 source_files

# Offline demos (no API key) - good for live presentation
python sql_rag/run_poc.py --qc
python sql_rag/run_poc.py --patterns
streamlit run sql_rag/frontend.py

# Grounded queries (needs OPENAI_API_KEY in sql_rag/.env)
python sql_rag/run_poc.py -q "Highest ADT station?"
python sql_rag/run_poc.py --benchmark
```

- [ ] `sql_rag/traffic_data.db` ingested (**457** files)
- [ ] `sql_rag/ARCHITECTURE.md` included in zip
- [ ] Demo: **QC Narratives** + **Pattern Detection** work without API
- [ ] **Query Interface** shows pipeline trace (Intent → … → Evaluation)
- [ ] **Methodology Compare** page: Grounded vs Direct LLM

---

## Slide order note

Your deck may show slides out of narrative order in the XML (e.g. “Thank You” as slide 3). Before submitting, reorder in PowerPoint to:

1. Title  
2. Project Overview  
3. Data Inventory  
4. Data Quality  
5. UC1 / UC2 / UC3  
6. Methodology  
7. Summary  
8. Recommendations  
9. Architecture (Phase 2)  
10. Thank You  

---

## Honest framing (avoid over-claiming)

| Claim | Safer wording |
|-------|----------------|
| “100% accuracy” | “**100% on 5 verified benchmark queries**” |
| “~99% on all structured queries” | “**95–99%** on grounded benchmark; **5-query** pilot” |
| “~40% time savings” | “**Estimated ~40%** reduction in manual QC inspection (pilot)” |
| “6 anomalies across 454 files” | “**6 critical anomaly types** identified across **457 files**” |

---

## Final sign-off

- [ ] Report, slides, and code use **same numbers** (457, 31, 8,545, 17,057, etc.)
- [ ] Proposal scope matches what you delivered (3 use cases, grounded architecture)
- [ ] PDF export of report + PDF of slides for committee archive
- [ ] Zip: `ISU_Phase1_QC_Traffic_LLM_submission.zip` containing report, slides, proposal, `sql_rag/`, `datasets/` (or link to data)

**Do not submit until Slides 6, 9, 10 and Report Section 3 match this checklist.**
