import { useState } from 'react';
import { TraceNode as TraceNodeType } from '../../types';
import { JsonView } from '../DetailsPanel/JsonView';

interface TraceNodeProps {
  node: TraceNodeType;
  depth: number;
  onSelectNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

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

export const TraceNode: React.FC<TraceNodeProps> = ({
  node,
  depth,
  onSelectNode,
  selectedNodeId,
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
                  <JsonView data={event.payload} maxHeight={200} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {node.children.length > 0 && expanded && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TraceNode
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
