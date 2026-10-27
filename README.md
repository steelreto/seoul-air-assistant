# 서울 대기질 AI 비서

2025년 서울 초미세먼지·기상 기록 365일을 분석해 두고, 그 요약을 GPT 시스템 프롬프트에 넣어
**"내 데이터를 알고 답하는" AI 채팅**을 제공하는 웹 서비스입니다.

> 일반 ChatGPT에 "작년에 공기가 제일 나빴던 날은?"이라고 물으면 일반론만 돌아옵니다.
> 이 서비스는 저장된 기록을 요약해 매 질문마다 AI에게 함께 전달하므로
> "2025-01-21, 91.8㎍/㎥(매우나쁨). 풍속 1.6m/s로 바람이 약했던 날이에요"처럼 답합니다.

## 배포 URL

| 구분 | URL |
|---|---|
| 프론트엔드 (Vercel) | `https://(작성 예정).vercel.app` |
| 백엔드 API (Render) | `https://(작성 예정).onrender.com` |
| Swagger UI | `https://(작성 예정).onrender.com/docs` |

> Render 무료 플랜은 15분간 요청이 없으면 잠들어, 첫 접속에 최대 1분 정도 걸립니다.
> 프론트는 접속 시 `/health`로 서버를 먼저 깨우고 "서버를 깨우는 중이에요" 안내를 띄웁니다.

## 주요 기능

- **데이터 기반 AI 채팅**: 요약을 시스템 프롬프트에 주입한 GPT 답변, 로딩 표시, 추천 질문
- **데이터 관리(CRUD)**: 날짜별 기록 추가·수정·삭제, 월 필터, 메모 검색, 입력값 검증
- **대화 기록**: 질문할 때마다 자동 저장, 목록 조회, 불러오기, 삭제
- **대기질 요약**: 최근 기록, 기간·개수·평균·최고/최저·추세, 등급별 일수, 월별 평균
- 보너스: 일별 추이 그래프, 기상 조건별 평균(추가 지표), CSV/JSON 내보내기, 다크 모드

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.10+, FastAPI, Pydantic, Uvicorn |
| DB | Firebase Firestore (`firebase-admin`) |
| AI | OpenAI Chat Completions API (`openai`, 기본 모델 `gpt-4o-mini`) |
| 프론트엔드 | HTML / CSS / JavaScript (프레임워크 없음), Chart.js(그래프) |
| 배포 | Render(백엔드), Vercel(프론트) |

## 데이터

| 출처 | 내용 |
|---|---|
| 서울 열린데이터광장 「서울시 일별 평균 대기오염도 정보」 2025 | 측정소별 PM10·PM2.5 일평균 |
| 기상청 기상자료개방포털 ASOS 일자료, 서울(108) 2025 | 평균·최저·최고기온, 일강수량, 평균 풍속, 평균 습도 |

전처리(`scripts/preprocess.py`)
1. 측정소 50곳 중 **자치구 측정소 25곳**만 사용 (도로변 측정소는 차량 영향으로 서울 평균을 높게 왜곡)
2. 날짜별 25곳 평균 → PM2.5를 주 지표 `value`로 사용
3. 기상청 자료와 날짜로 병합, 강수량 빈칸은 비가 오지 않은 날이므로 0으로 채움

결과: `data/seoul_air_2025.csv` (365행)

```
date,value,pm10,temp_avg,temp_min,temp_max,rain,wind,humidity,memo
2025-01-21,91.8,112.0,2.4,...,0.0,1.6,...,
```

## 구조

```
seoul-air-assistant/
├─ backend/
│  ├─ main.py                 앱 생성, CORS, 예외 처리, 라우터 등록
│  ├─ seed.py                 CSV → Firestore 업로드
│  ├─ core/                   config(환경변수), firebase(DB 초기화), errors, memory_db(로컬 테스트용)
│  ├─ schemas/                Pydantic 요청/응답 모델
│  ├─ routers/                HTTP 엔드포인트 (data, conversations, chat)
│  └─ services/               비즈니스 로직 (CRUD, 요약 계산, 프롬프트 생성, GPT 호출)
├─ frontend/                  index.html, style.css, app.js, config.js, build.sh, vercel.json
├─ data/seoul_air_2025.csv    전처리 결과
└─ scripts/                   preprocess.py, make_demo_data.py
```

