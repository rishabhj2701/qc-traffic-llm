import glob
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "traffic_data.db"

_COLUMN_RE = re.compile(r"[^0-9a-zA-Z_]+")
_TABLE_RE = re.compile(r"[^0-9a-zA-Z_]+")


def _normalize_column_name(column_name: str) -> str:
    value = "" if column_name is None else str(column_name)
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = value.lower()
    value = _COLUMN_RE.sub("_", value)
    value = re.sub(r"__+", "_", value).strip("_")
    if not value:
        value = "column"
    if value[0].isdigit():
        value = f"c_{value}"
    return value


def _sanitize_table_name(name: str) -> str:
    base = "" if name is None else str(name)
    base = base.replace("\u00a0", " ")
    base = re.sub(r"\s+", " ", base).strip()
    base = base.lower()
    base = _TABLE_RE.sub("_", base)
    base = re.sub(r"__+", "_", base).strip("_")
    if not base:
        base = "table"
    if base[0].isdigit():
        base = f"t_{base}"
    return base


def _infer_sqlite_type(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    if pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TEXT"
    # Fallback: if all values are integers in strings, treat as INTEGER
    values = series.dropna().astype(str).str.strip()
    if not values.empty and values.map(lambda v: v.isdigit()).all():
        return "INTEGER"
    return "TEXT"


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_column_name(col) for col in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda v: str(v).strip() if pd.notna(v) else None)

    df = df.where(pd.notnull(df), None)
    return df


def _prepare_table_name(base_name: str, existing_names: List[str]) -> str:
    base = _sanitize_table_name(base_name)
    if base not in existing_names:
        return base
    index = 1
    while f"{base}_{index}" in existing_names:
        index += 1
    return f"{base}_{index}"


def _create_metadata_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_metadata (
            table_name TEXT PRIMARY KEY,
            columns_json TEXT,
            source_files_json TEXT,
            created_at TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT,
            table_name TEXT,
            source_type TEXT,
            loaded_at TEXT
        );
        """
    )
    conn.commit()


def _create_table_for_dataframe(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    columns = []
    for column in df.columns:
        col_type = _infer_sqlite_type(df[column])
        columns.append(f"\"{column}\" {col_type}")
    create_sql = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" ({', '.join(columns)});"
    conn.execute(create_sql)
    conn.commit()


def _insert_dataframe(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    columns = [f"\"{col}\"" for col in df.columns]
    placeholders = ["?" for _ in df.columns]
    insert_sql = f"INSERT INTO \"{table_name}\" ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

    values = [tuple(row) for row in df.itertuples(index=False, name=None)]
    conn.executemany(insert_sql, values)
    conn.commit()
    return len(values)


def load_schema_metadata(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Return a dictionary of schema metadata for all tables in the SQLite database."""
    if not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    table_names = [row[0] for row in cursor.fetchall()]
    metadata: Dict[str, Any] = {}
    excluded = {"schema_metadata", "source_files"}

    for table_name in table_names:
        if table_name in excluded:
            continue
        cursor.execute(f"PRAGMA table_info(\"{table_name}\")")
        columns = [(row[1], row[2]) for row in cursor.fetchall()]
        cursor.execute(f"SELECT * FROM \"{table_name}\" LIMIT 3")
        sample_rows = [dict(zip([col[0] for col in columns], row)) for row in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
        row_count = cursor.fetchone()[0]
        metadata[table_name] = {
            "columns": columns,
            "sample_rows": sample_rows,
            "row_count": row_count,
        }

    conn.close()
    return metadata


def _smart_read_csv(file_path: str) -> pd.DataFrame:
    """Read a CSV file by detecting where the actual header starts and extracting metadata."""
    # Read first 30 lines to find the header and metadata
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [f.readline() for _ in range(30)]
    
    header_idx = 0
    metadata = {}
    
    for i, line in enumerate(lines):
        # Extract metadata like "Direction:", "Station ID:", "Agency:"
        if ":" in line and line.count(",") >= 1:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 2 and parts[0].endswith(":"):
                key = parts[0].strip(":")
                val = parts[1]
                if val:
                    metadata[key] = val
                    
        if "Start Time" in line or "Interval Start" in line or "Time" in line:
            if line.count(",") >= 2:
                header_idx = i
                break
                
    # Read the CSV starting from the detected header
    df = pd.read_csv(file_path, skiprows=header_idx, dtype=object, low_memory=False)
    
    # Skip potential empty metadata row after header
    if not df.empty and df.iloc[0].isna().sum() > (len(df.columns) / 2):
        df = df.iloc[1:].reset_index(drop=True)
        
    # Add metadata as columns
    for key, val in metadata.items():
        col_name = _normalize_column_name(key)
        if col_name not in df.columns:
            df[col_name] = val
            
    return df


def build_db_from_files(data_dirs: List[str], db_path: str = DB_PATH) -> str:
    """
    Scan CSV/XLSX files in data_dirs, normalize them, and load them into SQLite.
    Returns the database path.
    """
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    _create_metadata_tables(conn)

    existing_tables = []
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing_tables = [row[0] for row in cursor.fetchall()]

    for data_dir in data_dirs:
        if not os.path.isdir(data_dir):
            continue
        for file_name in sorted(os.listdir(data_dir)):
            if file_name.startswith(("~$", ".")):
                continue
            file_path = os.path.join(data_dir, file_name)
            if os.path.isdir(file_path):
                continue
            ext = Path(file_path).suffix.lower()
            source_type = "xlsx" if ext == ".xlsx" else "csv" if ext == ".csv" else None
            if source_type is None:
                continue

            try:
                if source_type == "xlsx":
                    xls = pd.ExcelFile(file_path, engine="openpyxl")
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
                        table_name = _prepare_table_name(f"{Path(file_name).stem}_{sheet_name}", existing_tables)
                        df = _normalize_dataframe(df)
                        _create_table_for_dataframe(conn, table_name, df)
                        inserted = _insert_dataframe(conn, table_name, df)
                        existing_tables.append(table_name)
                        conn.execute(
                            "INSERT OR REPLACE INTO source_files (source_path, table_name, source_type, loaded_at) VALUES (?, ?, ?, ?)"
                            , (file_path, table_name, source_type, datetime.utcnow().isoformat())
                        )
                else:
                    df = _smart_read_csv(file_path)
                    table_name = _prepare_table_name(Path(file_name).stem, existing_tables)
                    df = _normalize_dataframe(df)
                    _create_table_for_dataframe(conn, table_name, df)
                    inserted = _insert_dataframe(conn, table_name, df)
                    existing_tables.append(table_name)
                    conn.execute(
                        "INSERT OR REPLACE INTO source_files (source_path, table_name, source_type, loaded_at) VALUES (?, ?, ?, ?)"
                        , (file_path, table_name, source_type, datetime.utcnow().isoformat())
                    )
                conn.commit()
            except Exception as exc:
                print(f"[WARN] Could not ingest {file_path}: {exc}")

    conn.close()
    return db_path
