# AgentGate

> **AI Agent Tool Call Gateway** — AI 에이전트가 내부 도구를 호출하기 전에 정책 평가, 비용 제어, 인간 승인, 감사 로그를 강제하는 백엔드 제어 플레인

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-112%20passed-brightgreen)](#테스트)
[![DDD](https://img.shields.io/badge/architecture-DDD%20%2B%20Hexagonal-orange)](ARCHITECTURE.md)

---

## 왜 필요한가

AI 에이전트는 환불, 주문 취소, 개인정보 조회 같은 내부 도구를 자율적으로 호출합니다. 제어 플레인이 없으면:

| 문제 | 결과 |
|------|------|
| 권한 없는 에이전트가 민감 도구 호출 | 데이터 유출, 잘못된 환불 |
| 고위험 작업이 즉시 실행 | 되돌릴 수 없는 부작용 |
| 비용 추적 없음 | LLM 비용 통제 불가 |
| 감사 로그 없음 | 사고 후 원인 파악 불가 |

AgentGate는 에이전트와 도구 사이에서 이 모든 것을 일관되게 처리합니다.

---

## 기능 개요

| 기능 | 설명 |
|------|------|
| **Tool Registry** | 도구 등록, 위험도 설정, 활성화/비활성화 |
| **Policy Engine** | 7개 룰의 체인 구조 — 도구/사용자/에이전트 상태, 역할, 도메인, 비용 한도, 위험도 순서로 평가 |
| **Approval Flow** | HIGH 위험 도구는 관리자 승인 후 실행. PENDING → APPROVED → EXECUTED 상태 추적 |
| **MockExecutor** | 실제 HTTP 없이 도구 실행 시뮬레이션. 실제 실행기로 교체 가능한 인터페이스 |
| **Audit Log** | 모든 호출에 `trace_id`, `policy_reason`, `duration_ms` 기록. 페이지네이션 제공 |
| **표준 에러 응답** | 전역 예외 핸들러로 `{"code": "...", "message": "..."}` 일관된 에러 스키마 |
| **Domain Events** | 상태 전환마다 이벤트 발행 — 이벤트 버스 연결 확장점 |

---

## 핵심 흐름

```
┌─────────────┐        POST /api/v1/gateway/invoke
│  AI Agent   │ ──────────────────────────────────────────▶ ┌──────────────────────┐
└─────────────┘                                              │  InvokeToolUseCase   │
                                                             └──────────┬───────────┘
                                                                        │ 1. 도구/에이전트/사용자 조회
                                                                        │ 2. 일일 비용 집계
                                                                        ▼
                                                             ┌──────────────────────┐
                                                             │   PolicyEngine       │
                                                             │   (7-rule chain)     │
                                                             └──────────┬───────────┘
                                                                        │
                                         ┌──────────────────────────────┼──────────────────────────────┐
                                         ▼                              ▼                              ▼
                                      DENY                       REQUIRE_APPROVAL                   ALLOW
                                         │                              │                              │
                                  tool_call.deny()            tool_call.request_approval()    executor.execute()
                                         │                              │                              │
                                  execution=SKIPPED             approval=PENDING               tool_call.record_execution()
                                                                                               execution=SIMULATED
                                         │                              │                              │
                                         └──────────────────────────────┴──────────────────────────────┘
                                                                        │
                                                              tool_call_repo.save()
                                                              (tool_calls + approvals 원자적 저장)
                                                                        │
                                                                 Audit Log 기록
                                                         trace_id · policy_reason · duration_ms
```

---

## 승인 플로우 시퀀스

```
Agent          Gateway API        ApprovalAPI       DB
  │                │                   │              │
  │── invoke ─────▶│                   │              │
  │                │── PolicyEngine ──▶│              │
  │                │   (REQUIRE_APPROVAL)             │
  │                │── save ──────────────────────────▶│  tool_calls(PENDING)
  │◀── 200 PENDING ┤                   │              │  approvals(PENDING)
  │  request_id    │                   │              │
  │                │                   │              │
Admin             │                   │              │
  │               │── GET /approvals ─▶│              │
  │               │◀── [{approval_id}] ┤              │
  │               │                   │              │
  │               │── POST /approve ──▶│              │
  │               │                   │── save ──────▶│  approvals(APPROVED)
  │               │◀── 200 APPROVED ──┤              │
  │               │                   │              │
Agent             │                   │              │
  │── execute ───▶│                   │              │
  │               │── MockExecutor    │              │
  │               │── record_execution│              │
  │               │── save ───────────────────────────▶│  tool_calls(SIMULATED)
  │               │                   │              │  approvals(EXECUTED)
  │◀── 200 SIMULATED                  │              │
```

---

## 아키텍처

DDD + Hexagonal Architecture. 상세 내용은 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.

```
┌─────────────────────────────────────────────────────┐
│  api/          FastAPI 라우터, Pydantic 스키마        │
│                HTTP 변환만 담당, 비즈니스 로직 없음   │
└───────────────────────────┬─────────────────────────┘
                            │ calls
┌───────────────────────────▼─────────────────────────┐
│  application/  Use Case 커맨드 객체 + 오케스트레이터  │
│                InvokeToolUseCase, ExecuteApproved    │
└───────────────────────────┬─────────────────────────┘
                            │ 인터페이스(ABC)에만 의존
┌───────────────────────────▼─────────────────────────┐
│  domain/       순수 비즈니스 로직 (I/O 없음)          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ ToolCall    │  │ PolicyEngine │  │  Domain    │  │
│  │ Aggregate   │  │ (rule chain) │  │  Events    │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │  IToolRepository  IToolCallRepository          │  │
│  │  IAgentRepository IToolExecutor (ports)        │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                            ▲ 인터페이스 구현
┌───────────────────────────┴─────────────────────────┐
│  infrastructure/  Adapters                           │
│  SQLAlchemy ORM  ·  ToolCallRepository               │
│  MockExecutor    ·  Alembic migrations               │
└─────────────────────────────────────────────────────┘
```

---

## 빠른 시작

### Docker (권장)

```bash
make up          # 서버 + PostgreSQL 기동 (마이그레이션 자동 포함)
open http://localhost:8000/docs   # Swagger UI
make seed        # 데모 데이터 삽입
```

### 로컬 개발

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up db -d
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

---

## API 목록

### Gateway (핵심)

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/gateway/invoke` | 도구 호출 — 정책 평가 후 실행/승인요청/차단 |
| `POST` | `/api/v1/gateway/execute/{request_id}` | 승인된 호출 실행 |

**요청 예시 (invoke):**
```json
{
  "agent_id": "cs-agent-001",
  "user_id": "user-001",
  "tool_name": "refund_order",
  "input": {"order_id": "ORDER-1234", "amount": 12000},
  "trace_id": "optional-custom-trace-id"
}
```

**응답 예시 (ALLOW):**
```json
{
  "request_id": "uuid",
  "policy_decision": "ALLOW",
  "policy_reason": "All policy checks passed",
  "execution_status": "SIMULATED",
  "trace_id": "optional-custom-trace-id",
  "duration_ms": 2,
  "actual_cost": 0.01
}
```

### Tool Registry

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/tools` | 도구 등록 |
| `GET` | `/api/v1/tools` | 도구 목록 |
| `GET` | `/api/v1/tools/{tool_id}` | 도구 조회 |
| `PATCH` | `/api/v1/tools/{tool_id}` | 도구 수정 |
| `DELETE` | `/api/v1/tools/{tool_id}` | 도구 삭제 |

### Approvals

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/approvals` | 승인 목록 (`?pending_only=true`) |
| `GET` | `/api/v1/approvals/{approval_id}` | 승인 상세 |
| `POST` | `/api/v1/approvals/{approval_id}/approve` | 승인 |
| `POST` | `/api/v1/approvals/{approval_id}/reject` | 거절 |

### Audit Log

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/audit-logs` | 페이지네이션 감사 로그 |
| `GET` | `/api/v1/audit-logs/{request_id}` | 단건 조회 |

**감사 로그 응답:**
```json
{
  "items": [...],
  "total": 42,
  "limit": 50,
  "offset": 0,
  "has_next": false
}
```

---

## 시나리오 예시

### 저위험 — 즉시 실행

```bash
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: trace-001" \
  -d '{"agent_id":"cs-agent-001","user_id":"user-001",
       "tool_name":"get_order_detail","input":{"order_id":"ORDER-1234"}}'
# ↳ policy_decision: "ALLOW"
# ↳ execution_status: "SIMULATED"
# ↳ policy_reason: "All policy checks passed"
# ↳ duration_ms: 1
```

### 고위험 — 승인 플로우

```bash
# 1. 호출 → PENDING
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -d '{"agent_id":"cs-agent-001","user_id":"user-001",
       "tool_name":"refund_order","input":{"order_id":"ORDER-1234","amount":12000}}'
# ↳ approval_status: "PENDING", request_id: "uuid"

# 2. 승인 목록에서 approval_id 확인
curl "http://localhost:8000/api/v1/approvals?pending_only=true"

# 3. 승인
curl -X POST "http://localhost:8000/api/v1/approvals/{approval_id}/approve" \
  -d '{"approver_id":"admin-001","reason":"정상 환불 확인"}'

# 4. 실행
curl -X POST "http://localhost:8000/api/v1/gateway/execute/{request_id}"
# ↳ execution_status: "SIMULATED"
# ↳ approval_status: "EXECUTED"
```

### 거부 — 역할 없음

```bash
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -d '{"agent_id":"bot-001","user_id":"viewer-001","tool_name":"refund_order","input":{}}'
# ↳ policy_decision: "DENY"
# ↳ policy_reason: "User lacks required role: cs_agent"
# ↳ execution_status: "SKIPPED"
```

---

## 테스트

```bash
make test                                      # Docker 컨테이너 내부 실행
pytest --cov=app --cov-report=term-missing     # 커버리지 포함
```

| 파일 | 대상 | 테스트 수 |
|------|------|-----------|
| `test_tool_call_aggregate.py` | ToolCall 상태 머신 — 모든 전환 경로 | 18 |
| `test_value_objects.py` | InputData 해싱, ExecutionResult 불변성 | 12 |
| `test_policy.py` | PolicyEngine 전체 결정 흐름 | 9 |
| `test_policy_rules.py` | 각 룰 격리 테스트 + 커스텀 체인 | 22 |
| `test_domain_events.py` | 상태 전환마다 이벤트 발행 검증 | 8 |
| `test_audit_enrichment.py` | trace_id, policy_reason, duration_ms, 페이지네이션, 에러 포맷 | 21 |
| `test_gateway.py` | Gateway 통합 — ALLOW/DENY/APPROVAL/전체 플로우 | 10 |
| `test_approvals.py` | 승인 CRUD + 이중 승인 가드 | 6 |
| `test_tools.py` | Tool Registry CRUD | 7 |

**112 tests, 0 failures.** SQLite 인메모리 — PostgreSQL 불필요.

---

## 주요 설계 결정

### Policy Engine — Chain of Responsibility

7개 룰이 순서대로 평가되며 첫 매칭에서 단락됩니다. 새 정책 추가 = 새 `PolicyRule` 서브클래스 하나만 작성.

```python
PolicyEngine(rules=[MyNewRule(), *DEFAULT_RULES])  # 주입 가능
```

### ToolCall Aggregate Root

모든 상태 전환이 애그리게이트 메서드 안에 있어 외부에서 불변식을 깰 수 없습니다.

### 도메인 이벤트

`collect_events()`로 이벤트를 수집해 이벤트 버스에 발행할 수 있습니다 — 애그리게이트 수정 없이 Slack 알림, OpenTelemetry 스팬 생성 등을 구현 가능합니다.

---

## ERD

```
tools                    agents                   users
─────────────────        ─────────────────        ──────────────
tool_id (UK)             agent_id (UK)            user_id (UK)
name · domain            name                     roles (JSON)
risk_level               allowed_domains (JSON)   enabled
required_role            enabled
approval_required
daily_cost_limit
enabled

tool_calls
──────────────────────────────────────────────────────────────
request_id (UK)          trace_id (INDEX)
agent_id · user_id       policy_reason
tool_name                duration_ms
input_data (JSON)
input_hash               risk_level
                         policy_decision   ALLOW | REQUIRE_APPROVAL | DENY
approval_status          PENDING | APPROVED | REJECTED | EXECUTED | FAILED
execution_status         SIMULATED | SUCCESS | FAILED | SKIPPED
estimated_cost · actual_cost
created_at · executed_at

approvals
──────────────────────────────
id
tool_call_id → tool_calls.id
approver_id · status · reason
created_at · updated_at
```

---

## Make 커맨드

```bash
make up       # 서버 기동 (DB 포함, 포그라운드)
make up-d     # 백그라운드 기동
make down     # 종료 + 볼륨 삭제
make test     # 테스트 실행 (컨테이너 내부)
make seed     # 데모 데이터 삽입
make migrate  # DB 마이그레이션
make shell    # api 컨테이너 셸 진입
make logs     # 로그 스트리밍
```

---

## 확장 로드맵

| 항목 | 구현 위치 |
|------|-----------|
| 실제 도구 HTTP 실행 | `IToolExecutor` 구현체 작성 → `deps.py` 교체 |
| LangGraph / OpenAI Agent 연동 | `api/v1/`에 `/mcp` 또는 `/agent` 라우터 추가 |
| JWT / API Key 인증 | `app/main.py` 미들웨어 + `deps.py` Depends |
| 비동기 전환 | `Session` → `AsyncSession` (infrastructure layer) |
| 이벤트 버스 연결 | use case에서 `collect_events()` 후 Kafka/SQS 발행 |
| Slack / Email 알림 | `ApprovalRequestedEvent` 구독 |
| OpenTelemetry | `trace_id`를 스팬 컨텍스트로 전파 |
| Rate Limiting | `app/main.py` 미들웨어 |
