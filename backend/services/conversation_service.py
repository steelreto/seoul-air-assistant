"""conversations 컬렉션 비즈니스 로직.

문서 구조
  conversations/{auto_id}
    title: str
    messages: [{role, content, created_at}, ...]
    message_count: int
    created_at, updated_at: ISO 문자열
"""
from datetime import datetime, timezone

from core.errors import NotFoundError
from core.firebase import get_db

COLLECTION = "conversations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _col():
    return get_db().collection(COLLECTION)


def make_title(messages: list[dict]) -> str:
    first = next((m["content"] for m in messages if m["role"] == "user"), "새 대화")
    first = " ".join(first.split())
    return first[:30] + ("…" if len(first) > 30 else "")


def _summary(doc_id: str, data: dict) -> dict:
    messages = data.get("messages", [])
    last = messages[-1]["content"] if messages else ""
    return {
        "id": doc_id,
        "title": data.get("title") or "새 대화",
        "message_count": len(messages),
        "last_message": last[:80],
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }


def list_conversations() -> list[dict]:
    items = [_summary(s.id, s.to_dict() or {}) for s in _col().stream()]
    items.sort(key=lambda c: c["updated_at"], reverse=True)
    return items


def get_conversation(conv_id: str) -> dict:
    snap = _col().document(conv_id).get()
    if not snap.exists:
        raise NotFoundError(f"대화를 찾을 수 없어요: {conv_id}")
    data = snap.to_dict()
    return {**_summary(snap.id, data), "messages": data.get("messages", [])}


def create_conversation(messages: list[dict], title: str | None = None) -> dict:
    now = _now()
    for m in messages:
        m.setdefault("created_at", now)
        if m.get("created_at") is None:
            m["created_at"] = now
    ref = _col().document()
    data = {
        "title": (title or "").strip() or make_title(messages),
        "messages": messages,
        "message_count": len(messages),
        "created_at": now,
        "updated_at": now,
    }
    ref.set(data)
    return {**_summary(ref.id, data), "messages": messages}


def append_messages(conv_id: str, new_messages: list[dict]) -> dict:
    ref = _col().document(conv_id)
    snap = ref.get()
    if not snap.exists:
        raise NotFoundError(f"대화를 찾을 수 없어요: {conv_id}")
    data = snap.to_dict()
    messages = data.get("messages", []) + new_messages
    now = _now()
    ref.update({"messages": messages, "message_count": len(messages), "updated_at": now})
    data.update(messages=messages, updated_at=now)
    return {**_summary(conv_id, data), "messages": messages}


def delete_conversation(conv_id: str) -> None:
    ref = _col().document(conv_id)
    if not ref.get().exists:
        raise NotFoundError(f"대화를 찾을 수 없어요: {conv_id}")
    ref.delete()
