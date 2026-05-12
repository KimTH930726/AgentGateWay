# AgentGate — Architecture Guide

## 개요

AgentGate는 AI 에이전트의 모든 도구 호출을 인터셉트해 **정책 평가 → 실행/승인/차단 → 감사 기록** 까지의 전체 흐름을 강제하는 백엔드 게이트웨이입니다.

설계 원칙:
- **DDD (Domain-Driven Design)**: Aggregate, Entity, Value Object, Domain Service로 도메인 모델 표현
- **Hexagonal Architecture (Ports & Adapters)**: 도메인은 인터페이스(ABC)만 알고, 구현체는 infrastructure에서 주입
- **Clean Architecture 의존 방향**: 모든 화살표가 안쪽(domain)을 향함

---

## 레이어 맵

```
┌─────────────────────────────────────────────────────────────────┐
│  api/                         HTTP 경계                          │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ tools.py  │  │gateway.py│  │approvals │  │ audit_logs.py │  │
│  └───────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│  FastAPI 라우터 — HTTP 변환만 담당, try/except 없음              │
│  schemas.py (Pydantic) · deps.py (의존성 주입 배선)             │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls (Use Case 호출)
┌────────────────────────────▼────────────────────────────────────┐
│  application/                  Use-case 레이어                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ InvokeToolUseCase      ExecuteApprovedUseCase            │   │
│  │ ApproveToolCallUseCase RejectToolCallUseCase             │   │
│  │ RegisterToolUseCase    GetToolUseCase  ...               │   │
│  └──────────────────────────────────────────────────────────┘   │
│  Command 객체(frozen dataclass) + 단일 책임 클래스               │
└────────────────────────────┬────────────────────────────────────┘
                             │ depends on (ABC 인터페이스)
┌────────────────────────────▼────────────────────────────────────┐
│  domain/                  핵심 비즈니스 로직 (I/O 없음)          │
│                                                                  │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │ ToolCall            │  │ PolicyEngine                     │  │
│  │ (Aggregate Root)    │  │ (Domain Service)                 │  │
│  │  ├ Approval(Entity) │  │  ┌─ ToolEnabledRule              │  │
│  │  └ DomainEvents     │  │  ├─ UserEnabledRule              │  │
│  └─────────────────────┘  │  ├─ AgentEnabledRule             │  │
│                           │  ├─ RoleCheckRule                │  │
│  ┌─────────────────────┐  │  ├─ DomainAccessRule             │  │
│  │ Tool  Agent  User   │  │  ├─ CostLimitRule                │  │
│  │ (Aggregates)        │  │  └─ ApprovalRequiredRule         │  │
│  └─────────────────────┘  └──────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Ports (ABC):  IToolRepository  IAgentRepository         │   │
│  │                IUserRepository  IToolCallRepository      │   │
│  │                IToolExecutor                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             ▲ 인터페이스 구현 (Adapters)
┌────────────────────────────┴────────────────────────────────────┐
│  infrastructure/                                                 │
│  ┌───────────────────────────┐  ┌──────────────────────────┐    │
│  │ persistence/              │  │ execution/               │    │
│  │  orm_models.py (SQLAlchemy│  │  MockExecutor            │    │
│  │  ToolCallRepository       │  │  (IToolExecutor 구현)    │    │
│  │  ToolRepository           │  └──────────────────────────┘    │
│  │  AgentRepository          │                                   │
│  │  UserRepository           │                                   │
│  └───────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

**핵심 규칙**: infrastructure는 domain을 import할 수 있지만, domain은 infrastructure를 절대 import하지 않습니다.

---

## 도메인 흐름 — InvokeToolUseCase 오케스트레이션

```
InvokeToolUseCase.execute(InvokeToolCommand)
        │
        ├─▶ IToolRepository.find_by_name(cmd.tool_name)
        │   └─▶ Tool (or NotFoundError)
        │
        ├─▶ IAgentRepository.find_by_agent_id(cmd.agent_id)
        │   └─▶ Agent (or NotFoundError)
        │
        ├─▶ IUserRepository.find_by_user_id(cmd.user_id)
        │   └─▶ User (or NotFoundError)
        │
        ├─▶ IToolCallRepository.get_daily_cost(cmd.tool_name)
        │   └─▶ float (오늘 누적 비용)
        │
        ├─▶ PolicyEngine.evaluate(PolicyContext)
        │   └─▶ PolicyResult(decision, reason)
        │
        ├─▶ ToolCall.create(...)           ← 애그리게이트 생성
        │   └─▶ [ToolCallCreatedEvent] 발행
        │
        ├─▶ (decision == DENY)
        │   └─▶ tool_call.deny(reason)     ← execution_status = SKIPPED
        │       └─▶ [ToolCallDeniedEvent]
        │
        ├─▶ (decision == REQUIRE_APPROVAL)
        │   └─▶ tool_call.request_approval()
        │       └─▶ [ApprovalRequestedEvent]
        │
        ├─▶ (decision == ALLOW)
        │   └─▶ IToolExecutor.execute(tool_name, input)
        │       └─▶ ExecutionResult(status, output, cost, duration_ms)
        │   └─▶ tool_call.record_execution(result)
        │       └─▶ [ToolCallExecutedEvent]
        │
        └─▶ IToolCallRepository.save(tool_call)
            └─▶ tool_calls 행 + approvals 행 원자적 upsert
