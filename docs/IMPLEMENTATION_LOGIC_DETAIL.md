# EventOps 세부 로직과 구성 문서

## 문서 목적

이 문서는 EventOps가 실제로 어떤 순서와 규칙으로 동작하는지 설명합니다.
즉, "무엇이 있는가"보다 "어떻게 동작하는가"에 집중합니다.

## 현재 구현 형태

현재 MVP는 하나의 FastAPI 앱 안에서 다음 로직을 수행합니다.

- 소스 등록
- 문서 인덱싱
- 데모 추론
- 이벤트 저장
- 리포트 생성
- 질의응답
- 리뷰 반영
- 메트릭 수집

## 1. 영상 소스 업로드 로직

입력:

- `source_name`
- MP4 파일

처리:

1. 파일이 비어 있지 않은지 확인
2. `source_id` 생성
3. 스토리지 경로에 파일 저장
4. `video_sources` 레코드 생성

출력:

- `source_id`
- 업로드 상태

RTSP도 비슷하지만 파일 저장 없이 메타데이터만 저장합니다.

## 2. 추론 job 생성 로직

입력:

- `source_id`
- `model_name`
- `model_version`
- `backend_type`
- `threshold`

처리:

1. source 조회
2. `inference_jobs` 레코드 생성
3. source 이름에서 이벤트 키워드 추론
4. confidence, risk level 기본값 계산
5. `events` 생성
6. `raw_detections` 생성
7. `event_evidence` 생성

현재 이벤트 판별 예시:

- `fall` 포함 -> `fall`
- `fire` 포함 -> `fire`
- `intrusion`, `trespass` 포함 -> `intrusion`
- 그 외 -> `anomaly`

즉, 현재 추론기는 실제 YOLO가 아니라 재현 가능한 데모 어댑터입니다.

## 3. risk level 계산 로직

기본 규칙:

- evidence가 없으면 high risk 금지
- `fall`, `fire`, `intrusion`은 evidence가 있으면 `high`
- `illegal_dumping`은 `medium`
- 나머지는 `low`

이 규칙은 PRD의 guardrail 요구와 연결됩니다.

## 4. 문서 ingestion 로직

입력:

- title
- version
- Markdown 또는 PDF 파일

처리:

1. 파일 바이트 읽기
2. Markdown은 utf-8 decode
3. PDF는 `pypdf`로 텍스트 추출
4. 빈 문서면 거절
5. `documents` 레코드 생성
6. chunking 수행
7. `document_chunks` 저장

chunking 방식:

- 단어 기준 분할
- 기본 chunk size 90
- overlap 20

현재 retrieval은 embedding 기반이 아니라 lexical match 기반입니다.

## 5. 검색 로직

현재 검색은 매우 단순하고 재현 가능하게 설계되어 있습니다.

동작 방식:

1. 질문 또는 이벤트 기반 query를 token set으로 변환
2. 각 chunk의 token set과 겹치는 개수 계산
3. 점수가 높은 chunk를 상위로 정렬
4. 상위 `k`개 반환

즉, 지금은 운영 흐름 검증용 retrieval이며, 나중에 vector DB로 쉽게 교체할 수 있습니다.

## 6. 리포트 생성 로직

리포트 생성은 EventOps의 핵심입니다.

입력:

- `event_id`

처리 순서:

1. event 조회
2. evidence 조회
3. 관련 chunk 검색
4. citation document title 수집
5. grounded action 추출
6. risk reason 생성
7. summary 생성
8. trace 생성
9. notification 필요 여부 판단

### 6-1. grounded action 추출 방식

이번 구현에서 중요한 부분입니다.

단순히 검색된 chunk 텍스트 전체에서 bullet을 긁지 않고,
원본 업로드 문서를 다시 읽어 다음 section을 우선 탐색합니다.

- `action`
- `response`
- `escalation`
- `next step`
- `protocol`
- `조치`
- `대응`

그 안의 bullet 또는 numbered list만 추출하고,
중복 제거 후 최대 3개까지만 사용합니다.

이 방식의 장점:

- `## Escalation` 같은 heading artifact가 action에 섞이지 않음
- chunk 경계 때문에 문장이 합쳐지는 문제를 줄임
- 원문 policy 구조를 더 잘 보존함

### 6-2. 리포트 출력 필드

`agent_reports`에는 다음이 저장됩니다.

- summary
- risk_level
- risk_reason
- recommended_actions_json
- policy_refs_json
- model_name
- prompt_version

### 6-3. trace 생성 로직

