# AgentGate — Architecture Deep Dive

## 개요

AgentGate는 AI Agent의 모든 도구 호출을 인터셉트해
**정책 평가 → 실행/승인/차단 → 감사 기록** 파이프라인을 강제하는 백엔드 게이트웨이입니다.

Governance 확장 후에는 단순 Tool 실행 제어를 넘어 **Agent 단위 정책, 비용·토큰 예산, 도구 선택 추적, 정책 평가 trace, 설정 변경 이력**까지 동일한 도메인 경계 안에서 다룹니다 — "AI Agent Tool Governance Platform".

**설계 원칙**
- **DDD (Domain-Driven Design)**: 비즈니스 불변식을 Aggregate 경계 안에 캡슐화
- **Hexagonal Architecture (Ports & Adapters)**: 도메인은 인터페이스(ABC)만 알고, 구현체는 주입
- **Clean Architecture 의존 방향**: `api → application → domain ← infrastructure`

---

## 레이어 구조

```mermaid
graph TB
    subgraph api ["api/ — HTTP 경계"]
        R["FastAPI Routers\ntools · gateway · approvals · audit_logs\nagent_tool_policies · governance · agents · users"]
        S["Pydantic Schemas\n(request / response 변환)"]
        DP["deps.py\n(의존성 배선)"]
    end

    subgraph application ["application/ — Use-case 레이어"]
        UC1["InvokeToolUseCase\nExecuteApprovedUseCase"]
        UC2["ApproveToolCallUseCase\nRejectToolCallUseCase"]
        UC3["RegisterToolUseCase ...\nCreateAgentToolPolicyUseCase ...\nListChangeLogsUseCase"]
    end

    subgraph domain ["domain/ — 핵심 비즈니스 로직 (I/O 없음)"]
        AGG["ToolCall Aggregate Root\n+ Approval Entity\n+ Domain Events"]
        AGG2["AgentToolPolicy Aggregate\nConfigChangeLog Aggregate"]
        PE["PolicyEngine\n(Domain Service)\n+ RuleEvaluation trace"]
        RULES["PolicyRule Chain\n12개 구체 룰"]
        PORTS["Ports (ABC)\nIToolRepository · IToolCallRepository\nIAgentToolPolicyRepository\nIConfigChangeLogRepository · IToolExecutor"]
        VO["Value Objects\nInputData · ExecutionResult\nToolSelection · CandidateTool"]
    end

    subgraph infra ["infrastructure/ — Adapters"]
        REPO["SQLAlchemy Repositories\nToolCallRepository · ToolRepository\nAgentToolPolicyRepository\nConfigChangeLogRepository ..."]
        EXEC["MockExecutor\n(IToolExecutor 구현)"]
        ORM["ORM Models\ntool_calls · approvals · tools\nagents · agent_tool_policies\nconfig_change_logs"]
    end

    api --> application
    application --> domain
    infra -.->|"implements"| domain

    style domain fill:#fff3cd,stroke:#ffc107,color:#000
    style infra fill:#d1ecf1,stroke:#17a2b8,color:#000
```

---

## 도메인 모델 전체 구조

