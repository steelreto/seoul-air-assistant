from fastapi import APIRouter, status

from schemas.conversation import ConversationCreate, ConversationDetail, ConversationSummary
from schemas.data import DeleteResult
from services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(payload: ConversationCreate):
    messages = [m.model_dump() for m in payload.messages]
    return conversation_service.create_conversation(messages, payload.title)


@router.get("", response_model=list[ConversationSummary], summary="대화 목록 조회 (messages 미포함)")
def list_conversations():
    return conversation_service.list_conversations()


@router.get("/{conv_id}", response_model=ConversationDetail, summary="대화 불러오기 (전체 messages)")
def get_conversation(conv_id: str):
    return conversation_service.get_conversation(conv_id)


@router.delete("/{conv_id}", response_model=DeleteResult, summary="대화 삭제")
def delete_conversation(conv_id: str):
    conversation_service.delete_conversation(conv_id)
    return {"id": conv_id, "deleted": True}
