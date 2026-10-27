"""AI 채팅 = 컨텍스트 주입.

GPT는 사용자의 데이터를 모른다. 그래서 매 요청마다
  1) 데이터 요약을 계산하고
  2) 그 요약을 시스템 프롬프트에 글로 넣어서
  3) GPT가 '이미 알고 있는 것처럼' 답하게 만든다.
마지막으로 질문과 답변을 conversations에 자동 저장한다.
"""
from datetime import datetime, timezone

from core.config import get_settings
from core.errors import ExternalServiceError, NotConfiguredError
from services import conversation_service, data_service

_client = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fmt(v, unit: str = "") -> str:
    return "-" if v is None else f"{v}{unit}"


def build_system_prompt(s: dict) -> str:
    if not s.get("count"):
        return ("당신은 '서울 대기질 AI 비서'입니다. 아직 저장된 데이터가 없습니다. "
                "데이터 관리 화면에서 데이터를 먼저 추가해 달라고 안내하세요.")

    u = s["metric"]["unit"]
    m = s["metrics"]
    g = s["grade_days"]
    latest = s["latest"]

    monthly = "\n".join(
        f"  - {x['month']}: PM2.5 {_fmt(x['pm25_avg'])} / PM10 {_fmt(x['pm10_avg'])} {u}, "
        f"평균기온 {_fmt(x['temp_avg'], '℃')}, 강수 합계 {_fmt(x['rain_total'], 'mm')}"
        for x in s["monthly"]
    )

    def day_line(d: dict) -> str:
        line = (f"  - {d['date']}: PM2.5 {d['value']}{u} (PM10 {_fmt(d['pm10'])}), "
                f"기온 {_fmt(d['temp_avg'], '℃')}, 풍속 {_fmt(d['wind'], 'm/s')}, 강수 {_fmt(d['rain'], 'mm')}")
        return line + (f", 메모: {d['memo']}" if d.get("memo") else "")

    worst = "\n".join(day_line(d) for d in s["worst_days"])
    best = "\n".join(day_line(d) for d in s["best_days"])

    wr = s["weather_relation"]

    def rel(items: list[dict]) -> str:
        return ", ".join(f"{i['label']} {i['pm25_avg']}{u}({i['days']}일)" for i in items) or "-"

    memos = "\n".join(f"  - {x['date']}: {x['memo']} (PM2.5 {x['value']}{u})" for x in s["memos"]) or "  - 없음"

    return f"""당신은 '서울 대기질 AI 비서'입니다. 사용자가 저장한 서울 일별 대기질·기상 데이터를 근거로 답합니다.

[사용자 데이터 요약]
- 데이터 기간: {s['period']}
- 총 레코드: {s['count']}개 (하루 1건, 서울 25개 자치구 측정소 평균 + 기상청 서울 관측소)
- 주요 지표 — 초미세먼지(PM2.5, {u}):
  평균 {m['average']}, 중앙값 {m['median']}, 최고 {m['max']} ({m['max_date']}), 최저 {m['min']} ({m['min_date']})
  참고: 미세먼지(PM10) 평균 {_fmt(m['pm10_average'])}{u}, 평균기온 {_fmt(m['temp_average'], '℃')}
- 등급별 일수 (환경부 기준 좋음 0~15 / 보통 16~35 / 나쁨 36~75 / 매우나쁨 76 이상):
  좋음 {g['좋음']}일, 보통 {g['보통']}일, 나쁨 {g['나쁨']}일, 매우나쁨 {g['매우나쁨']}일
- 최근 트렌드: {s['trend']['text']}
- 가장 최근 기록:
{day_line(latest)}
- 월별 평균:
{monthly}
- 초미세먼지가 가장 높았던 날 Top 5:
{worst}
- 가장 낮았던 날 Top 3:
{best}
- 기상 조건별 PM2.5 평균:
  기온별: {rel(wr['by_temp'])}
  강수별: {rel(wr['by_rain'])}
  풍속별: {rel(wr['by_wind'])}
- 사용자가 남긴 메모:
{memos}

[답변 규칙]
1. 위 요약의 수치만 근거로 답하고, 숫자에는 단위({u}, ℃, mm, m/s)를 붙이세요.
2. 요약에 없는 세부 정보(특정 날짜의 값 등)는 추측하지 말고 "요약 데이터에는 없어요"라고 말한 뒤 '데이터 관리' 화면에서 확인하도록 안내하세요.
3. 이 데이터는 실시간이 아니라 저장된 기록입니다. "오늘", "이번 달", "요즘" 같은 질문은 가장 최근 기록 날짜를 밝히고 그 시점 기준으로 답하세요.
4. 원인을 설명할 때는 기상 조건별 평균처럼 데이터 근거를 들고, 단정하지 말고 "~한 경향이 있어요"처럼 표현하세요.
5. 한국어로 2~5문장, 친절하고 간결하게 답하세요. 건강 관련 질문에는 일반적인 행동 요령만 짧게 덧붙이세요.
6. 채팅 화면은 마크다운을 표시하지 않습니다. **, #, 표 같은 마크다운 기호 없이 일반 문장으로 쓰세요."""


