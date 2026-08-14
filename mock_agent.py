"""Mock AI agent for testing AgentTracer end-to-end.

Every "LLM call" and "tool call" returns a static, canned response —
no real LLM or external services are needed. The agent is deterministic:
it routes to tools based on prompt keywords so you can exercise different
trace trees.

Usage:
    python mock_agent.py "what is the weather in Tunis?"
    python mock_agent.py "calculate 2 + 2"
    python mock_agent.py "search for fastapi docs"
"""

import argparse
import time
from typing import Any

from agent_trace_sdk import (
    init_tracing,
    record_input,
    record_output,
    shutdown_tracing,
    trace_agent_run,
    trace_span,
)


# --- Static "LLM" (canned responses, no network) -----------------------------


@trace_span(name="llm_plan", span_type="llm_call")
def llm_plan(prompt: str) -> list[str]:
    """'Reason' about which tools to use — purely keyword-based."""
    record_input({"prompt": prompt})
    lowered = prompt.lower()
    if "weather" in lowered:
        plan = ["get_weather", "get_time"]
    elif "calcul" in lowered or "sum" in lowered:
        plan = ["calculator"]
    elif "search" in lowered or "docs" in lowered:
        plan = ["search_web"]
    else:
        plan = ["search_web", "get_time"]
    record_output({"plan": plan})
    return plan


@trace_span(name="llm_respond", span_type="llm_call")
def llm_respond(prompt: str, steps: list[dict[str, Any]]) -> str:
    """Build a final canned answer from the recorded tool results."""
    record_input({"prompt": prompt, "steps": steps})
    answer = "I looked it up. Here is what I found:\n"
    for step in steps:
        answer += f"- {step['tool']}: {step['result']}\n"
    record_output({"answer": answer})
    return answer.strip()


# --- Static "tools" (canned responses, no network) ---------------------------


@trace_span(name="get_weather", span_type="tool_call")
def get_weather(city: str) -> dict[str, Any]:
    record_input({"city": city})
    result = {"city": city, "temperature_c": 24, "condition": "partly cloudy"}
    record_output(result)
    return result


@trace_span(name="get_time", span_type="tool_call")
def get_time() -> dict[str, Any]:
    result = {"iso": "2026-08-11T12:00:00Z", "note": "static"}
    record_output(result)
    return result


@trace_span(name="calculator", span_type="tool_call")
def calculator(expression: str) -> dict[str, Any]:
    record_input({"expression": expression})
    result = {"expression": expression, "result": 42}
    record_output(result)
    return result


@trace_span(name="search_web", span_type="tool_call")
def search_web(query: str) -> dict[str, Any]:
    record_input({"query": query})
    result = {"hits": [f"Mock hit 1 for {query!r}", "Mock hit 2", "Mock hit 3"]}
    record_output(result)
    return result


TOOLS = {
    "get_weather": lambda: get_weather("Tunis"),
    "get_time": get_time,
    "calculator": lambda: calculator("2 + 2"),
    "search_web": lambda: search_web("fastapi docs"),
}


# --- The agent run -----------------------------------------------------------


@trace_agent_run(name="mock_agent")
def run_agent(prompt: str) -> str:
    record_input({"prompt": prompt})
    steps: list[dict[str, Any]] = []
    for tool in llm_plan(prompt):
        result = TOOLS[tool]()
        steps.append({"tool": tool, "result": result})
        time.sleep(0.05)  # space out timestamps so durations are visible
    answer = llm_respond(prompt, steps)
    record_output({"answer": answer})
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock AgentTracer agent")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="what is the weather in Tunis?",
        help="prompt to 'answer' (keywords route to different tools)",
    )
    args = parser.parse_args()

    init_tracing(service_name="mock-agent")
    try:
        answer = run_agent(args.prompt)
    finally:
        shutdown_tracing()  # flush buffered spans to the backend before exit
    print(answer)


if __name__ == "__main__":
    main()
