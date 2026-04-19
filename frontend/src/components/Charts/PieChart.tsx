import ReactECharts from 'echarts-for-react';
import { useCallback, useRef, useState } from 'react';

interface Props { title: string; data: { name: string; value: number }[]; onSectorClick?: (name: string) => void; }

const COLORS = ['#D946EF', '#3B82F6', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316', '#6366F1'];

function buildOption(title: string, data: { name: string; value: number }[], expanded: boolean, onSectorClick?: (name: string) => void) {
  return {
    title: { text: title, left: 'center', top: 4, textStyle: { color: '#1F2937', fontSize: 13, fontWeight: 600 } },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      textStyle: { color: '#1F2937', fontSize: 12 },
      confine: true,
    },
    legend: {
      orient: 'horizontal' as const,
      bottom: 0,
      left: 'center',
      textStyle: { color: '#6B7280', fontSize: 11 },
      inactiveColor: '#D1D5DB',
      itemWidth: 10,
      itemHeight: 10,
    },
    color: COLORS,
    grid: { containLabel: true },
    series: [{
      type: 'pie',
      radius: expanded ? ['35%', '62%'] : ['38%', '65%'],
      center: ['50%', expanded ? '45%' : '48%'],
      data,
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' }, scaleSize: 4 },
      label: {
        formatter: '{b}\n{d}%',
        color: '#6B7280',
        fontSize: expanded ? 12 : 11,
        overflow: 'none',
      },
      labelLine: { length: expanded ? 15 : 10, length2: expanded ? 12 : 8, lineStyle: { color: '#D1D5DB' } },
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 3, cursor: onSectorClick ? 'pointer' : 'default' },
    }],
  };
}

export default function PieChart({ title, data, onSectorClick }: Props) {
  const [hovered, setHovered] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleEnter = useCallback(() => {
    if (containerRef.current) {
      setRect(containerRef.current.getBoundingClientRect());
    }
    setHovered(true);
  }, []);

  const handleLeave = useCallback(() => {
    setHovered(false);
  }, []);

  if (!data.length) return <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无数据</div>;

  const normalOption = buildOption(title, data, false, onSectorClick);
  const expandedOption = buildOption(title, data, true, onSectorClick);

  const onEvents = onSectorClick
    ? { click: (params: { name: string }) => onSectorClick(params.name) }
    : undefined;

  const EXPAND_X = 80;
  const EXPAND_Y = 60;

  return (
    <>
      <div ref={containerRef} style={{ height: 300, position: 'relative' }} onMouseEnter={handleEnter}>
        {!hovered && <ReactECharts option={normalOption} style={{ height: 300 }} onEvents={onEvents} />}
      </div>

      {hovered && rect && (
        <div
          onMouseLeave={handleLeave}
          style={{
            position: 'fixed',
            left: Math.max(8, rect.left - EXPAND_X),
            top: Math.max(8, rect.top - EXPAND_Y),
            width: rect.width + EXPAND_X * 2,
            height: rect.height + EXPAND_Y * 2,
            zIndex: 1000,
            backgroundColor: '#FFFFFF',
            borderRadius: 12,
            boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
          }}
        >
          <ReactECharts
            option={expandedOption}
            style={{ width: '100%', height: '100%' }}
            onEvents={onEvents}
          />
        </div>
      )}
    </>
  );
}
