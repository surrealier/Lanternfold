# PRD — EventOps Agent Platform

- Version: v1.0
- Date: 2026-03-06
- Owner: Bong Kijeong
- Type: 대표 포트폴리오 프로젝트
- Goal: Vision AI 기반 이벤트 탐지 시스템을, 운영자 의사결정까지 연결하는 Agentic AI 플랫폼으로 확장한다.

---

## 1. Product Overview

### 1.1 한 줄 설명
CCTV/영상 스트림에서 이벤트를 탐지한 뒤, 관련 규정/매뉴얼을 검색하고, 상황을 요약하고, 추천 조치를 제안하며, 운영 로그와 알림까지 남기는 **운영형 Vision+LLM Agent 플랫폼**.

### 1.2 왜 이 프로젝트를 만드는가
기존 Vision AI 포트폴리오는 보통 여기서 끝난다.
- 사람/객체/행동을 검출한다
- confidence를 낸다
- bbox나 clip을 저장한다

하지만 실제 현장에서는 그 다음이 더 중요하다.
- 이 이벤트가 왜 중요한가?
- 어떤 규정과 연결되는가?
- 운영자는 지금 무엇을 해야 하는가?
- 유사 사례는 있었는가?
- 어떤 팀/채널에 통지해야 하는가?

즉, 현업은 “탐지 모델”보다 “탐지 결과를 운영 액션으로 연결하는 시스템”을 원한다. 이 프로젝트는 바로 그 간극을 메우는 데 목적이 있다.

### 1.3 핵심 가치
1. **Detection → Decision** 으로 확장
2. Vision AI + RAG + Agent + Backend + MLOps를 한 플랫폼으로 묶음
3. 연구 코드가 아니라 실제 운영형 시스템으로 보이게 만듦
4. 대기업 AI 채용 공고에서 자주 나오는 요구사항을 하나의 프로젝트 안에서 증명

---

## 2. Product Goals / Non-Goals

### 2.1 Goals
이 프로젝트의 주요 목표는 아래 6가지를 포괄한다.

#### G1. 운영 가능한 Vision inference 서비스 구축
- 영상/RTSP 입력 기반 이벤트 탐지
- 결과 저장, 조회, 재현 가능
- 실시간 또는 near-real-time 처리 가능

#### G2. Agentic workflow 구축
- 이벤트 발생 시 자동으로 문서 검색
- 관련 정책/매뉴얼 기반으로 상황 요약
- 추천 조치 생성
- 알림 발송
- trace/log 저장

#### G3. Backend/API/DB 체계화
- 운영자가 조회 가능한 API 제공
- 이벤트/리포트/질의응답 이력 저장
- 검색, 필터링, 감사 가능

#### G4. LLM 서빙/최적화 접점 확보
- 소형 오픈소스 LLM/VLM 연결
- quantization, serving 방식을 비교 가능한 구조
- 추후 보조 프로젝트와 연계 가능

#### G5. Multimodal 포트폴리오화
- detection 결과를 자연어 설명과 연결
- “무슨 일이 일어났는지”, “왜 그렇게 봤는지” 설명

#### G6. Graph/ontology 확장 가능 구조 설계
- 이벤트, 위험도, 규정, 액션, 담당자 관계를 구조화
- GraphRAG/Rule grounding 확장 가능

### 2.2 Non-Goals
아래는 v1 범위 밖이다.
- 완전한 상용 수준 UI 디자인 완성도
- 대규모 멀티테넌시 SaaS
- 수천 대 카메라 동시 처리
- 완전한 보안 인증 체계(OAuth SSO, RBAC 고도화)
- 대규모 파인튜닝 인프라 자체 구축
- 완벽한 법적/산업 안전 인증 대응

---

## 3. Target Users

### 3.1 Primary User — 운영자(Operator)
**문제:** 이벤트가 많이 발생해도 무엇을 먼저 봐야 할지 모른다.

**필요한 것:**
- 최근 이벤트 목록
- 위험도 정렬
- 관련 규정/조치 요약
- 영상 근거 프레임
- 빠른 재확인 링크

### 3.2 Secondary User — AI 엔지니어 / MLOps 엔지니어
**문제:** 모델은 있는데 운영 파이프라인이 없다.

