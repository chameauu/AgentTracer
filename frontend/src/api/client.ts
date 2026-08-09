import { Run, RunsListResponse, TraceTree } from "../types";

const API_BASE = "/api/v1";

export async function listRuns(limit = 20, offset = 0, status?: string): Promise<RunsListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) params.set("status", status);
  
  const response = await fetch(`${API_BASE}/runs?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to list runs: ${response.statusText}`);
  }
  return response.json();
}

export async function getRun(runId: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  if (!response.ok) {
    throw new Error(`Failed to get run: ${response.statusText}`);
  }
  return response.json();
}

export async function getRunTree(runId: string): Promise<TraceTree> {
  const response = await fetch(`${API_BASE}/runs/${runId}/tree`);
  if (!response.ok) {
    throw new Error(`Failed to get run tree: ${response.statusText}`);
  }
  return response.json();
}

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }
  return response.json();
}