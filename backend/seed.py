"""전처리한 CSV를 Firestore data 컬렉션에 한 번에 올리는 스크립트.

실행 (backend 폴더에서, .env에 Firebase 키 설정 후)
  python seed.py
  python seed.py --csv ../data/seoul_air_2025.csv

같은 날짜(문서 ID)는 덮어쓴다. 여러 번 실행해도 중복이 생기지 않는다.
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "seoul_air_2025.csv"
NUMERIC = ["value", "pm10", "temp_avg", "temp_min", "temp_max", "rain", "wind", "humidity"]


def read_rows(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = {"date": raw["date"], "memo": (raw.get("memo") or "").strip()}
            for key in NUMERIC:
                v = (raw.get(key) or "").strip()
                row[key] = float(v) if v else None
            rows.append(row)
    return rows


def seed_from_csv(db, csv_path: Path = DEFAULT_CSV) -> int:
    rows = read_rows(csv_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    col = db.collection("data")
    batch, n = db.batch(), 0
    for row in rows:
        batch.set(col.document(row["date"]), {**row, "created_at": now, "updated_at": now})
        n += 1
        if n % 400 == 0:  # Firestore batch 한도(500) 안쪽에서 나눠 커밋
            batch.commit()
            batch = db.batch()
    batch.commit()
    return n


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    from core.firebase import get_backend, init_db, get_db

    init_db()
    count = seed_from_csv(get_db(), args.csv)
    print(f"[{get_backend()}] data 컬렉션에 {count}건 업로드 완료")
