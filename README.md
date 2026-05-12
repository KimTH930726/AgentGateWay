# AgentGate

> AI Agent가 내부 API를 호출하기 전에 **권한 · 정책 · 비용 · 승인 · 감사**를 통제하는 백엔드 게이트웨이

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-61%20passed-brightgreen)](#테스트)

---

## 핵심 시나리오

```
AI Agent → POST /api/v1/gateway/invoke
                │
         ┌──────▼──────┐
         │ PolicyEngine │  DENY / REQUIRE_APPROVAL / ALLOW
         └──────┬──────┘
    ┌───────────┼────────────┐
    ▼           ▼            ▼
  SKIPPED    승인 대기     MockExecutor
             (관리자 승인)  (즉시 실행)
    └───────────┴────────────┘
                │
           Audit Log (tool_calls 테이블)
```

---

## 아키텍처

DDD(Domain-Driven Design) 기반 4-레이어 구조. 자세한 내용은 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.

```
api  →  application  →  domain  ←  infrastructure
```

- **domain** : 순수 비즈니스 로직 (외부 의존 없음)
- **application** : Use Case 커맨드 객체 + 단일 책임 클래스
- **infrastructure** : SQLAlchemy ORM, Repository 구현체, MockExecutor
- **api** : FastAPI 라우터 (HTTP 변환만 담당)

---

## 빠른 시작

### 전제 조건
- Docker Desktop

```bash
# 1. 서버 기동 (DB 마이그레이션 자동 포함)
make up

# 2. Swagger UI 열기
open http://localhost:8000/docs

# 3. 데모 데이터 삽입
make seed
```

### 로컬 개발 (Docker 없이)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# PostgreSQL 컨테이너만 실행
docker compose up db -d

cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

---

## 테스트

```bash
# 전체 테스트 (SQLite 인메모리, PostgreSQL 불필요)
make test

# 커버리지 포함
pytest --cov=app --cov-report=term-missing
```

| 파일 | 내용 |
|------|------|
| `test_tool_call_aggregate.py` | ToolCall 도메인 애그리게이트 단위 테스트 (18개) |
| `test_value_objects.py` | InputData·ExecutionResult 값 객체 테스트 (12개) |
| `test_policy.py` | PolicyEngine 단위 테스트 (9개) |
| `test_gateway.py` | Gateway 통합 테스트 (11개) |
| `test_approvals.py` | 승인 플로우 통합 테스트 (6개) |
| `test_tools.py` | Tool Registry CRUD 테스트 (7개) |

---

## API 목록

### Tool Registry

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/tools` | Tool 등록 |
| `GET` | `/api/v1/tools` | Tool 목록 |
| `GET` | `/api/v1/tools/{tool_id}` | Tool 조회 |
| `PATCH` | `/api/v1/tools/{tool_id}` | Tool 수정 |
| `DELETE` | `/api/v1/tools/{tool_id}` | Tool 삭제 |

### Gateway (핵심)

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/gateway/invoke` | Tool 호출 — Policy 평가 후 실행/승인요청/차단 |
| `POST` | `/api/v1/gateway/execute/{request_id}` | 승인된 Tool 호출 실행 |

### Approvals

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/approvals` | 승인 목록 (`?pending_only=true`) |
| `GET` | `/api/v1/approvals/{approval_id}` | 승인 상세 |
| `POST` | `/api/v1/approvals/{approval_id}/approve` | 승인 |
| `POST` | `/api/v1/approvals/{approval_id}/reject` | 거절 |

### 감사 로그

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/v1/audit-logs` | 감사 로그 목록 |
| `GET` | `/api/v1/audit-logs/{request_id}` | 감사 로그 상세 |

---

## 핵심 시나리오 예시

### 낮은 위험도 — 즉시 실행

```bash
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "cs-agent-001",
    "user_id": "user-001",
    "tool_name": "get_order_detail",
    "input": {"order_id": "ORDER-1234"}
  }'
# → policy_decision: "ALLOW", execution_status: "SIMULATED"
```

### 높은 위험도 — 승인 플로우

```bash
# 1. 호출 → PENDING
curl -X POST http://localhost:8000/api/v1/gateway/invoke \
  -d '{"agent_id":"cs-agent-001","user_id":"user-001","tool_name":"refund_order","input":{"order_id":"ORDER-1234","amount":12000}}'
# → approval_status: "PENDING", request_id: "..."

# 2. 승인 목록 조회 → approval_id 확인
curl http://localhost:8000/api/v1/approvals?pending_only=true

# 3. 승인
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/approve \
  -d '{"approver_id":"admin-001","reason":"정상 환불"}'

# 4. 실행
curl -X POST http://localhost:8000/api/v1/gateway/execute/{request_id}
# → execution_status: "SIMULATED"
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

## ERD

```
tools               agents              users
──────              ──────              ─────
tool_id (UK)        agent_id (UK)       user_id (UK)
name                name                roles (JSON)
domain              allowed_domains
risk_level          enabled
required_role
approval_required
daily_cost_limit
enabled

tool_calls
──────────────────────────────────────────
request_id (UK)
agent_id · user_id · tool_name
input_data (JSON) · input_hash
risk_level
policy_decision     ALLOW | REQUIRE_APPROVAL | DENY
approval_status     PENDING | APPROVED | REJECTED | ...
execution_status    SIMULATED | SUCCESS | FAILED | SKIPPED
estimated_cost · actual_cost
created_at · executed_at

approvals
──────────────────────────────────
id
tool_call_id → tool_calls.id (index)
approver_id · status · reason
created_at · updated_at
```

---

## 다음 단계

| 항목 | 설명 |
|------|------|
| LLM 연동 | LangGraph Agent에서 AgentGate를 Tool Server로 사용 |
| MCP 지원 | Model Context Protocol Tool Server 인터페이스 |
| JWT 인증 | API Key / JWT 미들웨어 추가 |
| 실시간 알림 | 승인 대기 시 Slack / Email 알림 |
| Async 전환 | `AsyncSession` + `async def` 라우터 |
| OpenTelemetry | 분산 추적 및 메트릭 |
