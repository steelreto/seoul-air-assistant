from fastapi import APIRouter

from schemas.chat import ChatRequest, ChatResponse
from services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="AI 채팅 (요약 주입 + 자동 저장)")
def chat(payload: ChatRequest):
    return chat_service.chat(payload.message, payload.conversation_id)
