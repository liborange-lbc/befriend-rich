import ReactECharts from 'echarts-for-react';

interface Props { title: string; data: { name: string; value: number }[]; }

const COLORS = ['#D946EF', '#3B82F6', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316', '#6366F1'];

export default function PieChart({ title, data }: Props) {
  if (!data.length) return <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无数据</div>;

  const option = {
    title: { text: title, left: 'center', textStyle: { color: '#1F2937', fontSize: 13, fontWeight: 600 } },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)', backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: '#1F2937', fontSize: 12 } },
    legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { color: '#6B7280', fontSize: 11 }, inactiveColor: '#D1D5DB' },
    color: COLORS,
    series: [{
      type: 'pie', radius: ['42%', '72%'], center: ['60%', '52%'], data,
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.1)' }, scaleSize: 4 },
      label: { formatter: '{b}\n{d}%', color: '#6B7280', fontSize: 11 },
      labelLine: { lineStyle: { color: '#D1D5DB' } },
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 3 },
    }],
  };
  return <ReactECharts option={option} style={{ height: 280 }} />;
}
