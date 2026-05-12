import time
from typing import Any, Callable, Dict

from app.domain.enums import ExecutionStatus
from app.domain.shared.value_objects import ExecutionResult
from app.domain.tool_call.executor import IToolExecutor

_Handler = Callable[[Dict[str, Any]], ExecutionResult]
_REGISTRY: Dict[str, _Handler] = {}


def _handler(tool_name: str):
    def decorator(fn: _Handler) -> _Handler:
        _REGISTRY[tool_name] = fn
        return fn
    return decorator


@_handler("refund_order")
def _refund_order(inp: Dict) -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.SIMULATED,
        output={"status": "SIMULATED_SUCCESS", "order_id": inp.get("order_id"), "refunded_amount": inp.get("amount", 0)},
        cost=0.01,
    )


@_handler("get_order_detail")
def _get_order_detail(inp: Dict) -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.SIMULATED,
        output={
            "order_id": inp.get("order_id"),
            "customer": "test-customer",
            "items": [{"sku": "ITEM-001", "qty": 2, "price": 15000}],
            "total": 30000,
            "status": "DELIVERED",
        },
        cost=0.001,
    )


@_handler("cancel_order")
def _cancel_order(inp: Dict) -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.SIMULATED,
        output={"status": "SIMULATED_CANCELLED", "order_id": inp.get("order_id")},
        cost=0.005,
    )


@_handler("send_coupon")
def _send_coupon(inp: Dict) -> ExecutionResult:
    discount = inp.get("discount_rate", 10)
    return ExecutionResult(
        status=ExecutionStatus.SIMULATED,
        output={"status": "SIMULATED_SENT", "coupon_code": f"COUPON-{discount}PCT"},
        cost=0.002,
    )


class MockExecutor(IToolExecutor):
    """Adapter — implements IToolExecutor with canned responses."""

    def execute(self, tool_name: str, input_data: Dict[str, Any]) -> ExecutionResult:
        start = time.monotonic()
        handler = _REGISTRY.get(tool_name)
        if handler is None:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                output={"error": f"No mock handler registered for tool: {tool_name}"},
                cost=0.0,
                duration_ms=duration_ms,
            )
        result = handler(input_data)
        duration_ms = int((time.monotonic() - start) * 1000)
        # Recreate with actual timing since ExecutionResult is frozen
        return ExecutionResult(
            status=result.status,
            output=result.output,
            cost=result.cost,
            duration_ms=duration_ms,
        )
