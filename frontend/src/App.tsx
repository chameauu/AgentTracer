import { useState } from 'react';
import { RunList } from './components/RunList';
import { TraceTree } from './components/TraceTree';
import { DetailsPanel } from './components/DetailsPanel';
import { useRunTree } from './hooks/useRuns';
import './App.css';

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const { data: runTree, loading: treeLoading, error: treeError, refetch: refetchTree } =
    useRunTree(selectedRunId);

  const handleRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setSelectedNodeId(null); // Clear node selection when run changes
  };

  const handleNodeSelect = (nodeId: string) => {
    setSelectedNodeId(nodeId);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>AgentTracer</h1>
        <p className="app-version">v0.1.0</p>
      </header>
      
      <main className="app-main">
        <aside className="sidebar">
          <RunList 
            onSelectRun={handleRunSelect}
            selectedRunId={selectedRunId}
          />
        </aside>
        
        <section className="trace-view">
          <div className="trace-tree-header">
            <h2>Trace Tree</h2>
          </div>
          <div className="trace-tree-content">
            {treeLoading && !runTree ? (
              <div className="trace-tree-loading">Loading trace tree...</div>
            ) : treeError ? (
              <div className="trace-tree-error">
                <p>Error: {treeError.message}</p>
                <button onClick={refetchTree}>Retry</button>
              </div>
            ) : (!runTree || !runTree.root) ? (
              <div className="trace-tree-empty">
                <p>Select a run to view the trace tree</p>
              </div>
            ) : (
              <TraceTree 
                node={runTree.root} 
                onSelectNode={handleNodeSelect}
                selectedNodeId={selectedNodeId}
              />
            )}
          </div>
        </section>
        
        <aside className="details-panel">
          <DetailsPanel 
            tree={runTree?.root || null}
            nodeId={selectedNodeId}
          />
        </aside>
      </main>
    </div>
  );
}

export default App;