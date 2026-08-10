import { useState } from 'react';
import './JsonView.css';

interface JsonViewProps {
  data: unknown;
  maxHeight?: number;
}

const COLLAPSE_THRESHOLD = 600;

export const JsonView: React.FC<JsonViewProps> = ({ data, maxHeight = 320 }) => {
  const [expanded, setExpanded] = useState(false);
  const json = JSON.stringify(data, null, 2);
  const collapsible = json.length > COLLAPSE_THRESHOLD;
  const visible = collapsible && !expanded ? `${json.slice(0, COLLAPSE_THRESHOLD)}…` : json;

  return (
    <div className="json-view">
      <pre className="json-view-body" style={{ maxHeight }}>
        {visible}
      </pre>
      {collapsible && (
        <button className="json-view-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show less' : `Show more (${json.length} chars)`}
        </button>
      )}
    </div>
  );
};
