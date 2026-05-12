# AgentGate — Architecture Guide

## Overview

AgentGate is a backend gateway that intercepts every AI Agent tool call and enforces
**policy, cost, approval, and audit** before the tool is executed.
The codebase follows **Domain-Driven Design (DDD)** with a strict layered architecture
and the **Ports & Adapters (Hexagonal)** pattern.

---

## Layer Map

```
┌──────────────────────────────────────────────────────────┐
│  api/                HTTP boundary                        │
│  (FastAPI routers, Pydantic schemas, deps.py wiring)      │
└──────────────┬───────────────────────────────────────────┘
               │ calls
┌──────────────▼───────────────────────────────────────────┐
│  application/        Use-case layer                       │
│  (Command DTOs + single-responsibility use case classes)  │
└──────────────┬───────────────────────────────────────────┘
               │ depends on interfaces from
┌──────────────▼───────────────────────────────────────────┐
│  domain/             Core business logic (no I/O)         │
│  - Aggregates, Entities, Value Objects                    │
│  - Repository / Executor interfaces (ports)               │
│  - PolicyEngine domain service (rule chain)               │
│  - Domain events (lightweight dataclasses)                │
└──────────────────────────────────────────────────────────┘
               ▲ implements interfaces
┌──────────────┴───────────────────────────────────────────┐
│  infrastructure/     Adapters                             │
│  - persistence/: SQLAlchemy ORM + repositories            │
│  - execution/:   MockExecutor (swap for real HTTP later)  │
└──────────────────────────────────────────────────────────┘
```

**Rule:** dependencies only point inward.
Infrastructure imports domain; domain never imports infrastructure.

---

## Domain Model

### Aggregates & Entities

| Name | Type | Responsibility |
|------|------|----------------|
| `ToolCall` | Aggregate Root | Full lifecycle of one tool invocation |
| `Approval` | Entity (inside ToolCall) | Tracks the human-approval decision |
| `Tool` | Aggregate | Tool registry entry |
| `Agent` | Aggregate | Registered AI agent |
| `User` | Aggregate | Caller with role list |

### Value Objects

| Name | Description |
|------|-------------|
| `InputData` | Immutable payload wrapper; computes SHA-256 hash for audit |
| `ExecutionResult` | Immutable executor output (status, output dict, cost, duration_ms) |

### Domain Service

`PolicyEngine.evaluate(PolicyContext) → PolicyResult`

Pure function; no side effects. Iterates an ordered rule chain.
Returns one of:
- `ALLOW` — execute immediately
- `REQUIRE_APPROVAL` — gate on human decision
- `DENY` — block unconditionally

### Domain Events

Lightweight frozen dataclasses emitted by the `ToolCall` aggregate.
Collected via `tool_call.collect_events()` — the call clears the queue.

| Event | Emitted when |
|-------|-------------|
| `ToolCallCreatedEvent` | `ToolCall.create()` |
| `ToolCallDeniedEvent` | `deny()` |
| `ApprovalRequestedEvent` | `request_approval()` |
| `ToolCallApprovedEvent` | `approve()` |
| `ToolCallRejectedEvent` | `reject()` |
| `ToolCallExecutedEvent` | `record_execution()` |

---

## ToolCall State Machine

```
              ToolCall.create()
                     │
          ┌──────────┼──────────┐
          │          │          │
        DENY     REQUIRE_     ALLOW
          │      APPROVAL       │
          ▼          │          ▼
      SKIPPED    request_    record_execution()
                 approval()       │
                     │         SIMULATED / SUCCESS / FAILED
               PENDING          (approval untouched)
              ┌──────┴──────┐
              │             │
           approve()     reject()
              │             │
           APPROVED      REJECTED
              │
         record_execution()
              │
         SIMULATED / SUCCESS / FAILED
         (approval → EXECUTED / FAILED)
```

State transitions live **inside the aggregate** (`tool_call.py`).
No service or repository is allowed to mutate state directly.

---

## Policy Engine — Chain of Responsibility

```
domain/policy/
├── context.py     PolicyContext (input DTO), PolicyResult (output DTO)
├── rules.py       PolicyRule (ABC) + 7 concrete rules + DEFAULT_RULES list
└── policy_engine.py  PolicyEngine — iterates rule chain, returns first match
```

```
Decision tree (DEFAULT_RULES order):

Tool disabled?              → DENY  (ToolEnabledRule)
User account disabled?      → DENY  (UserEnabledRule)
Agent disabled?             → DENY  (AgentEnabledRule)
User missing required_role? → DENY  (RoleCheckRule)
Agent domain not allowed?   → DENY  (DomainAccessRule)
Daily cost limit reached?   → DENY  (CostLimitRule)
risk=HIGH or approval flag? → REQUIRE_APPROVAL  (ApprovalRequiredRule)
Otherwise                   → ALLOW
```

To add a new policy check: create a `PolicyRule` subclass, add it to `DEFAULT_RULES`.
To override in tests: `PolicyEngine(rules=[MyRule()])`.

---

## Repository Pattern (Port / Adapter)

Each domain sub-package owns its own interface:

```
domain/tool/repository.py       IToolRepository (ABC)
domain/agent/repository.py      IAgentRepository (ABC)
domain/user/repository.py       IUserRepository (ABC)
domain/tool_call/repository.py  IToolCallRepository (ABC)
domain/tool_call/executor.py    IToolExecutor (ABC)
```

