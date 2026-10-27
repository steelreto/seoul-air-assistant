"""data 컬렉션 비즈니스 로직 + 시계열 요약(프롬프트 주입용).

라우터는 HTTP 요청/응답만 다루고, 실제 처리(DB 접근, 통계 계산)는 여기서 한다.
chat_service도 요약이 필요할 때 HTTP로 /api/data/summary 를 호출하지 않고
이 모듈의 get_summary()를 직접 호출한다.
"""
import statistics
import time
from datetime import date, datetime, timedelta, timezone

from core.errors import AppError, ConflictError, NotFoundError
from core.firebase import get_db
from schemas.data import DataCreate, DataUpdate

COLLECTION = "data"
UNIT = "㎍/㎥"

# Firestore 읽기 비용을 줄이기 위한 간단한 캐시.
# 채팅 한 번마다 365건을 다시 읽지 않도록, 쓰기(추가/수정/삭제)가 일어나면 비운다.
_CACHE_TTL_SECONDS = 300
_cache: dict = {"records": None, "loaded_at": 0.0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _invalidate_cache() -> None:
    _cache["records"] = None


def _col():
    return get_db().collection(COLLECTION)


def _load_all() -> list[dict]:
    fresh = time.time() - _cache["loaded_at"] < _CACHE_TTL_SECONDS
    if _cache["records"] is not None and fresh:
        return _cache["records"]
    records = []
    for snap in _col().stream():
        item = snap.to_dict() or {}
        item["id"] = snap.id
        item.setdefault("date", snap.id)
        records.append(item)
    records.sort(key=lambda r: r["date"])
    _cache["records"] = records
    _cache["loaded_at"] = time.time()
    return records


# ---------------------------------------------------------------- CRUD

def list_records(start: date | None = None, end: date | None = None,
                 limit: int | None = None, order: str = "asc") -> list[dict]:
    records = _load_all()
    if start:
        records = [r for r in records if r["date"] >= start.isoformat()]
    if end:
        records = [r for r in records if r["date"] <= end.isoformat()]
    if order == "desc":
        records = list(reversed(records))
    if limit:
        records = records[:limit]
    return records


def get_record(record_id: str) -> dict:
    snap = _col().document(record_id).get()
    if not snap.exists:
        raise NotFoundError(f"데이터를 찾을 수 없어요: {record_id}")
    item = snap.to_dict()
    item["id"] = snap.id
    return item


def create_record(payload: DataCreate) -> dict:
    record_id = payload.date.isoformat()  # 날짜를 문서 ID로 사용 -> 같은 날짜 중복 저장 방지
    ref = _col().document(record_id)
    if ref.get().exists:
        raise ConflictError(f"{record_id} 데이터가 이미 있어요. 수정(PUT)을 사용하세요.")
    now = _now()
    data = payload.model_dump(mode="json")
    data.update(created_at=now, updated_at=now)
    ref.set(data)
    _invalidate_cache()
    return {**data, "id": record_id}


def update_record(record_id: str, payload: DataUpdate) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("수정할 값이 없어요.")
    if "value" in changes and changes["value"] is None:
        raise AppError("value(PM2.5)는 비울 수 없어요.")
    if "memo" in changes:
        changes["memo"] = (changes["memo"] or "").strip()

    ref = _col().document(record_id)
    if not ref.get().exists:
        raise NotFoundError(f"데이터를 찾을 수 없어요: {record_id}")
    changes["updated_at"] = _now()
    ref.update(changes)
    _invalidate_cache()
    return get_record(record_id)


def delete_record(record_id: str) -> None:
    ref = _col().document(record_id)
    if not ref.get().exists:
        raise NotFoundError(f"데이터를 찾을 수 없어요: {record_id}")
    ref.delete()
    _invalidate_cache()


# ---------------------------------------------------------------- 요약(분석)

def grade_pm25(v: float) -> str:
    """환경부 초미세먼지 예보 등급"""
    if v <= 15:
        return "좋음"
    if v <= 35:
        return "보통"
    if v <= 75:
        return "나쁨"
    return "매우나쁨"


def _avg(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 1) if values else None


def _group_avg(records: list[dict], key: str, bands: list[tuple[str, float, float]]) -> list[dict]:
    """key 값 구간별 PM2.5 평균. bands = [(라벨, 이상, 미만), ...]"""
    out = []
    for label, lo, hi in bands:
        group = [r["value"] for r in records if r.get(key) is not None and lo <= r[key] < hi]
        if group:
            out.append({"label": label, "days": len(group), "pm25_avg": _avg(group)})
    return out


def _trend(records: list[dict], window: int = 30) -> dict:
    last = date.fromisoformat(records[-1]["date"])
    recent_from = (last - timedelta(days=window)).isoformat()
    prev_from = (last - timedelta(days=window * 2)).isoformat()
    recent = [r["value"] for r in records if r["date"] > recent_from]
    previous = [r["value"] for r in records if prev_from < r["date"] <= recent_from]
    if not previous:  # 데이터가 짧으면 반으로 나눠 비교
        half = len(records) // 2 or 1
        previous = [r["value"] for r in records[:half]]
        recent = [r["value"] for r in records[half:]] or previous

    r_avg, p_avg = _avg(recent), _avg(previous)
    change = round((r_avg - p_avg) / p_avg * 100, 1) if p_avg else 0.0
    if abs(change) < 5:
        label = "유지"
    elif change > 0:
        label = "증가"
    else:
        label = "감소"
    note = {"증가": "공기질 악화", "감소": "공기질 개선", "유지": "큰 변화 없음"}[label]
    sign = "+" if change > 0 else ""
    return {
        "label": label,
        "window_days": window,
        "recent_avg": r_avg,
        "previous_avg": p_avg,
        "change_pct": change,
        "text": f"{label} ({note}) — 최근 {window}일 평균 {r_avg}{UNIT}, "
                f"직전 {window}일 {p_avg}{UNIT} 대비 {sign}{change}%",
    }


def _brief(r: dict) -> dict:
    return {k: r.get(k) for k in ("date", "value", "pm10", "temp_avg", "rain", "wind", "humidity", "memo")}


def get_summary() -> dict:
    records = [r for r in _load_all() if r.get("value") is not None]
    if not records:
        return {"period": None, "count": 0, "metrics": {}, "trend": {"label": "데이터 없음", "text": "데이터 없음"}}

    values = [r["value"] for r in records]
    max_r = max(records, key=lambda r: r["value"])
    min_r = min(records, key=lambda r: r["value"])

    grade_days = {"좋음": 0, "보통": 0, "나쁨": 0, "매우나쁨": 0}
    for v in values:
        grade_days[grade_pm25(v)] += 1

    months: dict[str, list[dict]] = {}
    for r in records:
        months.setdefault(r["date"][:7], []).append(r)
    monthly = [{
        "month": m,
        "days": len(rs),
        "pm25_avg": _avg(r["value"] for r in rs),
        "pm10_avg": _avg(r.get("pm10") for r in rs),
        "temp_avg": _avg(r.get("temp_avg") for r in rs),
        "rain_total": round(sum(r.get("rain") or 0 for r in rs), 1),
    } for m, rs in sorted(months.items())]

    by_value = sorted(records, key=lambda r: r["value"])

    return {
        "period": f"{records[0]['date']} ~ {records[-1]['date']}",
        "count": len(records),
        "metric": {"name": "초미세먼지(PM2.5)", "unit": UNIT},
        "metrics": {
            "average": _avg(values),
            "median": round(statistics.median(values), 1),
            "max": max_r["value"],
            "max_date": max_r["date"],
            "min": min_r["value"],
            "min_date": min_r["date"],
            "pm10_average": _avg(r.get("pm10") for r in records),
            "temp_average": _avg(r.get("temp_avg") for r in records),
        },
        "grade_days": grade_days,
        "trend": _trend(records),
        "latest": _brief(records[-1]),
        "monthly": monthly,
        "worst_days": [_brief(r) for r in reversed(by_value[-5:])],
        "best_days": [_brief(r) for r in by_value[:3]],
        "weather_relation": {
            "by_temp": _group_avg(records, "temp_avg", [
                ("0℃ 미만", -99, 0), ("0~10℃", 0, 10), ("10~20℃", 10, 20), ("20℃ 이상", 20, 99)]),
            "by_rain": _group_avg(records, "rain", [
                ("비 안 온 날(1mm 미만)", 0, 1), ("비 온 날(1mm 이상)", 1, 9999)]),
            "by_wind": _group_avg(records, "wind", [
                ("약한 바람(2m/s 미만)", 0, 2), ("보통 바람(2~3m/s)", 2, 3), ("강한 바람(3m/s 이상)", 3, 99)]),
        },
        "memos": [{"date": r["date"], "memo": r["memo"], "value": r["value"]}
                  for r in records if r.get("memo")][-20:],
    }
