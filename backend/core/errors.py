"""서비스 계층에서 쓰는 예외.

서비스는 HTTP를 모르게 두고(라우터/서비스 분리), main.py에서 HTTP 응답으로 바꾼다.
"""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ExternalServiceError(AppError):
    """OpenAI 등 외부 서비스 호출 실패"""
    status_code = 502


class NotConfiguredError(AppError):
    """필요한 환경변수가 설정되지 않음"""
    status_code = 503
