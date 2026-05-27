import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sql_rag.ingestion.build_db import build_db_from_files

DB_PATH = str(Path(__file__).resolve().parent / "traffic_data.db")


def main(db_path: str = DB_PATH, data_dirs: List[str] = None) -> str:
    if data_dirs is None:
        data_dirs = [str(Path(__file__).resolve().parents[1] / "datasets")]
    db_path = str(Path(db_path).resolve())
    build_db_from_files(data_dirs, db_path=db_path)
    print(f"Database created or updated at {db_path}")
    return db_path


if __name__ == "__main__":
    main()
