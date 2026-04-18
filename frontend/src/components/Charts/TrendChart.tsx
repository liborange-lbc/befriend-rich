import ReactECharts from 'echarts-for-react';

interface TrendData { date: string; [key: string]: string | number; }
interface Props { title: string; data: TrendData[]; seriesKeys: string[]; }

const COLORS = ['#D946EF', '#3B82F6', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316', '#6366F1'];

export default function TrendChart({ title, data, seriesKeys }: Props) {
  if (!data.length) return <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无趋势数据</div>;

  const option = {
    title: { text: title, left: 'center', textStyle: { color: '#1F2937', fontSize: 13, fontWeight: 600 } },
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: '#1F2937', fontSize: 12 } },
    legend: { data: seriesKeys, bottom: 0, textStyle: { color: '#6B7280', fontSize: 11 }, inactiveColor: '#D1D5DB' },
    color: COLORS,
    grid: { left: '3%', right: '4%', bottom: '15%', top: '12%', containLabel: true },
    dataZoom: [
      { type: 'slider', start: 0, end: 100, bottom: 26, borderColor: '#E5E7EB', backgroundColor: '#F9FAFB',
        fillerColor: 'rgba(217,70,239,0.08)', handleStyle: { color: '#D946EF', borderColor: '#D946EF' }, textStyle: { color: '#6B7280' } },
      { type: 'inside' },
    ],
    xAxis: { type: 'category', data: data.map((d) => d.date), boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 11 } },
    yAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#9CA3AF', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F3F4F6' } } },
    series: seriesKeys.map((key, idx) => ({
      name: key, type: 'line', data: data.map((d) => d[key] || 0), showSymbol: false, lineStyle: { width: 2 },
      areaStyle: { opacity: 0.06, color: COLORS[idx % COLORS.length] },
    })),
  };
  return <ReactECharts option={option} style={{ height: 300 }} />;
}
