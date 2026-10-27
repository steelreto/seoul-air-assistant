"""Firestore 클라이언트 초기화.

서비스 계정 키는 환경변수로만 받는다.
  - FIREBASE_SERVICE_ACCOUNT_JSON : 키 JSON 전체를 한 줄 문자열로 (Render 배포용)
  - FIREBASE_SERVICE_ACCOUNT_PATH : 키 파일 경로 (로컬 개발용, 파일은 .gitignore 처리)
둘 다 없고 USE_MEMORY_DB=true 이면 메모리 DB를 쓴다.
"""
import json
import logging

from core.config import get_settings

logger = logging.getLogger(__name__)

_db = None
_backend = None


def _init_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore

    settings = get_settings()
    if settings.firebase_json:
        info = json.loads(settings.firebase_json)
        # 환경변수에 붙여넣을 때 private_key 줄바꿈이 '\\n' 문자로 바뀌는 경우 복구
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(info)
    else:
        cred = credentials.Certificate(settings.firebase_path)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()


def init_db() -> str:
    """앱 시작 시 한 번 호출. 사용 중인 DB 종류를 반환한다."""
    global _db, _backend
    settings = get_settings()

    if settings.firebase_json or settings.firebase_path:
        _db = _init_firestore()
        _backend = "firestore"
    elif settings.use_memory_db:
        from core.memory_db import MemoryClient

        _db = MemoryClient()
        _backend = "memory"
        logger.warning("USE_MEMORY_DB=true: 메모리 DB 사용 중 (서버 재시작 시 데이터 초기화)")
    else:
        raise RuntimeError(
            "Firebase 설정이 없어요. FIREBASE_SERVICE_ACCOUNT_JSON 또는 "
            "FIREBASE_SERVICE_ACCOUNT_PATH 를 설정하거나, 로컬 테스트라면 USE_MEMORY_DB=true 로 실행하세요."
        )
    return _backend


def get_db():
    if _db is None:
        init_db()
    return _db


def get_backend() -> str | None:
    return _backend
