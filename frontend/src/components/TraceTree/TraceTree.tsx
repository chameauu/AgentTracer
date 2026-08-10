import { TraceNode as TraceNodeType } from '../../types';
import { TraceNode } from './TraceNode';
import './TraceTree.css';

interface TraceTreeProps {
  node: TraceNodeType | null;
  onSelectNode?: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

export const TraceTree: React.FC<TraceTreeProps> = ({ node, onSelectNode, selectedNodeId }) => {
  return (
    <div className="trace-tree-container">
      <div className="trace-tree-content">
        {node ? (
          <div className="tree-root">
            <TraceNode
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