```

---

## ToolCall 상태 머신

```
                     ToolCall.create()
                           │
                           │  policy_decision 결정됨
              ┌────────────┼────────────┐
              │            │            │
           DENY       REQUIRE_       ALLOW
              │        APPROVAL         │
              ▼            │            ▼
        deny(reason)        │     executor.execute()
              │        request_    record_execution()
   execution= │        approval()        │
   SKIPPED    │            │    execution_status:
   approval=  │      approval=    SIMULATED/SUCCESS/FAILED
   null       │      PENDING      approval= null
              │            │
              │     ┌──────┴──────┐
              │     │             │
              │  approve()    reject()
              │     │             │
              │  approval=    approval=
              │  APPROVED     REJECTED
              │     │
              │  executor.execute()
              │  record_execution()
              │     │
              │  execution_status:
              │  SIMULATED/SUCCESS/FAILED
              │  approval=
              │  EXECUTED / FAILED
              │
              └─────────────────── 모든 경로 → tool_call_repo.save()
```

**상태 조합 요약:**

| policy_decision | execution_status | approval_status |
|-----------------|------------------|-----------------|
| DENY | SKIPPED | null |
| REQUIRE_APPROVAL | null | PENDING |
| REQUIRE_APPROVAL | null | APPROVED (승인 후, 실행 전) |
| REQUIRE_APPROVAL | null | REJECTED |
| REQUIRE_APPROVAL | SIMULATED/SUCCESS | EXECUTED |
| REQUIRE_APPROVAL | FAILED | FAILED |
| ALLOW | SIMULATED/SUCCESS/FAILED | null |

---

## Policy Engine — Chain of Responsibility

```
PolicyEngine.evaluate(PolicyContext)
        │
        ▼
┌───────────────────┐
│ ToolEnabledRule   │── tool.enabled == False? ──▶ DENY "Tool is disabled"
└────────┬──────────┘
         │ None (통과)
┌────────▼──────────┐
│ UserEnabledRule   │── user.enabled == False? ──▶ DENY "User account is disabled"
└────────┬──────────┘
         │ None
┌────────▼──────────┐
│ AgentEnabledRule  │── agent.enabled == False? ──▶ DENY "Agent is disabled"
└────────┬──────────┘
         │ None
┌────────▼──────────┐
│ RoleCheckRule     │── user.has_role(tool.required_role) == False?
└────────┬──────────┘   ──▶ DENY "User lacks required role: {role}"
         │ None
┌────────▼──────────┐
│ DomainAccessRule  │── agent.can_access_domain(tool.domain) == False?
└────────┬──────────┘   ──▶ DENY "Agent not permitted to access domain: {domain}"
         │ None
┌────────▼──────────┐
│ CostLimitRule     │── daily_usage_cost >= tool.daily_cost_limit?
└────────┬──────────┘   ──▶ DENY "Daily cost limit exceeded: {limit}"
         │ None
┌────────▼──────────────┐
│ ApprovalRequiredRule  │── tool.requires_approval()?
└────────┬──────────────┘   ──▶ REQUIRE_APPROVAL "Tool risk level {level} requires..."
         │ None
         ▼
    ALLOW "All policy checks passed"
