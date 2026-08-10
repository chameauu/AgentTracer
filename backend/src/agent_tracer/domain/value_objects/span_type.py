from enum import Enum


class SpanType(str, Enum):
    AGENT_RUN = "agent_run"
    STEP = "step"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
