"""data 컬렉션 요청/응답 스키마.

Pydantic이 요청 본문을 자동으로 검증하므로, 잘못된 값(음수 농도, 습도 120% 등)은
서비스 코드에 도달하기 전에 422 에러로 거절된다.
"""
from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _DataFields(BaseModel):
    value: float = Field(..., ge=0, le=1000, description="초미세먼지(PM2.5) 일평균, ㎍/㎥", examples=[18.5])
    pm10: Optional[float] = Field(None, ge=0, le=2000, description="미세먼지(PM10) 일평균, ㎍/㎥")
    temp_avg: Optional[float] = Field(None, ge=-40, le=50, description="평균기온, ℃")
    temp_min: Optional[float] = Field(None, ge=-40, le=50, description="최저기온, ℃")
    temp_max: Optional[float] = Field(None, ge=-40, le=50, description="최고기온, ℃")
    rain: Optional[float] = Field(None, ge=0, le=1000, description="일강수량, mm")
    wind: Optional[float] = Field(None, ge=0, le=60, description="평균 풍속, m/s")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="평균 상대습도, %")
    memo: str = Field("", max_length=200, description="메모 (예: 황사 특보)")

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: str) -> str:
        return v.strip()


class DataCreate(_DataFields):
    """POST /api/data 요청 본문. date가 문서 ID가 된다(같은 날짜 중복 방지)."""
    date: Date = Field(..., description="측정일 (YYYY-MM-DD)", examples=["2026-01-15"])


class DataUpdate(BaseModel):
    """PUT /api/data/{id} 요청 본문. 보낸 필드만 수정한다. date(=ID)는 수정 불가."""
    model_config = ConfigDict(extra="forbid")

    value: Optional[float] = Field(None, ge=0, le=1000)
    pm10: Optional[float] = Field(None, ge=0, le=2000)
    temp_avg: Optional[float] = Field(None, ge=-40, le=50)
    temp_min: Optional[float] = Field(None, ge=-40, le=50)
    temp_max: Optional[float] = Field(None, ge=-40, le=50)
    rain: Optional[float] = Field(None, ge=0, le=1000)
    wind: Optional[float] = Field(None, ge=0, le=60)
    humidity: Optional[float] = Field(None, ge=0, le=100)
    memo: Optional[str] = Field(None, max_length=200)


class DataOut(_DataFields):
    id: str
    date: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DeleteResult(BaseModel):
    id: str
    deleted: bool = True
