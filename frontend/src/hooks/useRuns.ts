import { useState, useEffect, useCallback } from "react";
import { Run, TraceTree, RunsListResponse } from "../types";
import { listRuns, getRunTree } from "../api/client";

interface UseRunsParams {
  limit?: number;
  offset?: number;
  status?: string;
}

interface UseRunsResult {
  data: RunsListResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useRuns(params: UseRunsParams = {}): UseRunsResult {
  const { limit = 20, offset = 0, status } = params;
  const [data, setData] = useState<RunsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listRuns(limit, offset, status);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch runs"));
    } finally {
      setLoading(false);
    }
  }, [limit, offset, status]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  return { data, loading, error, refetch: fetchRuns };
}

interface UseRunTreeResult {
  data: TraceTree | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useRunTree(runId: string | null): UseRunTreeResult {
  const [data, setData] = useState<TraceTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchTree = useCallback(async () => {
    if (!runId) {
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await getRunTree(runId);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch tree"));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  return { data, loading, error, refetch: fetchTree };
}