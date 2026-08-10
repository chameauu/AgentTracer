import { Run } from '../../types';

interface RunListItemProps {
  run: Run;
  selected: boolean;
  onSelect: (runId: string) => void;
}

export const RunListItem: React.FC<RunListItemProps> = ({ run, selected, onSelect }) => {
  return (
    <tr className={selected ? 'selected' : ''} onClick={() => onSelect(run.id)}>
      <td>{run.name}</td>
      <td>
        <span className={`status-badge status-${run.status.toLowerCase()}`}>
          {run.status}
        </span>
      </td>
      <td>{new Date(run.started_at).toLocaleString()}</td>
      <td>
        {run.duration_ms !== null ? `${run.duration_ms.toFixed(1)} ms` : 'Running'}
      </td>
    </tr>
  );
};
