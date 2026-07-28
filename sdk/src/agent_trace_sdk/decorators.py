"""Decorators for easy tracing of agent functions."""
from __future__ import annotations

from typing import Callable, TypeVar, ParamSpec
from functools import wraps

from .tracer import Tracer

P = ParamSpec("P")
R = TypeVar("R")


def trace_agent_run(
    name: str | None = None,
    endpoint: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace a function as an agent run.

    Usage:
        @trace_agent_run(name="my_agent")
        def my_agent(input: str) -> str:
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        run_name = name or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with Tracer(name=run_name, endpoint=endpoint) as span:
                if "trace_span" in func.__code__.co_varnames:
                    kwargs["trace_span"] = span
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator