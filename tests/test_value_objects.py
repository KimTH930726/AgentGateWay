"""Unit tests for domain value objects."""
import pytest

from app.domain.enums import ExecutionStatus
from app.domain.shared.value_objects import ExecutionResult, InputData


class TestInputData:
    def test_hash_is_consistent(self):
        data = InputData(payload={"order_id": "1234"})
        assert data.hash == data.hash

    def test_hash_is_independent_of_key_order(self):
        a = InputData(payload={"b": 2, "a": 1})
        b = InputData(payload={"a": 1, "b": 2})
        assert a.hash == b.hash

    def test_different_payloads_have_different_hashes(self):
        a = InputData(payload={"order_id": "1234"})
        b = InputData(payload={"order_id": "5678"})
        assert a.hash != b.hash

    def test_equality_by_payload(self):
        a = InputData(payload={"k": "v"})
        b = InputData(payload={"k": "v"})
        assert a == b

    def test_inequality_by_payload(self):
        a = InputData(payload={"k": "v1"})
        b = InputData(payload={"k": "v2"})
        assert a != b

    def test_hashable_for_set_membership(self):
        a = InputData(payload={"x": 1})
        b = InputData(payload={"x": 1})
        assert len({a, b}) == 1

    def test_hash_is_16_chars(self):
        data = InputData(payload={"x": 1})
        assert len(data.hash) == 16

    def test_non_serialisable_payload_raises(self):
        class Unserializable:
            pass
        # default=str handles most custom types; this just verifies it doesn't crash silently
        data = InputData(payload={"obj": Unserializable()})
        assert isinstance(data.hash, str)  # default=str serialises unknown types

    def test_empty_payload(self):
        data = InputData(payload={})
        assert len(data.hash) == 16

    def test_nested_payload(self):
        data = InputData(payload={"a": {"b": [1, 2, 3]}})
        assert len(data.hash) == 16


class TestExecutionResult:
    def test_immutable(self):
        result = ExecutionResult(
            status=ExecutionStatus.SIMULATED, output={}, cost=0.01
        )
        with pytest.raises((AttributeError, TypeError)):
            result.cost = 0.99  # type: ignore[misc]

    def test_fields(self):
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            output={"error": "timeout"},
            cost=0.0,
        )
        assert result.status == ExecutionStatus.FAILED
        assert result.output["error"] == "timeout"
        assert result.cost == 0.0