```mermaid
classDiagram
    class ToolCall {
        +request_id: str
        +agent_id: str
        +user_id: str
        +tool_name: str
        +risk_level: RiskLevel
        +policy_decision: PolicyDecision
        +execution_status: ExecutionStatus
        +trace_id: str
        +policy_reason: str
        +duration_ms: int
        +create() ToolCall
        +deny(reason)
        +request_approval()
        +approve(approver_id, reason)
        +reject(approver_id, reason)
        +record_execution(result)
        +collect_events() List~DomainEvent~
    }

    class Approval {
        +approval_id: str
        +status: ApprovalStatus
        +approver_id: str
        +reason: str
        +decided_at: datetime
    }

    class InputData {
        +payload: dict
        +hash: str
        +__eq__()
        +__hash__()
    }

    class ExecutionResult {
        +status: ExecutionStatus
        +output: dict
        +cost: float
        +duration_ms: int
    }

    class PolicyEngine {
        -rules: List~PolicyRule~
        +evaluate(ctx) PolicyResult
    }

    class PolicyRule {
        <<abstract>>
        +evaluate(ctx) Optional~PolicyResult~
    }

    class PolicyContext {
        +tool: Tool
        +agent: Agent
        +user: User
        +daily_usage_cost: float
    }

    class DomainEvent {
        <<abstract>>
        +request_id: str
        +occurred_at: datetime
    }

    ToolCall "1" *-- "0..1" Approval : contains
    ToolCall "1" *-- "1" InputData : uses
    ToolCall "1" o-- "*" DomainEvent : collects
    PolicyEngine "1" o-- "*" PolicyRule : chains
    PolicyEngine ..> PolicyContext : input
    ToolCall ..> ExecutionResult : uses
```

---

## InvokeToolUseCase 오케스트레이션 흐름

```mermaid
sequenceDiagram
    participant UC as InvokeToolUseCase
    participant TR as IToolRepository
    participant AR as IAgentRepository
    participant UR as IUserRepository
    participant TCR as IToolCallRepository
    participant PE as PolicyEngine
    participant AGG as ToolCall (Aggregate)
    participant EX as IToolExecutor

    UC->>TR: find_by_name(tool_name)
    TR-->>UC: Tool
    UC->>AR: find_by_agent_id(agent_id)
    AR-->>UC: Agent
    UC->>UR: find_by_user_id(user_id)
    UR-->>UC: User
    UC->>TCR: get_daily_cost(tool_name)
    TCR-->>UC: float

    UC->>PE: evaluate(PolicyContext)
    PE-->>UC: PolicyResult(decision, reason)

    UC->>AGG: ToolCall.create(...)
    Note over AGG: [ToolCallCreatedEvent] 발행

    alt policy == DENY
        UC->>AGG: deny(reason)
        Note over AGG: execution_status = SKIPPED<br/>[ToolCallDeniedEvent] 발행
    else policy == REQUIRE_APPROVAL
        UC->>AGG: request_approval()
        Note over AGG: approval = PENDING<br/>[ApprovalRequestedEvent] 발행
    else policy == ALLOW
        UC->>EX: execute(tool_name, input)
        EX-->>UC: ExecutionResult
        UC->>AGG: record_execution(result)
        Note over AGG: execution_status = SIMULATED<br/>[ToolCallExecutedEvent] 발행
    end

    UC->>TCR: save(tool_call)
    Note over TCR: tool_calls + approvals<br/>원자적 upsert
```

---

## ToolCall 상태 머신

```mermaid
stateDiagram-v2
    [*] --> Created : ToolCall.create()\n▶ ToolCallCreatedEvent

    state "DENY 경로" as DENY_PATH {
        [*] --> Skipped : deny(reason)\nexecution_status = SKIPPED\n▶ ToolCallDeniedEvent
    }

    state "REQUIRE_APPROVAL 경로" as APPROVAL_PATH {
        [*] --> Pending : request_approval()\napproval.status = PENDING\n▶ ApprovalRequestedEvent
        Pending --> Approved : approve(approver_id)\napproval.status = APPROVED\n▶ ToolCallApprovedEvent
        Pending --> Rejected : reject(approver_id)\napproval.status = REJECTED\n▶ ToolCallRejectedEvent
        Approved --> ApprovalExecuted : record_execution()\nexecution_status = SIMULATED|SUCCESS|FAILED\napproval.status = EXECUTED|FAILED\n▶ ToolCallExecutedEvent
    }

    state "ALLOW 경로" as ALLOW_PATH {
        [*] --> DirectExecuted : record_execution()\nexecution_status = SIMULATED|SUCCESS|FAILED\n▶ ToolCallExecutedEvent
    }

    Created --> DENY_PATH : policy_decision == DENY
    Created --> APPROVAL_PATH : policy_decision == REQUIRE_APPROVAL
    Created --> ALLOW_PATH : policy_decision == ALLOW
```