def _get_client():
    global _client
    settings = get_settings()
    if not settings.openai_api_key:
        raise NotConfiguredError("OPENAI_API_KEY가 설정되지 않았어요. 서버 환경변수를 확인하세요.")
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,  # None이면 OpenAI 공식 주소
            timeout=30,
            max_retries=1,
        )
    return _client


def _detail(e: Exception) -> str:
    """외부 API가 돌려준 오류 문구 (디버깅용, 너무 길면 자름)"""
    return str(getattr(e, "message", e))[:200]


def _create(client, settings, messages: list[dict], token_param: str):
    return client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        **{token_param: settings.openai_max_tokens},  # 답변 길이(비용) 제한
    )


def call_llm(messages: list[dict]) -> str:
    """GPT 호출. 테스트에서 이 함수만 바꿔 끼우면 실제 과금 없이 흐름을 검증할 수 있다."""
    import openai

    settings = get_settings()
    client = _get_client()
    try:
        try:
            resp = _create(client, settings, messages, "max_completion_tokens")
        except openai.BadRequestError as e:
            # 일부 OpenAI 호환 서버는 예전 파라미터 이름(max_tokens)만 받는다
            if "max_completion_tokens" not in str(e):
                raise
            resp = _create(client, settings, messages, "max_tokens")
    except openai.NotFoundError as e:
        raise ExternalServiceError(
            f"모델 '{settings.openai_model}'을 찾을 수 없어요. OPENAI_MODEL 또는 OPENAI_BASE_URL을 확인하세요."
        ) from e
    except openai.AuthenticationError as e:
        raise ExternalServiceError(f"OpenAI 인증 실패: API 키나 OPENAI_BASE_URL을 확인하세요. ({_detail(e)})") from e
    except openai.RateLimitError as e:
        raise ExternalServiceError(f"OpenAI 사용량 한도 초과 또는 잔액 부족이에요. ({_detail(e)})") from e
    except openai.APIError as e:
        raise ExternalServiceError(f"OpenAI 호출 실패: {e.__class__.__name__} ({_detail(e)})") from e

    reply = (resp.choices[0].message.content or "").strip()
    if not reply:
        raise ExternalServiceError("AI가 빈 응답을 보냈어요. 잠시 후 다시 시도해 주세요.")
    return reply


def chat(message: str, conversation_id: str | None = None) -> dict:
    settings = get_settings()

    # 1) 요약 조회  2) 시스템 프롬프트에 삽입
    summary = data_service.get_summary()
    system_prompt = build_system_prompt(summary)

    # 이어지는 대화라면 최근 메시지 몇 개만 함께 보냄 (토큰 비용 제한)
    history: list[dict] = []
    if conversation_id:
        conv = conversation_service.get_conversation(conversation_id)  # 없으면 404
        history = [{"role": m["role"], "content": m["content"]}
                   for m in conv["messages"][-settings.chat_history_limit:]]

    llm_messages = [{"role": "system", "content": system_prompt}, *history,
                    {"role": "user", "content": message}]

    # 3) GPT 호출
    reply = call_llm(llm_messages)

    # 4) 자동 저장
    now = _now()
    new_messages = [
        {"role": "user", "content": message, "created_at": now},
        {"role": "assistant", "content": reply, "created_at": now},
    ]
    if conversation_id:
        conv = conversation_service.append_messages(conversation_id, new_messages)
    else:
        conv = conversation_service.create_conversation(new_messages)

    return {"conversation_id": conv["id"], "title": conv["title"], "reply": reply, "model": settings.openai_model}
