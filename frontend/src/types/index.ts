// Type definitions for AgentTracer

export interface Run {
  id: string;
  name: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  node_count: number | null;
}

export interface SpanEvent {
  id: string;
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface TraceNode {
  id: string;
  name: string;
  span_type: "agent_run" | "step" | "tool_call" | "llm_call";
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  children: TraceNode[];
  events: SpanEvent[];
}

export interface TraceTree {
  run_id: string;
  root: TraceNode | null;
}

export interface RunsListResponse {
  runs: Run[];
  total: number;
  limit: number;
  offset: number;
}