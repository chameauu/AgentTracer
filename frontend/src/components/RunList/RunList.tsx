import { useState } from 'react';
import { useRuns } from '../../hooks/useRuns';
import { Run } from '../../types';
import { RunListItem } from './RunListItem';
import './RunList.css';

interface RunListProps {
  onSelectRun: (runId: string) => void;
  selectedRunId: string | null;
}

export const RunList: React.FC<RunListProps> = ({ onSelectRun, selectedRunId }) => {
  const { data, loading, error, refetch } = useRuns({ limit: 20 });

  const handleRetry = () => {
    refetch();
  };

  if (loading && !data) {
    return <div className="run-list-loading">Loading runs...</div>;
  }

  if (error) {
    return (
      <div className="run-list-error">
        <p>Error loading runs: {error.message}</p>
        <button onClick={handleRetry}>Retry</button>
      </div>
    );
  }

  if (!data || data.runs.length === 0) {
    return (
      <div className="run-list-empty">
        <p>No runs found. Try tracing an agent with the SDK.</p>
        <button onClick={handleRetry}>Refresh</button>
      </div>
    );
  }

  return (
    <div className="run-list-container">
      <div className="run-list-header">
        <h2>Runs ({data.total})</h2>
        <button onClick={handleRetry} className="refresh-button">
          ⟲ Refresh
        </button>
      </div>
      <div className="run-list-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Started</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((run: Run) => (
              <RunListItem
                key={run.id}
                run={run}
                selected={run.id === selectedRunId}
                onSelect={onSelectRun}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};