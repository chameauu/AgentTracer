import { useState, useEffect } from 'react';
import { TraceNode } from '../../types';
import './DetailsPanel.css';

interface DetailsPanelProps {
  tree: TraceNode | null;
  nodeId: string | null;
}

const findNodeById = (node: TraceNode | null, targetId: string): TraceNode | null => {
  if (!node) return null;
  if (node.id === targetId) return node;

  for (const child of node.children) {
    const found = findNodeById(child, targetId);
    if (found) return found;
  }

  return null;
};

export const DetailsPanel: React.FC<DetailsPanelProps> = ({ 
  tree, 
  nodeId 
}) => {
  const [selectedNode, setSelectedNode] = useState<TraceNode | null>(null);

  // Update selected node when nodeId or tree changes
  useEffect(() => {
    if (tree && nodeId) {
      setSelectedNode(findNodeById(tree, nodeId));
    } else {
      setSelectedNode(null);
    }
  }, [tree, nodeId]);

  if (!selectedNode) {
    return (
      <div className="details-panel">
        <div className="details-header">
          <h2>Node Details</h2>
          <p className="placeholder">Select a node from the trace tree to view details</p>
        </div>
      </div>
    );
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (ms: number | null): string => {
    if (ms === null) return '-';
    return `${ms.toFixed(1)}ms`;
  };

  const getBadgeClass = (spanType: string): string => {
    switch (spanType) {
      case 'agent_run': return 'agent-run';
      case 'step': return 'step';
      case 'tool_call': return 'tool-call';
      case 'llm_call': return 'llm-call';
      default: return 'unknown';
    }
  };

  return (
    <div className="details-panel">
      <div className="details-header">
        <h2>Node Details</h2>
      </div>
      <div className="details-content">
        <div className="details-section">
          <h3>Overview</h3>
          <div className="details-grid">
            <div>
              <span className="label">Name:</span>
              <span className="value">{selectedNode.name}</span>
            </div>
            <div>
              <span className="label">Type:</span>
              <span 
                className={`value badge ${getBadgeClass(selectedNode.span_type)}`}
              >
                {selectedNode.span_type.replace(/_/g, ' ').toUpperCase()}
              </span>
            </div>
            <div>
              <span className="label">Started:</span>
              <span className="value">{formatDate(selectedNode.started_at)}</span>
            </div>
            <div>
              <span className="label">Ended:</span>
              <span className="value">
                {selectedNode.ended_at ? formatDate(selectedNode.ended_at) : 'Running'}
              </span>
            </div>
            <div>
              <span className="label">Duration:</span>
              <span className="value">{formatDuration(selectedNode.duration_ms)}</span>
            </div>
          </div>
        </div>

        {Object.keys(selectedNode.attributes).length > 0 && (
          <div className="details-section">
            <h3>Attributes</h3>
            <div className="attributes-json">
              <pre>{JSON.stringify(selectedNode.attributes, null, 2)}</pre>
            </div>
          </div>
        )}

        {selectedNode.events.length > 0 && (
          <div className="details-section">
            <h3>Events ({selectedNode.events.length})</h3>
            <div className="events-list">
              {selectedNode.events.map((event) => (
                <div key={event.id} className="event-item">
                  <div className="event-header">
                    <span className="event-type">{event.event_type}</span>
                    <span className="event-time">{formatDate(event.timestamp)}</span>
                  </div>
                  <div className="event-payload">
                    <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};