**상태 조합 요약**

| policy_decision | execution_status | approval_status |
|-----------------|------------------|-----------------|
| DENY | SKIPPED | _(없음)_ |
| REQUIRE_APPROVAL | _(없음)_ | PENDING |
| REQUIRE_APPROVAL | _(없음)_ | REJECTED |
| REQUIRE_APPROVAL | SIMULATED / SUCCESS | EXECUTED |
| REQUIRE_APPROVAL | FAILED | FAILED |
| ALLOW | SIMULATED / SUCCESS / FAILED | _(없음)_ |

---

## Policy Engine — Rule Chain 상세

12개 룰을 순서대로 평가하며, 첫 번째로 단락하는 룰이 결정을 확정합니다. 각 룰의 평가 결과(PASS / DENY / REQUIRE_APPROVAL + 사유)는 `RuleEvaluation`으로 수집되어 ToolCall에 `rule_trace` JSON으로 영구 저장됩니다.

```mermaid
flowchart TD
    CTX(["PolicyContext\nTool · Agent · User\ndaily_usage_cost · agent_daily_cost\nagent_daily_tokens · agent_tool_policies"]) --> R1

    R1{"ToolEnabledRule"} -->|disabled| D1(["DENY"])
    R1 -->|enabled| R2

    R2{"UserEnabledRule"} -->|disabled| D2(["DENY"])
    R2 -->|enabled| R3

    R3{"AgentEnabledRule"} -->|disabled| D3(["DENY"])
    R3 -->|enabled| R4

    R4{"AgentToolPolicyRule\nallowlist/denylist 평가"} -->|DENY 매칭| D4(["DENY\n'denylist'"])
    R4 -->|ALLOWLIST 누락| D4b(["DENY\n'not on allowlist'"])
    R4 -->|no opinion / allowed| R5

    R5{"RoleCheckRule"} -->|미보유| D5(["DENY"])
    R5 -->|보유| R6

    R6{"DomainAccessRule"} -->|불허| D6(["DENY"])
    R6 -->|허용| R7

    R7{"CostLimitRule\ntool 하드 한도"} -->|초과| D7(["DENY"])
    R7 -->|미달| R8

    R8{"ToolCostWarnRule\ntool 워닝 임계"} -->|구간 진입| RA1(["REQUIRE_APPROVAL"])
    R8 -->|미달| R9

    R9{"AgentBudgetHardRule\nagent 하드 한도"} -->|초과| D9(["DENY"])
    R9 -->|미달| R10

    R10{"AgentTokenLimitRule"} -->|초과| D10(["DENY"])
    R10 -->|미달| R11

    R11{"AgentBudgetWarnRule\nagent 워닝 임계"} -->|구간 진입| RA2(["REQUIRE_APPROVAL"])
    R11 -->|미달| R12

    R12{"ApprovalRequiredRule\ntool.requires_approval()"} -->|True| RA3(["REQUIRE_APPROVAL"])
    R12 -->|False| AL(["ALLOW"])
```

**룰 분류**

| 분류 | 룰 | 결정 |
|------|----|------|
| Entity 활성화 | ToolEnabledRule · UserEnabledRule · AgentEnabledRule | DENY |
| Agent 권한 | AgentToolPolicyRule (Allow/Deny) · RoleCheckRule · DomainAccessRule | DENY |
| Tool 비용 | CostLimitRule (하드) | DENY |
| Tool 비용 | ToolCostWarnRule (소프트) | REQUIRE_APPROVAL |
| Agent 예산 | AgentBudgetHardRule · AgentTokenLimitRule | DENY |
| Agent 예산 | AgentBudgetWarnRule | REQUIRE_APPROVAL |
| Risk 기반 | ApprovalRequiredRule | REQUIRE_APPROVAL |

