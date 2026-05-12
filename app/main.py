from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorCode, ErrorResponse
from app.api.v1 import agents, approvals, audit_logs, gateway, tools, users
from app.domain.shared.exceptions import ConflictError, DomainError, NotFoundError

app = FastAPI(
    title="AgentGate",
    description="AI Agent Gateway — policy, approval, and audit for internal tool calls",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(code=ErrorCode.NOT_FOUND, message=str(exc)).model_dump(),
    )


@app.exception_handler(ConflictError)
async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=ErrorResponse(code=ErrorCode.CONFLICT, message=str(exc)).model_dump(),
    )


@app.exception_handler(DomainError)
async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(code=ErrorCode.DOMAIN_ERROR, message=str(exc)).model_dump(),
    )


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=ErrorResponse(code=ErrorCode.CONFLICT, message=str(exc)).model_dump(),
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
