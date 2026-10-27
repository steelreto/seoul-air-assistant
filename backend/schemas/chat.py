from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, examples=["1월에 공기가 제일 나빴던 날은?"])
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 때 기존 대화 ID")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지가 비어 있어요")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    title: str
    reply: str
    model: str