**확장 방법**:
```python
# 새 룰 추가 (엔진·기존 룰 수정 없음)
class RateLimitRule(PolicyRule):
    def evaluate(self, ctx: PolicyContext) -> Optional[PolicyResult]:
        if self._is_rate_limited(ctx.agent.agent_id):
            return PolicyResult(PolicyDecision.DENY, "Rate limit exceeded")
        return None

DEFAULT_RULES.append(RateLimitRule())

# 테스트에서 단일 룰 격리
engine = PolicyEngine(rules=[RoleCheckRule()])
```

---

## 도메인 이벤트 흐름

```mermaid
graph LR
    subgraph Aggregate ["ToolCall Aggregate"]
        CREATE["create() →\nToolCallCreatedEvent"]
        DENY_EV["deny() →\nToolCallDeniedEvent"]
        REQ["request_approval() →\nApprovalRequestedEvent"]
        APR["approve() →\nToolCallApprovedEvent"]
        REJ["reject() →\nToolCallRejectedEvent"]
        EXEC["record_execution() →\nToolCallExecutedEvent"]
        QUEUE[["_events: List[DomainEvent]"]]
    end

    subgraph UseCase ["Use Case Layer"]
        COLLECT["collect_events()\n(큐 비우며 반환)"]
    end

    subgraph Future ["미래 확장 (현재 미구현)"]
        BUS["Event Bus\nKafka / SQS"]
        SLACK["Slack 알림\nApprovalRequestedEvent"]
        OTEL["OTel Span\nToolCallExecutedEvent"]
    end

    CREATE --> QUEUE
    DENY_EV --> QUEUE
    REQ --> QUEUE
    APR --> QUEUE
    REJ --> QUEUE
    EXEC --> QUEUE

    QUEUE --> COLLECT
    COLLECT -.->|"dispatch (TODO)"| BUS
    BUS -.-> SLACK
    BUS -.-> OTEL
```

---

## Repository Pattern (Port / Adapter)

```mermaid
graph LR
    subgraph Domain ["domain/ — Ports"]
        IT["IToolRepository\n<<ABC>>"]
        ITC["IToolCallRepository\n<<ABC>>"]
        IA["IAgentRepository\n<<ABC>>"]
        IU["IUserRepository\n<<ABC>>"]
        IE["IToolExecutor\n<<ABC>>"]
    end

    subgraph Infra ["infrastructure/ — Adapters"]
        TR["ToolRepository\n(SQLAlchemy)"]
        TCR["ToolCallRepository\n(upsert tool_calls\n+ approvals 원자적)"]
        AR["AgentRepository"]
        UR["UserRepository"]
        ME["MockExecutor\n(canned responses\n+ wall-clock timing)"]
    end

    TR -->|implements| IT
    TCR -->|implements| ITC
    AR -->|implements| IA
    UR -->|implements| IU
    ME -->|implements| IE

    note1["deps.py에서 구체 클래스 주입\napplication은 ABC만 import"]
```

**`save()`가 두 테이블을 원자적으로 upsert하는 이유**:
애그리게이트가 일관성의 단위이므로, `tool_calls` 행과 `approvals` 행은 단일 트랜잭션으로 함께 저장합니다. 호출자가 ORM 객체를 직접 조작하는 경로를 원천 차단합니다.

---

## 에러 처리 아키텍처

```mermaid
flowchart LR
    subgraph Domain
        NF["NotFoundError\ncode='NOT_FOUND'"]
        DE["DomainError\ncode='DOMAIN_ERROR'"]
        CE["ConflictError\ncode='CONFLICT'"]
        VE["ValueError"]
    end

    subgraph main.py ["main.py — 전역 핸들러"]
        H1["@exception_handler(NotFoundError)"]
        H2["@exception_handler(DomainError)"]
        H3["@exception_handler(ConflictError)"]
        H4["@exception_handler(ValueError)"]
    end

    subgraph HTTP
        R404["404\n{code, message}"]
        R422["422\n{code, message}"]
        R409["409\n{code, message}"]
    end

    NF --> H1 --> R404
    DE --> H2 --> R422
    CE --> H3 --> R409
    VE --> H4 --> R409
```

