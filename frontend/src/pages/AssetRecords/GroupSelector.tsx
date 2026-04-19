import { Tag } from 'antd';
import type { GroupDimension } from '../../types';

interface GroupSelectorProps {
  dimensions: GroupDimension[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export default function GroupSelector({ dimensions, selected, onChange }: GroupSelectorProps) {
  const handleToggle = (key: string, checked: boolean) => {
    const next = checked
      ? [...selected, key]
      : selected.filter((k) => k !== key);
    onChange(next);
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginBottom: 12,
      padding: '6px 12px',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      background: 'var(--bg-group)',
    }}>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>分组:</span>
      {dimensions.map((dim) => (
        <Tag.CheckableTag
          key={dim.key}
          checked={selected.includes(dim.key)}
          onChange={(checked) => handleToggle(dim.key, checked)}
        >
          {dim.label}
        </Tag.CheckableTag>
      ))}
      {dimensions.length === 0 && (
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>暂无可用维度</span>
      )}
    </div>
  );
}
