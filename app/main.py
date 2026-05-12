from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import agents, approvals, audit_logs, gateway, tools, users

app = FastAPI(
    title="AgentGate",
    description="AI Agent Gateway — policy, approval, and audit for internal tool calls",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_V1 = "/api/v1"
app.include_router(tools.router, prefix=_V1)
app.include_router(agents.router, prefix=_V1)
app.include_router(users.router, prefix=_V1)
app.include_router(gateway.router, prefix=_V1)
app.include_router(approvals.router, prefix=_V1)
app.include_router(audit_logs.router, prefix=_V1)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