라우터 파일에는 `try/except`가 없습니다. 예외 → HTTP 매핑은 단 한 곳에서 관리.

---

## 주요 설계 결정 및 근거

### 1. Approval을 독립 Aggregate로 분리하지 않은 이유

`ToolCall`은 생애주기 동안 최대 하나의 `Approval`을 가집니다.
이 관계를 분리하면:
- "PENDING 상태가 아닌 ToolCall을 승인 불가" 불변식을 크로스-애그리게이트 트랜잭션으로 보장해야 함
- 트랜잭션 실패 시 보상 로직(saga) 필요

내부 Entity로 유지하면:
```python
def approve(self, approver_id: str) -> None:
    self._assert_approval_is(ApprovalStatus.PENDING)  # 불변식 보장
    self._approval.status = ApprovalStatus.APPROVED
```

### 2. Approval.status를 EXECUTED/FAILED로 진행시키는 이유

실행 완료 후 `APPROVED` 상태를 유지하면 "승인됐지만 실행됐나?"가 불명확합니다.
`EXECUTED`/`FAILED`로 진행하면:
- 감사 쿼리가 단순해짐 (`approval_status = 'EXECUTED'` 한 조건)
- 실행 실패를 승인 이력에서 추적 가능

### 3. trace_id 처리 우선순위를 body > header > auto-generate로 설정한 이유

```
1순위: body.trace_id    — 에이전트가 의도적으로 지정
2순위: X-Trace-Id 헤더 — 인프라/게이트웨이 레이어 삽입
3순위: UUID 자동 생성  — 추적 ID 없는 레거시 클라이언트 대응
```

모든 호출에 trace_id가 보장되어, 로그 집계 시 `trace_id`로 전체 흐름을 추적 가능합니다.

### 4. N+1 쿼리 방지

```python
# orm_models.py
approval = relationship(
    "ApprovalORM",
    back_populates="tool_call",
    uselist=False,
    lazy="selectin",   # ← N+1 방지
)
```

`find_all()` 호출 시 SQLAlchemy가 `SELECT ... WHERE id IN (...)` 단일 쿼리로 모든 approval을 로드합니다.

---

## 파일 구조 참조