**필요한 것:**
- inference 결과 저장 구조
- 재처리 파이프라인
- 실험/운영 메트릭 분리
- 모델/서비스 관측성

### 3.3 Tertiary User — 관리자 / 팀 리드
**문제:** 실제로 AI가 업무를 줄였는지 증명하고 싶다.

**필요한 것:**
- 이벤트 volume, false alarm, 처리 시간
- agent 조치 추천 품질
- 운영 효율 지표

---

## 4. User Problems

### P1. 탐지 결과가 “bbox”로만 끝난다
운영자는 bbox보다 “무슨 상황인지”와 “지금 뭘 해야 하는지”가 궁금하다.

### P2. 규정/매뉴얼이 분산돼 있다
PDF, PPT, 문서, 운영 룰이 흩어져 있어서 사람이 직접 찾느라 시간이 오래 걸린다.

### P3. 이벤트 처리 이력이 구조화되지 않는다
누가 어떤 이벤트를 확인했고, 어떤 판단을 했는지 남기기 어렵다.

### P4. AI 시스템이 운영 환경과 분리돼 있다
모델 추론, 문서 검색, 알림, 로그가 따로 놀아 유지보수가 어렵다.

### P5. Agent 결과의 신뢰성을 평가하기 어렵다
요약이 맞는지, 규정 참조가 적절한지, hallucination이 있는지 검증 체계가 부족하다.

---

## 5. Product Scope

### 5.1 In Scope
- 영상 파일/RTSP 입력
- 이벤트 탐지
- 이벤트 메타데이터 저장
- 정책/매뉴얼 RAG
- Agent workflow
- 운영 요약/조치안 생성
- 알림
- API 및 대시보드
- K8s 배포
- 모니터링

### 5.2 Out of Scope (v1)
- 모바일 앱
- 음성 인터페이스 완성도 고도화
- 고급 access control
- 다국어 동시 서비스
- edge-device fleet management

---

## 6. Representative Use Cases

### UC1. 쓰러짐 이벤트 대응
1. 카메라에서 fall 의심 이벤트 탐지
2. 이벤트 메타데이터 저장
3. 관련 안전 SOP 검색
4. Agent가 위험도 평가 + 조치안 생성
5. 운영자에게 Telegram/Slack 알림 발송
6. 대시보드에서 근거 프레임/규정/추천 조치 확인

### UC2. 무단투기/침입/화재 초기 대응
1. 이벤트 검출
2. 유사 과거 사례 검색
3. 대응 프로토콜 제시
4. 담당 채널에 알림

### UC3. 운영자 질의응답
운영자가 다음처럼 질문한다.
- “이 이벤트 왜 high risk야?”
- “이 상황에서 제일 먼저 해야 할 조치는 뭐야?”
- “최근 7일간 유사 이벤트 몇 건 있었어?”

Agent는
- 이벤트 기록
- 관련 규정
- 최근 사례
를 기반으로 답변한다.

---

## 7. Success Metrics

### 7.1 Product Metrics
- 이벤트당 자동 리포트 생성 성공률 >= 95%
- 탐지 후 첫 요약 생성 시간 <= 10초
- 규정 retrieval top-k hit rate >= 80%
- 운영자 재조회 성공률 >= 95%
- 이벤트 저장 누락률 <= 1%

### 7.2 Model/Agent Metrics
- event detection precision/recall/F1
- policy retrieval recall@k, MRR
- recommendation relevance score (human eval)
- hallucination rate
- answer grounding rate

### 7.3 System Metrics
- API p95 latency
- inference p95 latency
- DB query latency
- queue backlog
- pod restart count
- service uptime

---

## 8. Functional Requirements

## FR-1. Video Ingestion
### Description
영상 파일 또는 RTSP 스트림을 입력으로 받는다.

### Requirements
- MP4 업로드 지원
- RTSP URL 등록 지원
- source_id 관리
- ingest 상태 추적
- clip/frame 저장 경로 관리

### Acceptance Criteria
- 사용자가 mp4를 업로드하면 job이 생성된다.
- 사용자가 RTSP를 등록하면 source 레코드가 생성된다.
- ingest 상태가 DB/API로 조회 가능하다.

---

## FR-2. Vision Inference Service
### Description
이벤트 탐지 모델이 입력 영상을 처리하고 event metadata를 생성한다.