```

**확장**: 새 정책 룰 추가 = `PolicyRule(ABC)` 서브클래스 작성 후 `DEFAULT_RULES`에 삽입.
**테스트**: `PolicyEngine(rules=[MyRule()])` 으로 단일 룰 격리 테스트 가능.

---

## 도메인 이벤트 흐름

```
ToolCall Aggregate                  Use Case Layer
        │                                 │
  .create()  ────▶ ToolCallCreatedEvent   │
  .deny()    ────▶ ToolCallDeniedEvent    │
  .request_approval() ──▶ ApprovalRequestedEvent
  .approve() ────▶ ToolCallApprovedEvent  │
  .reject()  ────▶ ToolCallRejectedEvent  │
  .record_execution() ──▶ ToolCallExecutedEvent
        │                                 │
        │  collect_events() ──────────────▶
        │  (이벤트 큐 클리어)              │
        │                          events 처리:
        │                          현재: 무시 (미래 확장점)
        │                          예시: Kafka 발행
        │                                Slack 알림
        │                                OTel 스팬 생성
```

이벤트는 애그리게이트 내부에서 수집되며, 외부에서 `collect_events()`로 가져갑니다. 애그리게이트를 수정하지 않고 이벤트 처리 로직을 추가할 수 있습니다.

---

## Repository Pattern (Port / Adapter)

```
domain/                              infrastructure/
  ┌────────────────────┐               ┌──────────────────────┐
  │ IToolRepository    │◀──implements──│ ToolRepository       │
  │ (ABC)              │               │ (SQLAlchemy Session) │
  └────────────────────┘               └──────────────────────┘
  ┌────────────────────┐               ┌──────────────────────┐
  │ IToolCallRepository│◀──implements──│ ToolCallRepository   │
  │ (ABC)              │               │ save() upserts both  │
  │ + count_all()      │               │ tool_calls+approvals │
  └────────────────────┘               └──────────────────────┘
  ┌────────────────────┐               ┌──────────────────────┐
  │ IToolExecutor      │◀──implements──│ MockExecutor         │
  │ (ABC)              │               │ (canned responses)   │
  └────────────────────┘               └──────────────────────┘
```

Application 레이어는 ABC만 import합니다. `deps.py`에서 구체 클래스를 주입.

---

## 주요 설계 결정

### Approval이 ToolCall 안에 있는 이유

`ToolCall`은 최대 하나의 `Approval`을 가지며, 두 객체의 생명주기가 결합되어 있습니다. `Approval`을 별도 애그리게이트로 분리하면 `approve()` 시 크로스 애그리게이트 트랜잭션이 필요하고, "이미 승인된 호출은 재승인 불가" 같은 불변식을 원자적으로 보장하기 어렵습니다.

### save()가 두 테이블을 원자적으로 upsert하는 이유

애그리게이트가 일관성의 단위입니다. 단일 `save()` 호출이 `tool_calls` 행과 `approvals` 행을 하나의 트랜잭션으로 저장합니다. 호출자는 ORM 객체를 직접 건드리지 않습니다.

### Approval.status가 EXECUTED/FAILED로 진행하는 이유

`record_execution()` 후 `APPROVED` 상태를 유지하면 "승인은 됐지만 실제로 실행됐나?"가 불명확합니다. `EXECUTED`/`FAILED`로 명시함으로써 최종 상태를 단순하게 만들고 감사 쿼리를 간소화합니다.

### N+1 방지

`ToolCallORM.approval`을 `lazy="selectin"`으로 설정해 목록 조회 시 SQLAlchemy가 별도의 IN 쿼리 하나로 모든 approval을 로드합니다.

### trace_id 우선순위

1. `InvokeRequest.trace_id` (body 필드)
2. `X-Trace-Id` HTTP 헤더
3. 자동 생성 UUID

---

## 에러 처리 흐름

```
Domain Exception          main.py handler          HTTP Response
──────────────────────────────────────────────────────────────────
NotFoundError        ──▶  _not_found()      ──▶  404
                                                  {"code":"NOT_FOUND","message":"..."}

DomainError          ──▶  _domain_error()   ──▶  422
                                                  {"code":"DOMAIN_ERROR","message":"..."}

ConflictError        ──▶  _conflict()       ──▶  409
                                                  {"code":"CONFLICT","message":"..."}

ValueError           ──▶  _value_error()    ──▶  409
                                                  {"code":"CONFLICT","message":"..."}
