# AgentGate

> **AI Agent Tool Call Gateway** — policy enforcement, human-in-the-loop approval, cost control, and full audit trail for every tool invocation made by AI agents.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-112%20passed-brightgreen)](#tests)
[![DDD](https://img.shields.io/badge/architecture-DDD%20%2B%20Hexagonal-orange)](#architecture)

---

## Problem Statement

AI agents call internal tools (refunds, cancellations, data lookups) autonomously. Without a control plane, there is no way to:

- Block unauthorized calls before they reach the target system
- Require human approval for high-risk operations
- Track costs and enforce per-tool daily limits
- Audit every invocation with a full trace

AgentGate sits between the agent and the tool, enforcing these controls consistently.

---

## Core Flow

```
AI Agent ──▶ POST /api/v1/gateway/invoke
                  │
         ┌────────▼────────┐
         │  PolicyEngine   │  Chain of 7 rules
         │  (domain svc)   │  DENY / REQUIRE_APPROVAL / ALLOW
         └────────┬────────┘
      ┌───────────┼──────────────┐
      ▼           ▼              ▼
   SKIPPED    PENDING        MockExecutor
  (audit)   (approval gate)  (immediate)
      └───────────┴──────────────┘
                  │
       Audit Log  (tool_calls table)
       trace_id · policy_reason · duration_ms
```

---

## Architecture

Domain-Driven Design with Hexagonal Architecture (Ports & Adapters). Details in [ARCHITECTURE.md](ARCHITECTURE.md).

```
api  →  application  →  domain  ←  infrastructure
```

| Layer | Responsibility |
|-------|----------------|
| `domain/` | Aggregates, Value Objects, domain services — zero I/O |
| `application/` | Use Case command objects, single-responsibility orchestrators |
| `infrastructure/` | SQLAlchemy ORM, repository implementations, MockExecutor |
| `api/` | FastAPI routers — HTTP translation only, no business logic |

**Dependency rule:** every arrow points inward. Infrastructure imports domain; domain never imports infrastructure.

---

## Key Design Decisions

### 1. Policy Engine — Chain of Responsibility

The `PolicyEngine` iterates an ordered list of `PolicyRule` objects. Each rule either short-circuits with a decision or passes `None` to continue the chain.

```python
class PolicyEngine:
    def __init__(self, rules: Sequence[PolicyRule] = DEFAULT_RULES) -> None: ...
    def evaluate(self, ctx: PolicyContext) -> PolicyResult: ...

# Seven concrete rules, in evaluation order:
# ToolEnabledRule → UserEnabledRule → AgentEnabledRule → RoleCheckRule
# → DomainAccessRule → CostLimitRule → ApprovalRequiredRule
```

**Why:** Adding a new policy check (e.g. rate limiting, geo-fencing) requires only a new `PolicyRule` subclass — no modification to the engine or any existing rule. Tests can inject a custom rule list to test each rule in isolation.

### 2. ToolCall as Aggregate Root

`ToolCall` owns its complete lifecycle. All state transitions are methods on the aggregate, enforcing invariants at the boundary:

```
create() → deny() | request_approval() → approve()/reject() → record_execution()
```

`Approval` is an embedded entity (not a separate aggregate) because its lifecycle is inseparable from `ToolCall`. A single `repository.save()` persists both atomically.

**Why:** No service or repository can put the aggregate into an inconsistent state. The state machine is tested without a database.

### 3. Domain Events

The aggregate collects lightweight events on every state transition:

```python
tc.collect_events()
# → [ToolCallCreatedEvent, ApprovalRequestedEvent, ToolCallApprovedEvent, ToolCallExecutedEvent]
```

Events are collected from the outside (use case layer) and can be dispatched to an event bus without changing the aggregate. Approval status advances to `EXECUTED`/`FAILED` after `record_execution()` so the final state is unambiguous.

### 4. Audit Enrichment

Every invocation stores:
- `trace_id` — caller-supplied or auto-generated UUID, accepted via JSON body or `X-Trace-Id` header
- `policy_reason` — human-readable string from the rule that produced the decision
- `duration_ms` — executor wall-clock time recorded by the aggregate

### 5. Global Exception Handlers

Domain exceptions map to HTTP status codes once, in `main.py`:

| Exception | HTTP | Error Code |
|-----------|------|------------|
| `NotFoundError` | 404 | `NOT_FOUND` |
| `DomainError` | 422 | `DOMAIN_ERROR` |
| `ConflictError` / `ValueError` | 409 | `CONFLICT` |

All error responses use the same `{"code": "...", "message": "..."}` schema.

---

## Quick Start

### Docker (recommended)

```bash
# Start server + PostgreSQL (runs Alembic migrations automatically)
make up

# Open Swagger UI
open http://localhost:8000/docs

# Insert demo data
make seed
```

### Local Dev (no Docker)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start PostgreSQL container only
docker compose up db -d

cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

---

## API

### Gateway

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/gateway/invoke` | Invoke a tool — policy evaluated, then execute / pend / block |
| `POST` | `/api/v1/gateway/execute/{request_id}` | Execute an approved tool call |

### Tool Registry

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/tools` | Register a tool |
| `GET` | `/api/v1/tools` | List tools |
| `GET` | `/api/v1/tools/{tool_id}` | Get tool |
| `PATCH` | `/api/v1/tools/{tool_id}` | Update tool |
| `DELETE` | `/api/v1/tools/{tool_id}` | Delete tool |

### Approvals

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/approvals` | List approvals (`?pending_only=true`) |
| `GET` | `/api/v1/approvals/{approval_id}` | Get approval detail |
| `POST` | `/api/v1/approvals/{approval_id}/approve` | Approve |
| `POST` | `/api/v1/approvals/{approval_id}/reject` | Reject |

### Audit Log

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/audit-logs` | Paginated audit log (`limit`, `offset`) |
| `GET` | `/api/v1/audit-logs/{request_id}` | Get single entry |

---

## Scenario Walkthrough

### Low-risk — Immediate Execution

```bash
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: trace-001" \
  -d '{
    "agent_id": "cs-agent-001",
    "user_id": "user-001",
    "tool_name": "get_order_detail",
    "input": {"order_id": "ORDER-1234"}
  }'
# → { "policy_decision": "ALLOW", "execution_status": "SIMULATED",
#     "policy_reason": "All policy checks passed", "trace_id": "trace-001",
#     "duration_ms": 1 }
```

### High-risk — Approval Flow

```bash
# 1. Invoke → PENDING
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -d '{"agent_id":"cs-agent-001","user_id":"user-001","tool_name":"refund_order",
       "input":{"order_id":"ORDER-1234","amount":12000}}'
# → { "approval_status": "PENDING", "request_id": "uuid-..." }

# 2. List pending approvals
curl "http://localhost:8000/api/v1/approvals?pending_only=true"

# 3. Approve
curl -X POST "http://localhost:8000/api/v1/approvals/{approval_id}/approve" \
  -d '{"approver_id":"admin-001","reason":"verified"}'

# 4. Execute
curl -X POST "http://localhost:8000/api/v1/gateway/execute/{request_id}"
# → { "execution_status": "SIMULATED", "approval_status": "EXECUTED" }
```

---

## Tests

```bash
make test                                      # all tests in Docker
pytest --cov=app --cov-report=term-missing     # with coverage
```

| File | What it covers | Tests |
|------|----------------|-------|
| `test_tool_call_aggregate.py` | ToolCall state machine — all transitions | 18 |
| `test_value_objects.py` | InputData hashing, ExecutionResult immutability | 12 |
| `test_policy.py` | PolicyEngine end-to-end decisions | 9 |
| `test_policy_rules.py` | Each rule in isolation + custom rule chains | 22 |
| `test_domain_events.py` | Event emission on every state transition | 8 |
| `test_audit_enrichment.py` | trace_id, policy_reason, duration_ms, pagination, error format | 21 |
| `test_gateway.py` | Gateway integration — ALLOW/DENY/APPROVAL/full flow | 10 |
| `test_approvals.py` | Approval CRUD + double-approve guard | 6 |
| `test_tools.py` | Tool registry CRUD | 7 |

**112 tests, 0 failures.** All tests run against SQLite in-memory — no PostgreSQL required.

---

## Make Commands

```bash
make up       # Start server + DB (foreground)
make up-d     # Start server + DB (background)
make down     # Stop + delete volumes
make test     # Run tests inside container
make seed     # Insert demo data
make migrate  # Run Alembic migrations
make shell    # Shell into api container
make logs     # Stream logs
```

---

## Data Model (ERD)

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
input_data (JSON)        risk_level
input_hash               policy_decision   ALLOW | REQUIRE_APPROVAL | DENY
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

## Roadmap

| Feature | Where to add |
|---------|-------------|
| Real tool execution | Implement `IToolExecutor`, wire in `deps.py` |
| LangGraph / OpenAI agent | Add `/mcp` or `/agent` router in `api/v1/` |
| JWT authentication | FastAPI middleware + `Depends` in `deps.py` |
| Async support | Swap `Session` → `AsyncSession` in infrastructure |
| Domain event bus | `domain/events.py`, publish from aggregate via `collect_events()` |
| Slack / Email alerts | Subscribe to `ApprovalRequestedEvent` |
| OpenTelemetry | Propagate `trace_id` as span context |
