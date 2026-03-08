# EventOps

EventOps는 영상에서 이상 이벤트를 감지하고, 관련 문서를 근거로 운영자에게 요약, 위험도, 추천 조치, 질의응답, 알림 정보를 제공하는 운영형 AI 플랫폼입니다.

쉽게 말하면:

- 카메라가 이상한 장면을 찾고
- 시스템이 관련 규정과 매뉴얼을 찾아보고
- 운영자에게 "무슨 일이 생겼고, 왜 중요하고, 지금 뭘 해야 하는지"를 알려주는 프로젝트입니다.

## 이 프로젝트가 보여주는 것

많은 AI 데모는 "탐지했다"에서 끝납니다.
EventOps는 그다음 단계까지 연결합니다.

- Detection -> Event
- Event -> Grounded Report
- Report -> Operator Action

즉, 모델 하나가 아니라 실제 운영 흐름 전체를 보여주는 것이 목적입니다.

## 현재 MVP에서 가능한 것

- MP4 업로드
- RTSP source 등록
- deterministic demo inference로 이벤트 생성
- 이벤트, evidence, raw detection 저장
- 정책 문서 업로드 및 검색
- grounded report 생성
- operator QA
- review status / feedback 저장
- dashboard 확인
- Prometheus metrics 확인
- Docker 기반 로컬 실행

## 현재 구현의 성격

현재 버전은 "운영 흐름을 검증하는 MVP"입니다.

- Vision: 실제 YOLO가 아니라 deterministic demo adapter
- Retrieval: vector DB가 아니라 lexical retrieval
- Report: heuristic grounded agent
- Notification: record mode 중심

즉, 실제 production detector/LLM/vector DB로 교체 가능한 구조를 먼저 만들어 둔 상태입니다.

## 빠르게 이해하는 사용자 흐름

1. 안전 문서(SOP)를 업로드합니다.
2. MP4 파일을 업로드합니다.
3. inference job을 생성합니다.
4. 이벤트가 생성됩니다.
5. report를 생성합니다.
6. 위험도, 근거 문서, 추천 조치를 확인합니다.
7. QA로 "왜 high risk인가?" 같은 질문을 합니다.
8. 운영자가 review 상태와 feedback을 남깁니다.

## 저장소 구조

```text
services/
  api-gateway/
  vision-service/
  agent-service/
  frontend/
libs/
  prompts/
  eval/
  schemas/
infra/
  docker/
  k8s/
  monitoring/
docs/
datasets/
```

## 문서 안내

프로젝트를 이해할 때는 아래 순서로 보는 것이 가장 쉽습니다.

- [docs/PROJECT_EXPLAINED_FOR_EVERYONE.md](docs/PROJECT_EXPLAINED_FOR_EVERYONE.md)
- [docs/SYSTEM_ARCHITECTURE_GUIDE.md](docs/SYSTEM_ARCHITECTURE_GUIDE.md)
- [docs/IMPLEMENTATION_LOGIC_DETAIL.md](docs/IMPLEMENTATION_LOGIC_DETAIL.md)
- [docs/MVP_SPEC.md](docs/MVP_SPEC.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 빠른 시작

### 1. Docker Desktop 실행

Docker Desktop이 켜져 있어야 합니다.

### 2. 애플리케이션 실행

저장소 루트에서 실행합니다.

```powershell
docker compose -f infra/docker/docker-compose.yml up --build
```

### 3. 접속 주소

- Dashboard: `http://localhost:8000`
- OpenAPI Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/healthz`
- Prometheus Metrics: `http://localhost:8000/metrics`

## 가장 중요한 API

- `POST /api/v1/sources/files`
- `POST /api/v1/sources/rtsp`
- `GET /api/v1/sources`
- `POST /api/v1/inference/jobs`
- `GET /api/v1/inference/jobs/{job_id}`
- `GET /api/v1/events`
- `GET /api/v1/events/{event_id}`
- `PATCH /api/v1/events/{event_id}`
- `POST /api/v1/documents`
- `GET /api/v1/documents/search`
- `POST /api/v1/reports/generate`
- `POST /api/v1/qa`
- `GET /api/v1/metrics/summary`

## 테스트 실행

전체 테스트:

```powershell
docker compose -f infra/docker/docker-compose.yml run --rm api pytest
```

특정 테스트만 실행하고 싶다면:

```powershell
docker compose -f infra/docker/docker-compose.yml run --rm api pytest services/api-gateway/tests/test_event_workflow.py
```

## 설정

주요 환경 변수:

- `EVENTOPS_DATABASE_URL`
- `EVENTOPS_STORAGE_ROOT`
- `EVENTOPS_SEED_SAMPLE_DATA`
- `EVENTOPS_NOTIFICATION_MODE`
- `EVENTOPS_NOTIFICATION_TARGET`
- `EVENTOPS_API_TOKEN`

`EVENTOPS_API_TOKEN`을 설정하면 `/api/*` 경로는 `x-api-token` 헤더를 요구합니다.

## 현재 검증된 범위

로컬 Docker 기준으로 다음 흐름이 검증되어 있습니다.

- 문서 업로드
- 영상 업로드
- inference job 생성
- 이벤트 조회
- report 생성
- QA 응답
- dashboard 렌더링
- metrics 노출
- legacy SQLite schema compatibility

## 구현상 중요한 포인트

- 이벤트와 raw detection을 분리해서 저장합니다.
- high risk는 evidence 없이 생성하지 않도록 가드레일을 둡니다.
- report action은 업로드된 원본 policy 문서의 action section에서 추출합니다.
- schema가 오래된 SQLite DB도 부팅 시 자동 보정합니다.
- metrics와 structured log를 기본 제공합니다.

## 한계와 다음 단계

현재는 MVP이므로 아래는 아직 단순화되어 있습니다.

- 실제 detector 연동
- vector DB 연동
- 실제 Slack / Telegram 전송
- production-grade auth
- multi-camera real-time scale-out

다음 단계에서는 다음 교체가 자연스럽습니다.

- Vision -> YOLO / RF-DETR / ONNX Runtime
- Retrieval -> pgvector / Qdrant
- Agent -> 실제 LLM orchestration
- DB -> PostgreSQL
- Storage -> object storage

## 핵심 메시지

EventOps는 "영상 이벤트를 찾는 AI"가 아니라,
"영상 이벤트를 사람이 행동할 수 있는 운영 정보로 바꾸는 시스템"입니다.