```

라우터 파일에 `try/except`가 없습니다. 예외 → HTTP 매핑은 `main.py` 한 곳에서만 관리.

---

## 파일 구조 참조

```
app/
├── domain/
│   ├── enums.py                    RiskLevel, PolicyDecision, ApprovalStatus, ExecutionStatus
│   ├── shared/
│   │   ├── exceptions.py           AgentGateError 계층 구조 (code 속성 포함)
│   │   └── value_objects.py        InputData(SHA-256 해시), ExecutionResult(duration_ms 포함)
│   ├── tool/
│   │   ├── tool.py                 Tool 애그리게이트 (requires_approval() 포함)
│   │   └── repository.py           IToolRepository (ABC)
│   ├── agent/
│   │   ├── agent.py                Agent 애그리게이트 (can_access_domain() 포함)
│   │   └── repository.py           IAgentRepository (ABC)
│   ├── user/
│   │   ├── user.py                 User 애그리게이트 (has_role() 포함)
│   │   └── repository.py           IUserRepository (ABC)
│   ├── tool_call/
│   │   ├── tool_call.py            ToolCall Aggregate Root + Approval Entity
│   │   │                           상태 머신: deny/request_approval/approve/reject/record_execution
│   │   ├── events.py               도메인 이벤트 6종 (frozen dataclass)
│   │   ├── repository.py           IToolCallRepository (ABC) — count_all() 포함
│   │   └── executor.py             IToolExecutor (ABC)
│   └── policy/
│       ├── context.py              PolicyContext (입력), PolicyResult (출력)
│       ├── rules.py                PolicyRule (ABC) + 7개 구체 룰 + DEFAULT_RULES
│       └── policy_engine.py        PolicyEngine — 룰 체인 순회, 첫 매칭 반환
│
├── application/
│   ├── tool/use_cases.py           Register/Get/List/Update/Delete
│   ├── gateway/use_cases.py        InvokeToolUseCase(trace_id, 타이밍), ExecuteApprovedUseCase
│   └── approval/use_cases.py       List/Get/Approve/Reject
│
├── infrastructure/
│   ├── persistence/
│   │   ├── database.py             SQLAlchemy 엔진 + 세션 팩토리 (SQLite/PostgreSQL 호환)
│   │   ├── orm_models.py           ORM 정의 (trace_id, policy_reason, duration_ms 컬럼 포함)
│   │   └── repositories/           구체 리포지토리 구현체
│   └── execution/
│       └── mock_executor.py        MockExecutor — 벽시계 타이밍 포함 (IToolExecutor 구현)
│
└── api/
    ├── deps.py                     FastAPI 의존성 배선 (use case 조립)
    ├── schemas.py                  Pydantic 모델 (ErrorCode, ErrorResponse, AuditLogPage 포함)
    └── v1/
        ├── gateway.py              /gateway/invoke, /gateway/execute/{id}
        ├── tools.py                /tools CRUD
        ├── approvals.py            /approvals CRUD + approve/reject
        ├── audit_logs.py           /audit-logs 페이지네이션
        ├── agents.py               /agents
        └── users.py                /users

alembic/versions/
├── 0001_initial_schema.py          기본 스키마
├── 0002_add_performance_indices.py 복합 인덱스 (tool_name+created_at, approval FK)
└── 0003_audit_enrichment.py        trace_id(INDEX), policy_reason, duration_ms 컬럼

tests/
├── test_tool_call_aggregate.py     18개 — 상태 머신 전환 경로 전체
├── test_value_objects.py           12개 — 해싱, 불변성
├── test_policy.py                  9개  — PolicyEngine 전체 결정
├── test_policy_rules.py            22개 — 룰 격리 + 커스텀 체인
├── test_domain_events.py           8개  — 이벤트 발행 순서/내용
├── test_audit_enrichment.py        21개 — trace_id, policy_reason, 페이지네이션, 에러 포맷
├── test_gateway.py                 10개 — 통합 플로우
├── test_approvals.py               6개  — 승인 CRUD + 이중 승인 가드
└── test_tools.py                   7개  — Tool Registry
```

---

## 확장 지점

| 기능 | 구현 위치 |
|------|-----------|
| 실제 도구 HTTP 실행 | `IToolExecutor` 구현체 작성 → `deps.py`에서 교체 |
| LangGraph / OpenAI Agent | `api/v1/`에 `/mcp` 또는 `/agent` 라우터 추가 |
| JWT / API Key 인증 | `app/main.py` 미들웨어 + `deps.py` Depends |
| 비동기 전환 | `Session` → `AsyncSession` (infrastructure 레이어) |
| 이벤트 버스 연결 | use case에서 `collect_events()` 후 Kafka/SQS 발행 |
| 지오펜싱 / IP 체크 | 새 `PolicyRule` 서브클래스 작성 → `DEFAULT_RULES` 삽입 |
| OpenTelemetry | `trace_id`를 스팬 컨텍스트로 전파 |