```
app/
├── domain/
│   ├── enums.py                    RiskLevel · PolicyDecision · ApprovalStatus · ExecutionStatus
│   │                               AgentToolPolicyType · GovernanceEntityType · ChangeType · RuleOutcome
│   ├── shared/
│   │   ├── exceptions.py           AgentGateError 계층 (code 속성)
│   │   └── value_objects.py        InputData · ExecutionResult(duration_ms, tokens_used)
│   │                               ToolSelection · CandidateTool
│   ├── tool/
│   │   ├── tool.py                 Tool 애그리게이트 (requires_approval() · warn_cost_threshold)
│   │   └── repository.py           IToolRepository (ABC)
│   ├── agent/
│   │   ├── agent.py                Agent 애그리게이트 + 예산 필드 (daily/monthly cost, token, warn)
│   │   └── repository.py           IAgentRepository (ABC, update 포함)
│   ├── user/
│   │   ├── user.py                 User 애그리게이트 (has_role())
│   │   └── repository.py           IUserRepository (ABC)
│   ├── tool_call/
│   │   ├── tool_call.py            ToolCall Aggregate Root + Approval Entity
│   │   │                           + tool_selection · rule_trace · tokens_used
│   │   ├── events.py               도메인 이벤트 6종 (frozen dataclass)
│   │   ├── repository.py           IToolCallRepository (ABC, agent 단위 집계 포함)
│   │   └── executor.py             IToolExecutor (ABC)
│   ├── policy/
│   │   ├── context.py              PolicyContext (agent 예산·정책 포함) · PolicyResult
│   │   ├── rules.py                PolicyRule(ABC) + 12 concrete rules + DEFAULT_RULES
│   │   ├── policy_engine.py        PolicyEngine — rule chain + trace 수집
│   │   └── trace.py                RuleEvaluation 값 객체 + JSON 직렬화 헬퍼
│   ├── agent_tool_policy/
│   │   ├── agent_tool_policy.py    AgentToolPolicy aggregate
│   │   │                           + evaluate_agent_tool_policies (DENY > ALLOW)
│   │   └── repository.py           IAgentToolPolicyRepository (ABC)
│   └── governance/
│       ├── change_log.py           ConfigChangeLog aggregate (append-only)
│       └── repository.py           IConfigChangeLogRepository (ABC)
│
├── application/
│   ├── tool/use_cases.py           Register · Get · List · Update · Delete + change-log 발생
│   ├── gateway/use_cases.py        InvokeToolUseCase · ExecuteApprovedUseCase
│   │                               + selected_reason · candidates · agent 예산 컨텍스트
│   ├── approval/use_cases.py       List · Get · Approve · Reject
│   ├── agent_tool_policy/
│   │   └── use_cases.py            Create · List · Get · Update · Delete + change-log 발생
│   └── governance/
│       └── use_cases.py            ListChangeLogsUseCase (페이지네이션)
│
├── infrastructure/
│   ├── persistence/
│   │   ├── database.py             SQLAlchemy 엔진 (SQLite/PostgreSQL 이중 호환)
│   │   ├── orm_models.py           ORM 정의 (governance 컬럼 + 신규 테이블)
│   │   └── repositories/           구체 리포지토리 (agent_tool_policy · change_log 포함)
│   └── execution/
│       └── mock_executor.py        MockExecutor (wall-clock timing 포함)
│
└── api/
    ├── deps.py                     FastAPI 의존성 배선
    ├── schemas.py                  Pydantic 스키마 (governance DTO 포함)
    └── v1/
        ├── gateway.py              /invoke · /execute — selection · rule_trace 노출
        ├── tools.py                /tools CRUD — X-Acting-User · X-Change-Reason 헤더
        ├── approvals.py            /approvals
        ├── audit_logs.py           /audit-logs 페이지네이션 + 신규 필드 노출
        ├── agents.py               /agents CRUD + /agents/{id}/usage
        ├── users.py
        ├── agent_tool_policies.py  /agent-tool-policies CRUD
        └── governance.py           /governance/change-logs 페이지네이션 조회

alembic/versions/
├── 0001_initial_schema.py
├── 0002_add_performance_indices.py  복합 인덱스 (tool_name+created_at) · approval FK
├── 0003_audit_enrichment.py         trace_id(INDEX) · policy_reason · duration_ms
└── 0004_governance_expansion.py     warn_cost_threshold · agent 예산 · tokens_used
                                     rule_trace · selected_reason · candidate_tools
                                     agent_tool_policies · config_change_logs

tests/                               154 tests, 0 failures (coverage 95%)
├── test_tool_call_aggregate.py      18 — 상태 머신 전환 경로
├── test_value_objects.py            12 — 해싱 · 불변성
├── test_policy.py                    9 — PolicyEngine 전체 흐름
├── test_policy_rules.py             22 — 룰 격리 + 커스텀 체인
├── test_domain_events.py             8 — 이벤트 발행 순서/내용
├── test_audit_enrichment.py         21 — trace_id · pagination · 에러 포맷
├── test_gateway.py                  10 — HTTP 통합 테스트
├── test_approvals.py                 6 — 승인 플로우
├── test_tools.py                     7 — Tool Registry
├── test_agent_tool_policy.py        15 — DENY > ALLOW + CRUD + e2e
├── test_agent_budget.py             13 — 룰 격리 + warn band + /usage
├── test_decision_tracking.py         6 — selected_reason · candidates · rule_trace
└── test_change_log.py                8 — Tool / Policy 변경 감사
```
