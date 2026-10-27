"""conversations 컬렉션 요청/응답 스키마.

대화 불러오기는 (A) 방식:
  GET /api/conversations      -> 목록만 (messages 미포함, 가볍게)
  GET /api/conversations/{id} -> 전체 messages 포함
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)
    created_at: Optional[str] = None


class ConversationCreate(BaseModel):
    """POST /api/conversations 요청 본문 (수동 저장용)."""
    title: Optional[str] = Field(None, max_length=100)
    messages: list[Message] = Field(..., min_length=1, max_length=200)


class ConversationSummary(BaseModel):
    """목록 응답 한 건. messages는 포함하지 않는다."""
    id: str
    title: str
    message_count: int
    last_message: str = ""
    created_at: str
    updated_at: str


class ConversationDetail(ConversationSummary):
    messages: list[Message]