### Requirements
- 모델 버전 관리
- threshold 설정
- bbox, class, confidence, track_id 저장
- event temporal grouping 지원
- 결과 재현 가능해야 함

### Acceptance Criteria
- inference 결과가 JSON으로 반환된다.
- event_type, timestamp, confidence, frame_ref가 저장된다.
- 동일 입력에 대해 동일 모델 버전 기준 재처리 가능하다.

---

## FR-3. Event Store
### Description
탐지 결과를 구조화된 이벤트 단위로 저장한다.

### Requirements
- raw detection과 logical event 분리
- risk_level 필드 지원
- review_status 필드 지원
- operator_feedback 저장
- 검색/필터링 API 제공

### Acceptance Criteria
- 날짜, source, class, risk_level, status 기준 검색 가능
- event detail 조회 시 관련 frame/clip과 agent report가 함께 보임

---

## FR-4. Document Ingestion / RAG
### Description
정책/매뉴얼 문서를 ingestion해 검색 가능한 지식베이스를 만든다.

### Requirements
- PDF/Markdown ingestion
- chunking 전략 설정
- embedding 생성
- vector DB 저장
- 문서 출처/버전 관리

### Acceptance Criteria
- 문서 업로드 후 retrieval API로 검색 가능
- chunk별 source citation 반환 가능

---

## FR-5. Agent Workflow
### Description
이벤트 발생 시 자동 workflow를 수행한다.

### Workflow Example
1. load_event
2. retrieve_policy
3. summarize_situation
4. estimate_risk
5. recommend_actions
6. notify
7. persist_trace

### Requirements
- LangGraph 기반 상태 흐름 정의
- tool calling 지원
- event_id 기반 실행 가능
- retry / failure state 관리
- trace 저장

### Acceptance Criteria
- event_id 입력 시 report 생성
- 보고서에 summary, risk, evidence, policy_refs, actions 포함
- trace가 저장되고 재조회 가능

---

## FR-6. Operator QA API
### Description
운영자는 이벤트 관련 질문을 자연어로 할 수 있다.

### Requirements
- event-grounded QA
- recent event aggregate query
- policy-grounded answer
- citation 제공

### Acceptance Criteria
- 질문에 대해 event, policy, log를 근거로 답변
- citation 또는 evidence frame 반환

---

## FR-7. Notification
### Description
이벤트/보고서/위험도에 따라 외부 채널에 알림을 보낸다.

### Requirements
- Telegram 또는 Slack 연동
- severity threshold 기반 알림
- message template 설정
- deduplication 지원

### Acceptance Criteria
- high risk 이벤트 발생 시 채널 메시지 발송
- 중복 이벤트는 rate-limit 또는 묶음 전송 가능

---

## FR-8. Dashboard
### Description
운영자가 이벤트를 조회하고 리포트를 확인하는 웹 UI

### Requirements
- event list
- filters
- event detail
- report view
- evidence media view
- trace/log view
- KPI summary

### Acceptance Criteria
- 최근 이벤트 목록 확인 가능
- 상세 페이지에서 video/frame, summary, actions, citations 확인 가능

---

## FR-9. Observability
### Description
서비스 상태를 추적하고 장애를 빠르게 파악한다.

### Requirements
- metrics export
- structured logging
- tracing(가능하면)
- dashboard visualization
- alert rules

### Acceptance Criteria
- API latency, inference latency, error rate 시각화 가능
- pod/service 장애 감지 가능

---

## FR-10. Evaluation Harness
### Description
탐지/RAG/Agent 품질을 평가하는 내부 도구

### Requirements
- golden set 구성
- retrieval eval
- answer grounding eval
- hallucination tagging
- latency/quality tradeoff 기록

### Acceptance Criteria
- 정답셋 기준 주기적 평가 가능
- 모델/프롬프트/embedding 변경 전후 비교 가능

---

## 9. Non-Functional Requirements

### NFR-1. Reliability
- 장애 시 재시도 가능
- 최소한 event 저장은 유실 없이 보장
- 비동기 queue 설계 고려

### NFR-2. Performance
- 단일 이벤트 report 생성 <= 10초 목표
- UI 조회 응답 <= 2초 목표
- ingestion/inference 병렬 처리 가능 구조

