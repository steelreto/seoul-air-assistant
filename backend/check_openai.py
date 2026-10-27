"""OpenAI(또는 호환 API) 연결 점검 스크립트.

backend 폴더에서 실행:  python check_openai.py
키 전체는 출력하지 않고 길이와 앞뒤 몇 글자만 보여 준다.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

raw_key = os.getenv("OPENAI_API_KEY", "")
raw_base = os.getenv("OPENAI_BASE_URL", "")
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

key = raw_key.strip()
base = raw_base.strip().rstrip("/")

print("=== .env 읽은 값 ===")
print(f"OPENAI_API_KEY : 길이 {len(key)}자, 앞 '{key[:7]}…' 뒤 '…{key[-4:]}'" if key else "OPENAI_API_KEY : (비어 있음)")
if raw_key != key:
    print("  ! 키 앞뒤에 공백이나 줄바꿈이 있어요 (코드는 자동으로 제거함)")
if any(c in key for c in "\"' <>"):
    print("  ! 키 안에 따옴표/공백/꺾쇠가 들어 있어요. .env에서 키만 남기세요")
print(f"OPENAI_BASE_URL: {base or '(비어 있음 → OpenAI 공식 서버)'}")
print(f"OPENAI_MODEL   : {model}")

client = OpenAI(api_key=key, base_url=base or None, timeout=30, max_retries=0)
print(f"실제 요청 주소 : {client.base_url}chat/completions")


def show_error(step: str, e: Exception) -> None:
    status = getattr(e, "status_code", "-")
    msg = getattr(e, "message", str(e))
    print(f"[{step}] 실패: {e.__class__.__name__} (HTTP {status})\n  서버 메시지: {msg}")


print("\n=== 1) 모델 목록 조회 ===")
try:
    ids = [m.id for m in client.models.list().data]
    print(f"성공: {len(ids)}개 → {', '.join(ids[:15])}{' …' if len(ids) > 15 else ''}")
    if ids and model not in ids:
        print(f"  ! '{model}'이 목록에 없어요. 위 목록에 있는 이름으로 OPENAI_MODEL을 바꿔 보세요")
except Exception as e:  # 일부 호환 서버는 이 기능을 지원하지 않음 → 2번 결과가 더 중요
    show_error("모델 목록", e)

print("\n=== 2) 채팅 요청 ===")
try:
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "한 단어로 인사해 줘"}],
        max_completion_tokens=300,  # GPT-5 계열은 추론 토큰도 여기에 포함됨
    )
    print("성공:", r.choices[0].message.content)
except Exception as e:
    show_error("채팅", e)
