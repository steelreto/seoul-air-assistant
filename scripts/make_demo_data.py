"""프론트 데모 모드용 demo-data.js 생성.

백엔드의 요약 함수를 그대로 써서, 서버 없이도 같은 요약이 화면에 나오게 한다.
실행 (프로젝트 루트에서): python scripts/make_demo_data.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ["USE_MEMORY_DB"] = "true"
os.environ.pop("FIREBASE_SERVICE_ACCOUNT_JSON", None)
os.environ.pop("FIREBASE_SERVICE_ACCOUNT_PATH", None)

from core.firebase import get_db, init_db  # noqa: E402
from seed import read_rows, seed_from_csv  # noqa: E402
from services.data_service import get_summary  # noqa: E402

init_db()
seed_from_csv(get_db())
records = read_rows(ROOT / "data" / "seoul_air_2025.csv")
payload = {"records": records, "summary": get_summary()}
out = ROOT / "frontend" / "demo-data.js"
out.write_text("// scripts/make_demo_data.py 로 생성한 예시 데이터 (데모 모드 전용)\nwindow.DEMO_DATA = "
               + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
print(f"생성: {out} ({out.stat().st_size // 1024}KB, {len(records)}건)")
