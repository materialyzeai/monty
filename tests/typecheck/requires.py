"""Static contracts for the dependency guard; checked by the lint workflow."""

from __future__ import annotations

from typing import TypeVar, assert_type

from monty.dev import requires


@requires(True, "missing")
def calculate(value: int, *, scale: float = 2.0) -> float:
    return value * scale


assert_type(calculate(3, scale=4.0), float)
calculate("invalid")  # type: ignore[arg-type]
calculate(3, 4.0)  # type: ignore[call-arg]
calculate(3, unknown=4.0)  # type: ignore[call-arg]


class Result:
    def __init__(self, value: int) -> None:
        self.value = value


GuardedResult = requires(True, "missing")(Result)
assert_type(GuardedResult(3), Result)
GuardedResult("invalid")  # type: ignore[arg-type]


T = TypeVar("T")


@requires(True, "missing")
def identity(value: T) -> T:
    return value


assert_type(identity(3), int)
assert_type(identity("value"), str)
