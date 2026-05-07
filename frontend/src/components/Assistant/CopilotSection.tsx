import { SmileOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useCopilot } from './CopilotContext';

interface CopilotSectionProps {
  /** 模块名称，如 "总资产"、"模型配比" */
  sectionName: string;
  /** 当前模块展示的数据摘要 */
  contextData: unknown;
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}

export default function CopilotSection({
  sectionName,
  contextData,
  children,
  style,
  className,
}: CopilotSectionProps) {
  const [hovered, setHovered] = useState(false);
  const openCopilot = useCopilot();

  return (
    <div
      style={{ position: 'relative', ...style }}
      className={className}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {children}
      {hovered && (
        <div
          onClick={(e) => {
            e.stopPropagation();
            openCopilot(sectionName, contextData);
          }}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #D946EF, #A855F7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(217,70,239,0.35)',
            zIndex: 10,
            transition: 'transform 0.15s',
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1.15)'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)'; }}
          title={`向萌可提问：${sectionName}`}
        >
          <SmileOutlined style={{ color: '#fff', fontSize: 14 }} />
        </div>
      )}
    </div>
  );
}