### NFR-3. Maintainability
- 서비스 분리
- 환경 변수 관리
- model/service versioning
- 테스트 가능한 구조

### NFR-4. Reproducibility
- model version, prompt version, embedding model version, document version 저장
- 동일 event에 대한 report 재생성 가능

### NFR-5. Security
- 기본 auth 토큰
- secrets 분리
- 외부 채널 webhook 관리
- 민감정보 로그 마스킹

### NFR-6. Scalability
- API, agent, inference, vector DB 분리
- pod 단위 scale-out 가능 구조

---

## 10. System Architecture

## 10.1 Logical Components
1. **Video Source Layer**
   - mp4 upload
   - RTSP stream

2. **Vision Service**
   - YOLO / RF-DETR / custom detector
   - ONNX / TensorRT / OpenVINO backend

3. **Event Processor**
   - detection grouping
   - event schema mapping
   - DB write

4. **Knowledge Layer**
   - document parser
   - embedding
   - vector DB
   - optional graph store

5. **Agent Service**
   - LangGraph orchestration
   - retrieval tool
   - summarization
   - action recommendation
   - trace persistence

6. **API Gateway**
   - FastAPI
   - auth
   - CRUD / query endpoints

7. **Frontend**
   - operator dashboard

8. **Infra & Observability**
   - PostgreSQL
   - Redis/queue
   - Prometheus/Grafana/Loki
   - K8s

## 10.2 Suggested Tech Stack
### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy / Alembic
- Pydantic
- Celery or RQ

### DB / Storage
- PostgreSQL
- Redis
- MinIO or local object storage
- pgvector or Qdrant

### Vision
- PyTorch
- ONNX Runtime
- TensorRT or OpenVINO
- OpenCV

### Agent / LLM
- LangGraph
- LangChain (optional helper)
- Qwen / Llama 계열 소형 모델
- vLLM or Ollama or TGI
- Langfuse (optional)

### Frontend
- React / Next.js
- simple admin UI

### Infra
- Docker
- docker-compose
- k3s / Kubernetes
- Prometheus
- Grafana
- GitHub Actions

---

## 11. Data Model

## 11.1 entities

### `video_sources`
- id
- source_type (file, rtsp)
- source_name
- source_uri
- created_at
- is_active

### `inference_jobs`
- id
- source_id
- model_name
- model_version
- backend_type
- status
- started_at
- completed_at

### `events`
- id
- source_id
- job_id
- event_type
- start_ts
- end_ts
- confidence
- risk_level
- location_label
- status (new, reviewed, escalated, dismissed)
- created_at

### `event_evidence`
- id
- event_id
- frame_uri
- clip_uri
- bbox_json
- track_id
- timestamp

### `documents`
- id
- title
- source_uri
- version
- uploaded_at

### `document_chunks`
- id
- document_id
- chunk_text
- embedding_ref
- page_no
- metadata_json

### `agent_reports`
- id
- event_id
- summary
- risk_reason
- recommended_actions_json
- policy_refs_json
- model_name
- prompt_version
- created_at

### `agent_traces`
- id
- event_id
- state_graph_json
- tool_calls_json
- token_usage_json
- latency_ms
- created_at

### `operator_queries`
- id
- event_id nullable
- user_text
- answer_text
- citations_json
- created_at

### `notifications`
- id
- event_id
- channel_type
- recipient
- status
- sent_at

---

## 12. API Requirements

## 12.1 Example APIs

### POST `/api/v1/sources/files`
영상 파일 업로드

**Input**
- multipart file
- source_name

**Output**
```json
{
  "source_id": "src_001",
  "status": "uploaded"
}
```

### POST `/api/v1/sources/rtsp`
RTSP 등록

**Input**
```json
{
  "source_name": "factory_cam_01",
  "source_uri": "rtsp://..."
}
```

**Output**
```json
{
  "source_id": "src_002",
  "status": "registered"
}
```

### POST `/api/v1/inference/jobs`
추론 작업 생성

**Input**
```json
{
  "source_id": "src_001",
  "model_name": "rf-detr",
  "model_version": "v0.3.1",
  "backend_type": "onnx"
}
```

**Output**
```json
{
  "job_id": "job_001",
  "status": "queued"
}
```

### GET `/api/v1/events`
이벤트 목록 조회