Concrete adapters live in `infrastructure/persistence/repositories/` and
`infrastructure/execution/`. The application layer only imports the ABCs.

---

## Key Design Decisions

### Why `Approval` is inside `ToolCall`, not a separate aggregate

A `ToolCall` always has at most one `Approval`; their lifecycles are tightly coupled.
Keeping `Approval` as an embedded entity means `ToolCall.approve()` can enforce
invariants (e.g. "can't approve an already-approved call") without a cross-aggregate
transaction.

### Why `IToolCallRepository.save()` upserts both tables

The aggregate is the unit of consistency. A single `save()` persists the full
aggregate state atomically (`tool_calls` row + `approvals` row). Callers never touch
ORM objects directly.

### Why `Approval.status` advances to `EXECUTED`/`FAILED`

After `record_execution()`, the outcome is unambiguous: the approval that gated this
call is either `EXECUTED` (tool ran successfully) or `FAILED`. This eliminates the
ambiguous `APPROVED` terminal state and makes audit queries simpler.

### N+1 prevention

`ToolCallORM.approval` is configured with `lazy="selectin"`, so SQLAlchemy
issues one IN-query for approvals rather than one query per row.

### Audit enrichment fields

| Field | Source |
|-------|--------|
| `trace_id` | Body `trace_id` field, then `X-Trace-Id` header, then auto-generated UUID |
| `policy_reason` | `PolicyResult.reason` from the first matching rule |
| `duration_ms` | `MockExecutor` wall-clock time; stored in `ExecutionResult.duration_ms` |

### Global exception handlers

All domain exceptions map to HTTP status in `main.py` — routers contain no
`try/except` blocks. Consistent `{"code": "...", "message": "..."}` error schema.

---

## Extension Points

| Feature | Where to add |
|---------|-------------|
| Real tool execution | Implement `IToolExecutor`, wire in `deps.py` |
| LangGraph / OpenAI agent | Add a `/mcp` or `/agent` router in `api/v1/` |
| JWT authentication | FastAPI middleware + `Depends` in `api/deps.py` |
| Async support | Swap `Session` for `AsyncSession` in `infrastructure/persistence/` |
| Event bus | Consume `tool_call.collect_events()` in use case, publish to broker |
| Rate limiting | Middleware in `app/main.py` |
| Geo-fencing / IP check | New `PolicyRule` subclass, append to `DEFAULT_RULES` |

---

## Directory Reference

```
app/
├── domain/
│   ├── enums.py                  RiskLevel, PolicyDecision, ApprovalStatus, ExecutionStatus
│   ├── shared/
│   │   ├── exceptions.py         AgentGateError hierarchy with code attributes
│   │   └── value_objects.py      InputData, ExecutionResult (with duration_ms)
│   ├── tool/
│   │   ├── tool.py               Tool aggregate
│   │   └── repository.py         IToolRepository (ABC)
│   ├── agent/
│   │   ├── agent.py              Agent aggregate
│   │   └── repository.py         IAgentRepository (ABC)
│   ├── user/
│   │   ├── user.py               User aggregate
│   │   └── repository.py         IUserRepository (ABC)
│   ├── tool_call/
│   │   ├── tool_call.py          ToolCall aggregate root + Approval entity
│   │   ├── events.py             Domain events (ToolCallCreated, Approved, …)
│   │   ├── repository.py         IToolCallRepository (ABC) + count_all
│   │   └── executor.py           IToolExecutor (ABC)
│   └── policy/
│       ├── context.py            PolicyContext, PolicyResult
│       ├── rules.py              PolicyRule (ABC) + 7 concrete rules + DEFAULT_RULES
│       └── policy_engine.py      PolicyEngine — iterates rule chain
├── application/
│   ├── tool/use_cases.py         Register/Get/List/Update/Delete tool
│   ├── gateway/use_cases.py      InvokeToolUseCase (trace_id, timing), ExecuteApproved
│   └── approval/use_cases.py     List/Get/Approve/Reject
├── infrastructure/
│   ├── persistence/
│   │   ├── database.py           SQLAlchemy engine + session factory
│   │   ├── orm_models.py         ORM table definitions (trace_id, policy_reason, duration_ms)
│   │   └── repositories/         Concrete repository implementations
│   └── execution/
│       └── mock_executor.py      MockExecutor with wall-clock timing
└── api/
    ├── deps.py                   FastAPI dependency wiring
    ├── schemas.py                Pydantic models (ErrorCode, ErrorResponse, AuditLogPage)
    └── v1/                       Route handlers (HTTP translation, no try/except)

alembic/versions/
├── 0001_initial_schema.py
├── 0002_add_performance_indices.py
└── 0003_audit_enrichment.py     trace_id, policy_reason, duration_ms columns

tests/
├── test_tool_call_aggregate.py  (18 tests)
├── test_value_objects.py        (12 tests)
├── test_policy.py               (9 tests)
├── test_policy_rules.py         (22 tests — rule isolation + custom chains)
├── test_domain_events.py        (8 tests — event emission)
├── test_audit_enrichment.py     (21 tests — trace_id, policy_reason, pagination, errors)
├── test_gateway.py              (10 tests)
├── test_approvals.py            (6 tests)
└── test_tools.py                (7 tests)
```
