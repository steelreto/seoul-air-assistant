from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Query, status

from schemas.data import DataCreate, DataOut, DataUpdate, DeleteResult
from services import data_service

router = APIRouter(prefix="/api/data", tags=["data"])


# /summary 는 /{record_id} 보다 먼저 선언해야 'summary'가 ID로 해석되지 않는다.
@router.get("/summary", summary="데이터 요약 (프롬프트 주입용)")
def get_summary():
    return data_service.get_summary()


@router.get("", response_model=list[DataOut], summary="데이터 목록 조회")
def list_data(
    start: Optional[date] = Query(None, description="시작일 (포함)"),
    end: Optional[date] = Query(None, description="종료일 (포함)"),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    order: Literal["asc", "desc"] = "asc",
):
    return data_service.list_records(start, end, limit, order)


@router.post("", response_model=DataOut, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(payload: DataCreate):
    return data_service.create_record(payload)


@router.get("/{record_id}", response_model=DataOut, summary="데이터 1건 조회")
def get_data(record_id: str):
    return data_service.get_record(record_id)


@router.put("/{record_id}", response_model=DataOut, summary="데이터 수정")
def update_data(record_id: str, payload: DataUpdate):
    return data_service.update_record(record_id, payload)


@router.delete("/{record_id}", response_model=DeleteResult, summary="데이터 삭제")
def delete_data(record_id: str):
    data_service.delete_record(record_id)
    return {"id": record_id, "deleted": True}