**Query Params**
- event_type
- risk_level
- status
- start_date
- end_date
- source_id

### GET `/api/v1/events/{event_id}`
이벤트 상세 조회

**Output Example**
```json
{
  "event_id": "evt_001",
  "event_type": "fall",
  "risk_level": "high",
  "confidence": 0.93,
  "evidence": [
    {
      "frame_uri": ".../frame_120.jpg",
      "timestamp": "2026-03-20T10:11:22"
    }
  ],
  "report": {
    "summary": "작업장 내 쓰러짐 의심 이벤트입니다.",
    "policy_refs": ["SOP-12"],
    "recommended_actions": ["현장 관리자 호출"]
  }
}
```

### POST `/api/v1/reports/generate`
Agent report 생성

**Input**
```json
{
  "event_id": "evt_001"
}
```

### POST `/api/v1/qa`
운영자 질의응답

**Input**
```json
{
  "event_id": "evt_001",
  "question": "왜 high risk로 분류됐어?"
}
```

**Output**
```json
{
  "answer": "낙상 추정 프레임이 연속 3회 탐지되었고, 안전 매뉴얼 SOP-12에 따라 high risk로 간주됩니다.",
  "citations": ["SOP-12", "frame_120.jpg"]
}
```

### POST `/api/v1/documents`
문서 업로드

### GET `/api/v1/metrics/summary`
대시보드 KPI 요약

---

## 13. Agent Design

## 13.1 Agent Objectives
- 이벤트를 이해한다
- 근거 문서를 찾는다
- 운영자 친화적으로 요약한다
- hallucination을 줄인다
- trace를 남긴다

## 13.2 Candidate State Graph
1. `LOAD_EVENT`
2. `FETCH_EVIDENCE`
3. `RETRIEVE_POLICY`
4. `ASSESS_RISK`
5. `GENERATE_SUMMARY`
6. `RECOMMEND_ACTION`
7. `VALIDATE_GROUNDING`
8. `NOTIFY`
9. `PERSIST_REPORT`

## 13.3 Guardrails
- policy citation 없는 답변은 low confidence 표시
- evidence 없는 high risk 판단 금지
- 모호할 경우 “추가 확인 필요” 반환
- 알림 전 최소 필수 필드 검증

---

## 14. Evaluation Plan

## 14.1 Vision
- Precision / Recall / F1
- FPS / latency
- false alarm 분석
- class confusion

## 14.2 Retrieval
- recall@k
- MRR
- chunking 전략 비교
- embedding model 비교

## 14.3 Agent
- answer correctness
- grounding rate
- action relevance
- hallucination rate
- operator usefulness score

## 14.4 System
- p50/p95 latency
- queue delay
- resource usage
- deployment stability

---

## 15. Milestones

## Phase 0 — Planning (Week 1)
- domain 선정
- repo 구조 설계
- DB schema 설계
- API spec 초안
- architecture diagram 작성

## Phase 1 — Vision MVP (Week 2-3)
- video ingestion
- inference service
- event storage
- event list/detail API

## Phase 2 — RAG + Agent MVP (Week 4-5)
- document ingestion
- vector DB
- report generation workflow
- operator QA API

## Phase 3 — Dashboard + Notification (Week 6)
- list/detail/report UI
- Telegram/Slack 알림

## Phase 4 — Infra / MLOps (Week 7-8)
- Docker-compose
- k3s/K8s 배포
- Prometheus/Grafana
- CI/CD

## Phase 5 — Multimodal Upgrade (Week 9)
- frame/clip 설명
- event-grounded VLM QA

## Phase 6 — Graph Extension + Polish (Week 10-12)
- knowledge graph optional
- README 정리
- demo video
- benchmark 문서

---

## 16. Risks and Mitigations

### R1. 범위가 너무 넓어짐
**대응:** MVP와 extension 분리. 우선은 event→report→dashboard 까지만 완성.

### R2. Agent hallucination
**대응:** citation 강제, evidence 없는 추론 차단, golden set 평가.

### R3. K8s 운영 난이도
**대응:** 처음엔 docker-compose, 이후 k3s 단일 노드.

### R4. RTSP 안정성 이슈
**대응:** 파일 입력 우선 완성 후 RTSP 확장.

