# AgentGate — Architecture Guide

## Overview

AgentGate is a backend gateway that intercepts every AI Agent tool call and enforces
**policy, cost, approval, and audit** before the tool is executed.
The codebase follows **Domain-Driven Design (DDD)** with a strict layered architecture.

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
│  - PolicyEngine domain service                            │
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
| `ExecutionResult` | Immutable executor output (status, output dict, cost) |

### Domain Service

`PolicyEngine.evaluate(PolicyContext) → PolicyResult`

Pure function; no side effects. Returns one of:
- `ALLOW` — execute immediately
- `REQUIRE_APPROVAL` — gate on human decision
- `DENY` — block unconditionally

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
               PENDING
              ┌──────┴──────┐
              │             │
           approve()     reject()
              │             │
           APPROVED      REJECTED
              │
         record_execution()
              │
         SIMULATED / SUCCESS / FAILED
```

State transitions live **inside the aggregate** (`tool_call.py`).
No service or repository is allowed to mutate state directly.

---

## Policy Engine Decision Tree

```
Tool disabled?           → DENY
User disabled?           → DENY
Agent disabled?          → DENY
User missing required_role? → DENY
Agent domain not allowed?   → DENY
Daily cost limit reached?   → DENY
risk_level=HIGH or approval_required=true? → REQUIRE_APPROVAL
Otherwise                → ALLOW
```

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
aggregate state atomically (tool_calls row + approvals row). Callers never touch
ORM objects directly.

### N+1 prevention

`ToolCallORM.approval` is configured with `lazy="selectin"`, so SQLAlchemy
issues one IN-query for approvals rather than one query per row.

---

## Extension Points

| Feature | Where to add |
|---------|-------------|
| Real tool execution | Implement `IToolExecutor`, wire in `deps.py` |
| LangGraph / OpenAI agent | Add a `/mcp` or `/agent` router in `api/v1/` |
| JWT authentication | FastAPI middleware + `Depends` in `api/deps.py` |
| Async support | Swap `Session` for `AsyncSession` in `infrastructure/persistence/` |
| Event bus (domain events) | Add `domain/events.py`, publish from aggregate methods |
| Rate limiting | Middleware in `app/main.py` |

---

## Directory Reference

```
app/
├── domain/
│   ├── enums.py                  RiskLevel, PolicyDecision, ApprovalStatus, ExecutionStatus
│   ├── shared/
│   │   ├── exceptions.py         DomainError, NotFoundError, PolicyViolationError
│   │   └── value_objects.py      InputData, ExecutionResult
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
│   │   ├── repository.py         IToolCallRepository (ABC)
│   │   └── executor.py           IToolExecutor (ABC)
│   └── policy/
│       └── policy_engine.py      PolicyEngine domain service
├── application/
│   ├── tool/use_cases.py         Register/Get/List/Update/Delete tool
│   ├── gateway/use_cases.py      InvokeTool, ExecuteApproved
│   └── approval/use_cases.py     List/Get/Approve/Reject
├── infrastructure/
│   ├── persistence/
│   │   ├── database.py           SQLAlchemy engine + session factory
│   │   ├── orm_models.py         ORM table definitions
│   │   └── repositories/         Concrete repository implementations
│   └── execution/
│       └── mock_executor.py      MockExecutor (implements IToolExecutor)
└── api/
    ├── deps.py                   FastAPI dependency wiring
    ├── schemas.py                Pydantic request/response models
    └── v1/                       Route handlers (HTTP translation only)
```
