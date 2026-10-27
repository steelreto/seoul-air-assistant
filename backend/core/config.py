"""환경변수를 한 곳에서 읽어 오는 설정 모듈.

키나 URL을 코드에 직접 쓰지 않고, 여기서만 os.getenv로 꺼내 쓴다.
로컬에서는 backend/.env 파일, 배포 환경(Render)에서는 대시보드의 Environment 값이 사용된다.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # backend/.env 가 있으면 읽음 (배포 환경에서는 파일이 없어도 됨)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        # OpenAI
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
        # OpenAI 호환 API(예: 교육기관 제공 프록시)를 쓸 때만 설정. 비우면 OpenAI 공식 서버 사용
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "").strip().rstrip("/")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "500"))
        self.chat_history_limit: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))

        # Firebase: JSON 문자열(배포용) 또는 파일 경로(로컬용) 중 하나
        self.firebase_json: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        self.firebase_path: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()

        # Firebase 없이 로컬 개발할 때만 사용하는 메모리 DB (서버를 끄면 데이터가 사라짐)
        self.use_memory_db: bool = _bool("USE_MEMORY_DB")

        # CORS: 쉼표로 구분한 허용 도메인 목록
        origins = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080",
        )
        self.allowed_origins: list[str] = [o.strip().rstrip("/") for o in origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
