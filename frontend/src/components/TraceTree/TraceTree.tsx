import { useState } from 'react';
import { TraceNode } from '../../types';
import './TraceTree.css';

interface TraceTreeProps {
  node: TraceNode | null;
  onSelectNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

interface TraceNodeComponentProps {
  node: TraceNode;
  depth: number;
  onSelectNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

const TraceNodeComponent: React.FC<TraceNodeComponentProps> = ({ 
  node, 
  depth,
  onSelectNode,
  selectedNodeId
}) => {
  const [expanded, setExpanded] = useState(true);
  
  const toggleExpanded = () => {
    setExpanded(!expanded);
  };

  const handleNodeClick = () => {
    if (onSelectNode) {
      onSelectNode(node.id);
    }
  };

  // Format duration for display
  const formatDuration = (ms: number | null): string => {
    if (ms === null) return '-';
    return `${ms.toFixed(1)}ms`;
  };

  // Get badge class based on span type
  const getBadgeClass = (spanType: string): string => {
    switch (spanType) {
      case 'agent_run': return 'agent-run';
      case 'step': return 'step';
      case 'tool_call': return 'tool-call';
      case 'llm_call': return 'llm-call';
      default: return 'unknown';
    }
  };

  const isSelected = selectedNodeId === node.id;

  return (
    <div className={`trace-node ${isSelected ? 'selected' : ''}`}>
      <div className="node-row" onClick={handleNodeClick}>
        <div className="tree-toggle">
          {node.children.length > 0 ? (
            <button 
              className="toggle-button"
              onClick={(e) => {
                e.stopPropagation();
                toggleExpanded();
              }}
              aria-label={expanded ? 'Collapse' : 'Expand'}
            >
              {expanded ? '−' : '+'}
            </button>
          ) : (
            <button className="toggle-button placeholder" aria-disabled="true">
              ·
            </button>
          )}
        </div>
        
        <div className="node-content" style={{ marginLeft: `${depth * 20}px` }}>
          <span 
            className={`node-type-badge ${getBadgeClass(node.span_type)}`}
          >
            {node.span_type.replace(/_/g, ' ').toUpperCase()}
          </span>
          <div>
            <div className="node-name" title={node.name}>
              {node.name}
            </div>
            <div className="node-duration">
              {formatDuration(node.duration_ms)}
            </div>
          </div>
        </div>
      </div>
      
      {node.events.length > 0 && (
        <div className="node-events">
          <h4>Events ({node.events.length})</h4>
          <ul className="event-list">
            {node.events.map((event) => (
              <li key={event.id} className="event-item">
                <strong>{event.event_type}</strong>
                <span className="event-time">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <div className="event-payload">
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {node.children.length > 0 && expanded && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TraceNodeComponent 
              key={child.id} 
              node={child} 
              depth={depth + 1} 
              onSelectNode={onSelectNode}
              selectedNodeId={selectedNodeId}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const TraceTree: React.FC<TraceTreeProps> = ({ node, onSelectNode, selectedNodeId }) => {
  return (
    <div className="trace-tree-container">
      <div className="trace-tree-header">
        <h2>Trace Tree</h2>
      </div>
      <div className="trace-tree-content">
        {node ? (
          <div className="tree-root">
            <TraceNodeComponent 
              node={node} 
              depth={0} 
              onSelectNode={onSelectNode}
              selectedNodeId={selectedNodeId}
            />
          </div>
        ) : (
          <div className="tree-empty">
            <p>No trace data available</p>
          </div>
        )}
      </div>
    </div>
  );
};