trace는 실제 LangGraph 실행은 아니지만, PRD의 상태 기반 흐름을 흉내 내도록 저장됩니다.

예시 상태:

- `LOAD_EVENT`
- `FETCH_EVIDENCE`
- `RETRIEVE_POLICY`
- `ASSESS_RISK`
- `GENERATE_SUMMARY`
- `RECOMMEND_ACTION`
- `VALIDATE_GROUNDING`
- `NOTIFY`
- `PERSIST_REPORT`

이를 통해 운영자는 "리포트가 어떤 단계로 만들어졌는가"를 볼 수 있습니다.

## 7. 알림 생성 로직

현재 MVP에서는 실제 외부 전송 대신 `notifications` 테이블에 기록하는 방식입니다.

규칙:

- high risk일 때만 알림 생성
- 동일 event에 이미 알림이 있으면 중복 생성 방지

상태:

- `recorded`
- 또는 향후 실제 전송용 `pending`

## 8. QA 로직

입력:

- `event_id`
- `question`

처리:

1. event 조회
2. 최신 report가 없으면 먼저 생성
3. evidence와 policy citation 결합
4. 질문 패턴에 따라 응답 유형 결정

현재 지원하는 질문 의도:

- 왜 high risk인가
- 먼저 어떤 조치를 해야 하나
- 최근 유사 이벤트가 몇 건인가
- 일반 요약 요청

답변은 `operator_queries`에 저장됩니다.

## 9. 이벤트 상세 페이지 로직

이벤트 상세 페이지는 다음 정보를 한 화면에 모읍니다.

- event 기본 정보
- review status
- operator feedback
- report
- recommended actions
- policy references
- notifications
- evidence
- raw detections
- trace
- operator QA history

즉, 운영자가 판단하는 데 필요한 정보를 한 페이지로 모으는 구조입니다.

## 10. 메트릭과 로깅 로직

현재 HTTP middleware에서 다음을 처리합니다.

- optional API token 검사
- 요청 시간 측정
- status code 수집
- structured JSON log 출력
- Prometheus metric 적재

노출되는 대표 메트릭:

- request count
- request latency
- sources total
- jobs total
- events total
- reports total
- documents total
- notifications total

## 11. 스키마 호환성 로직

운영 중 DB 스키마가 조금 바뀌면 예전 SQLite 파일이 문제를 일으킬 수 있습니다.

실제로 `inference_jobs.threshold` 컬럼이 없는 예전 DB에서 오류가 발생했기 때문에,
부팅 시 다음 보정 로직을 수행합니다.

1. 현재 테이블 목록 확인
2. `inference_jobs` 존재 여부 확인
3. `threshold` 컬럼이 없으면 `ALTER TABLE` 수행

이것으로 persistent volume이 남아 있어도 앱이 부팅되도록 했습니다.

## 12. 테스트 구성

현재 테스트는 크게 세 축입니다.

### 1. workflow test

- 문서 업로드
- 영상 업로드
- inference
- event 조회
- report 생성
- review 반영

### 2. dashboard / QA test

- dashboard 렌더링
- event detail 렌더링
- QA 응답
- UI route 동작

### 3. evaluation / compatibility test

- golden evaluation
- API token 보호
- legacy schema bootstrap
- grounded action extraction

## 13. 현재 한계

현재는 완제품 MVP이지만, 일부는 데모 구현입니다.

- vision은 실제 detector가 아니라 deterministic adapter
- retrieval은 lexical search
- notification은 record mode 중심
- UI는 운영 검증용 최소 형태

하지만 PRD의 핵심 흐름인 아래 항목은 이미 닫혀 있습니다.

- source ingestion
- event creation
- evidence 저장
- document grounding
- report generation
- QA
- dashboard
- metrics
- Docker 검증

## 14. 향후 교체 지점

구조상 다음 부분은 비교적 쉽게 교체 가능합니다.

- detector -> YOLO / RF-DETR / ONNX Runtime
- retrieval -> pgvector / Qdrant
- report generator -> 실제 LLM agent
- notifications -> Slack / Telegram 실제 전송
- storage -> object storage
- DB -> PostgreSQL

즉, 현재 세부 로직은 "작동하는 MVP"이면서 동시에 "확장 가능한 골격"을 갖고 있습니다.

## 마지막 정리

EventOps의 세부 로직은 한 문장으로 정리할 수 있습니다.

"영상에서 찾은 신호를, 문서 근거와 함께, 운영자가 바로 행동할 수 있는 이벤트 리포트로 바꾸는 흐름"

이 문장이 현재 구현의 핵심입니다.