**라우터/서비스 분리 기준**: 라우터는 "어떤 URL로 무엇을 받아 무엇을 돌려주는지"만 정하고,
서비스는 HTTP를 모르는 순수 로직(DB 접근, 통계, GPT 호출)을 담당합니다.
그래서 `chat_service`는 요약이 필요할 때 HTTP로 `/api/data/summary`를 다시 부르지 않고
`data_service.get_summary()`를 직접 호출합니다. 서비스는 `NotFoundError` 같은 예외만 던지고,
`main.py`가 이를 404/409/503 응답으로 바꿉니다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/data` | 새 데이터 추가 (날짜가 문서 ID, 같은 날짜는 409) |
| GET | `/api/data` | 목록 조회 (`start`, `end`, `limit`, `order` 선택) |
| GET | `/api/data/{id}` | 1건 조회 |
| PUT | `/api/data/{id}` | 수정 (보낸 필드만, 날짜는 변경 불가) |
| DELETE | `/api/data/{id}` | 삭제 |
| GET | `/api/data/summary` | 요약 (프롬프트 주입용) |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록 (messages **미포함**) |
| GET | `/api/conversations/{id}` | 대화 불러오기 (messages 전체) — 요구사항 (A) 방식 |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | AI 채팅 |
| GET | `/health` | 상태 확인 (콜드스타트 깨우기용) |

### 요약 응답 예시 (`GET /api/data/summary`, 일부)

```json
{
  "period": "2025-01-01 ~ 2025-12-31",
  "count": 365,
  "metric": { "name": "초미세먼지(PM2.5)", "unit": "㎍/㎥" },
  "metrics": { "average": 18.5, "median": 15.6, "max": 91.8, "max_date": "2025-01-21", "min": 1.6, "min_date": "2025-10-07" },
  "grade_days": { "좋음": 174, "보통": 159, "나쁨": 31, "매우나쁨": 1 },
  "trend": { "label": "감소", "text": "감소 (공기질 개선) — 최근 30일 평균 19.3㎍/㎥, 직전 30일 21.7㎍/㎥ 대비 -11.1%" },
  "monthly": [ { "month": "2025-01", "pm25_avg": 27.7, "temp_avg": -0.4, "rain_total": 19.5 } ],
  "worst_days": [ ... ], "weather_relation": { "by_temp": [...], "by_rain": [...], "by_wind": [...] }
}
```

추세 판단: 마지막 날짜 기준 최근 30일 평균을 직전 30일 평균과 비교해 ±5% 미만이면 유지, 그보다 크면 증가/감소.

## 컨텍스트 주입 동작 원리 (`POST /api/chat`)

```
질문 도착
 → ① data_service.get_summary()로 요약 계산 (캐시 사용)
 → ② build_system_prompt(summary)로 요약을 한국어 문장으로 만들어 시스템 프롬프트에 삽입
 → ③ [시스템 프롬프트, 이전 대화 최근 10개, 새 질문]으로 GPT 호출 (max_completion_tokens=500)
 → ④ 질문과 답변을 conversations에 자동 저장 (새 대화면 생성, 아니면 이어 붙임)
 → 답변 + conversation_id 반환
```

GPT는 학습한 적 없는 내 데이터를 모르기 때문에, 질문할 때마다 필요한 사실(요약)을 프롬프트로 함께 보내는 방식입니다.
365건 원본 전체 대신 통계 요약(약 2,600자)만 보내서 토큰 비용을 줄이고, 답변 규칙(수치 근거, 추측 금지, 단위 표기)도 함께 지시합니다.

## Pydantic 검증

- `DataCreate`: 날짜 형식, PM2.5 0~1000, 습도 0~100, 풍속 0~60 등 범위 검사, 메모 200자 제한
- `DataUpdate`: 모든 필드 선택, 알 수 없는 필드(예: `date`)는 거절(`extra="forbid"`)
- `ChatRequest`: 공백만 있는 메시지 거절, 1000자 제한
- 잘못된 요청은 서비스 코드에 닿기 전에 422로 응답 → DB에 이상한 값이 들어가지 않음

## Firestore 컬렉션

```
data/{YYYY-MM-DD}
  date, value, pm10, temp_avg, temp_min, temp_max, rain, wind, humidity, memo, created_at, updated_at

conversations/{자동 ID}
  title, messages[{role, content, created_at}], message_count, created_at, updated_at
