"""
Phase 1 verified constants — aligned with final report & presentation.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "datasets"
DB_PATH = Path(__file__).resolve().parents[1] / "traffic_data.db"

TOTAL_CSV_FILES = 457
FOLDER_STATION_IDS = 48
PRIMARY_SCOPE_STATIONS = 31
MIDBLOCK_COUNT = 9
INT_SERIES_COUNT = 20

AGENCY = "Staging 2 - Alexandriava"
CITY = "Alexandria, Virginia"

PEAK_REAL_ADT = 17057
PEAK_REAL_STATION = "725"
PEAK_REAL_DATE = "Sep 27 2019"
PEAK_REAL_DIRECTION = "EB_WB"

CRITICAL_STATIONS = [
    "2447-stg-test-1-lane",
    "ExportCheckMB",
    "1234567891",
    "Export_CSV_Int",
    "717",
]

MODERATE_STATIONS = ["725", "1191", "7", "ClassOnly"]

INT_SERIES_IDS = [
    f"INT-{i:04d}"
    for i in list(range(2, 10)) + list(range(11, 23))
]

BENCHMARK_QUERIES = [
    {
        "id": "uc1_q1",
        "question": "What is the ADT for Station 1191 on April 9, 2025 in the NB_SB direction?",
        "expected": "8545",
    },
    {
        "id": "uc1_q2",
        "question": "What is the PM peak total entering volume for INT-0009 on October 16, 2012?",
        "expected": "5708",
    },
    {
        "id": "uc1_q3",
        "question": "What are the ADT values for Station 7 NB and SB on March 7, 2019?",
        "expected": "311 NB, 312 SB",
    },
    {
        "id": "uc1_q4",
        "question": "Which station has the highest verified real-world ADT in the dataset?",
        "expected": "725: 17057",
    },
    {
        "id": "uc1_q5",
        "question": "Compare weekday vs weekend ADT for Station 7 (NB_SB).",
        "expected": "748 vs 235 (~69% lower weekend)",
    },
]