### R5. UI 개발 시간이 과도하게 듦
**대응:** admin template 기반 최소 UI로 시작.

### R6. 문서 retrieval 품질 저하
**대응:** chunk 전략/embedding model 비교 실험 추가.

---

## 17. Portfolio Positioning

이 프로젝트는 아래 메시지를 주기 위해 설계한다.

> “저는 Vision AI 모델만 만든 것이 아니라, 이벤트 탐지 결과를 운영 프로세스와 연결하는 Agent 기반 AI 플랫폼을 설계·구현·배포할 수 있습니다.”

## 17.1 Resume Bullet Examples
- Vision 이벤트 탐지 결과를 RAG/Agent workflow와 결합해 운영자용 리포트 자동 생성 플랫폼 설계 및 구현
- FastAPI, PostgreSQL, Vector DB, LangGraph, K8s 기반의 운영형 AI 서비스 아키텍처 구축
- 탐지 결과의 정책 grounding, 추천 조치 생성, 알림 자동화까지 포함한 end-to-end Vision+LLM 시스템 구현
- ONNX/TensorRT/OpenVINO 기반 추론 서비스와 agent pipeline의 통합 운영 및 모니터링 구성

---

## 18. Demo Scenario

### Demo 1
- mp4 업로드
- 낙상 이벤트 탐지
- event list 생성
- report 자동 생성
- dashboard에서 evidence + policy + action 확인

### Demo 2
- 운영자가 “왜 위험도 high냐?” 질문
- event-grounded answer + citation 반환

### Demo 3
- 고위험 이벤트 발생 시 Telegram 알림 전송

### Demo 4
- Grafana에서 inference latency / report latency 시각화

---

## 19. MVP Definition

### MVP includes
- 영상 파일 업로드
- 1개 이벤트 클래스 탐지 모델
- event DB 저장
- 1개 문서 컬렉션 RAG
- report 자동 생성
- 간단한 list/detail UI
- Telegram 알림
- docker-compose 배포

### MVP excludes
- 실시간 대규모 RTSP 다중 입력
- 복잡한 멀티에이전트 협업
- graph store
- advanced auth
- 고급 UI

---

## 20. Post-MVP Extensions
- RTSP 멀티카메라
- Role-based access control
- GraphRAG
- VLM 기반 explainability 고도화
- operator feedback loop 기반 report 개선
- active learning 연계
- anomaly detection 확장

---

## 21. Open Questions
- vector DB를 pgvector로 갈지 Qdrant로 갈지?
- report 생성 모델은 local serving으로 충분한가?
- event risk taxonomy를 어떻게 정의할 것인가?
- operator feedback를 model eval과 어떻게 연결할 것인가?
- 멀티모달 설명은 VLM 1회 호출로 충분한가, 아니면 evidence selection이 먼저 필요한가?

---

## 22. Suggested Repository Structure

```text
eventops-agent-platform/
├─ services/
│  ├─ vision-service/
│  ├─ agent-service/
│  ├─ api-gateway/
│  └─ frontend/
├─ libs/
│  ├─ schemas/
│  ├─ prompts/
│  └─ eval/
├─ infra/
│  ├─ docker/
│  ├─ k8s/
│  └─ monitoring/
├─ docs/
│  ├─ architecture/
│  ├─ api/
│  └─ adr/
└─ datasets/
```

---

## 23. Recommended Blog Series
1. Vision 이벤트 탐지를 운영 리포트 자동화로 확장하는 방법
2. FastAPI + PostgreSQL + Vector DB로 이벤트 운영 시스템 설계하기
3. LangGraph로 event-grounded agent workflow 만들기
4. pgvector vs Qdrant 비교
5. k3s에서 Vision+LLM 서비스 운영해보기
6. Agent hallucination을 줄이기 위한 grounding 전략

---

## 24. Final Summary
이 프로젝트는 단순한 탐지 모델 데모가 아니다. Vision AI를 출발점으로 삼되,
- Backend
- RAG
- Agent orchestration
- MLOps/K8s
- Multimodal
- Graph 확장성

까지 연결한 **운영형 AI 시스템**을 증명하는 프로젝트다. 이 한 프로젝트만 제대로 완성해도, 현재 채용시장에서 자주 요구되는 역량 대부분을 매우 설득력 있게 보여줄 수 있다.