```

날짜를 문서 ID로 써서 같은 날짜가 두 번 저장되지 않게 했습니다.
채팅마다 365건을 다시 읽지 않도록 서버에 5분 캐시를 두고, 추가·수정·삭제 시 캐시를 비웁니다 (Firestore 무료 읽기 한도 절약).

## 환경 변수

### 백엔드 (`backend/.env`, Render Environment)

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅(배포) | 서비스 계정 키 JSON 전체를 한 줄 문자열로 |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | ✅(로컬) | 서비스 계정 키 파일 경로 (위 JSON과 둘 중 하나) |
| `ALLOWED_ORIGINS` | ✅ | CORS 허용 도메인, 쉼표 구분 (예: `https://xxx.vercel.app,http://127.0.0.1:5500`) |
| `OPENAI_BASE_URL` | | OpenAI 호환 API(교육기관 제공 등)를 쓸 때 그 주소. 비우면 OpenAI 공식 서버 |
| `OPENAI_MODEL` | | 기본 `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | | 답변 최대 토큰, 기본 500 (GPT-5 계열은 추론 토큰도 포함되므로 1500 권장) |
| `CHAT_HISTORY_LIMIT` | | GPT에 함께 보낼 이전 메시지 수, 기본 10 |
| `USE_MEMORY_DB` | | `true`면 Firebase 없이 메모리 DB로 실행 (로컬 테스트 전용) |

### 프론트엔드 (Vercel Environment)

| 이름 | 설명 |
|---|---|
| `API_BASE_URL` | 백엔드 주소 (예: `https://xxx.onrender.com`, 끝에 `/` 없이) |

바닐라 JS는 브라우저에서 환경변수를 읽을 수 없으므로, Vercel 빌드 때 `build.sh`가
`API_BASE_URL` 값으로 `config.js`를 생성합니다. 값이 비어 있으면 화면은 **데모 모드**(예시 데이터)로 열립니다.

### 왜 CORS·환경변수·키 관리가 필요한가

- **CORS**: 프론트(vercel.app)와 백엔드(onrender.com)는 도메인이 달라서, 브라우저는 백엔드가 허용한 도메인의 요청만 통과시킵니다. 허용 목록을 환경변수로 두면 코드 수정 없이 도메인을 바꿀 수 있습니다.
- **환경변수**: 로컬과 배포 환경의 값(키, DB, 허용 도메인)이 다르므로 코드와 설정을 분리합니다.
- **키 관리**: OpenAI 키가 유출되면 타인이 내 비용으로 API를 쓰고, Firebase 키가 유출되면 DB 전체를 읽고 지울 수 있습니다. 그래서 키는 `.env`/대시보드에만 두고 `.gitignore`로 GitHub 업로드를 막습니다.

## 로컬 실행

### 1) 백엔드

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env  → 값 채우기
python seed.py                   # 최초 1회: CSV 365건을 Firestore에 업로드
uvicorn main:app --reload        # http://127.0.0.1:8000/docs
```

Firebase 키 없이 먼저 돌려 보려면 `.env`에 `USE_MEMORY_DB=true`만 넣고 실행하세요. (CSV가 메모리에 자동 적재되고, 서버를 끄면 사라집니다)

### 2) 프론트엔드

`frontend/config.js`의 `API_BASE_URL`을 `"http://127.0.0.1:8000"`으로 바꾼 뒤:

```bash
cd frontend
python -m http.server 5500       # http://127.0.0.1:5500
```

(VS Code Live Server를 써도 됩니다. 포트가 다르면 `ALLOWED_ORIGINS`에 추가하세요.)

## 배포

### Render (백엔드)
1. GitHub에 저장소 푸시
2. Render → New → Web Service → 저장소 선택
3. Root Directory `backend` / Build Command `pip install -r requirements.txt` / Start Command `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment에 `OPENAI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ALLOWED_ORIGINS` 입력
5. 배포 후 `https://(서비스명).onrender.com/docs` 확인

### Vercel (프론트엔드)
1. Vercel → Add New Project → 같은 저장소 선택
2. Root Directory `frontend` (빌드 설정은 `vercel.json`이 자동 적용)
3. Environment Variables에 `API_BASE_URL` = Render 주소
4. 배포 후 Vercel 주소를 Render의 `ALLOWED_ORIGINS`에 추가하고 Render 재배포

## 스크린샷

| 화면 | 이미지 |
|---|---|
| 데이터 요약이 보이는 채팅 (질문+답변) | `docs/chat.png` (추가 예정) |
| 데이터 관리 (CRUD 동작) | `docs/data.png` (추가 예정) |
| 대화 기록 (불러오기) | `docs/history.png` (추가 예정) |

## 비용 관리

- `max_completion_tokens=500`, 이전 대화는 최근 10개만 전송
- 요약 캐시로 Firestore 읽기 절약
- OpenAI 대시보드에서 월 사용 한도(Usage limit)를 낮게 설정해 두기
