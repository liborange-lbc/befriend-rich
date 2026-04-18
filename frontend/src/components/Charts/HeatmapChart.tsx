import ReactECharts from 'echarts-for-react';
import type { DeviationSummary } from '../../types';

interface Props { data: DeviationSummary[]; }
const MA_KEYS = ['dev_30', 'dev_60', 'dev_90', 'dev_120', 'dev_180', 'dev_360'] as const;
const MA_LABELS = ['MA30', 'MA60', 'MA90', 'MA120', 'MA180', 'MA360'];

export default function HeatmapChart({ data }: Props) {
  if (!data.length) return <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无偏差数据</div>;

  const fundNames = data.map((d) => d.fund_name);
  const heatData: [number, number, number | null][] = [];
  data.forEach((fund, yIdx) => { MA_KEYS.forEach((key, xIdx) => { heatData.push([xIdx, yIdx, fund[key]]); }); });

  const option = {
    tooltip: { position: 'top', backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: '#1F2937', fontSize: 12 },
      formatter: (params: { data: [number, number, number | null] }) => { const [x, y, val] = params.data; return `${fundNames[y]} ${MA_LABELS[x]}: ${val !== null ? val?.toFixed(2) + '%' : 'N/A'}`; } },
    grid: { left: 120, top: 10, right: 20, bottom: 40 },
    xAxis: { type: 'category', data: MA_LABELS, splitArea: { show: true, areaStyle: { color: ['#FAFAFA', '#fff'] } },
      axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#6B7280', fontSize: 11 } },
    yAxis: { type: 'category', data: fundNames, splitArea: { show: true, areaStyle: { color: ['#FAFAFA', '#fff'] } },
      axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#6B7280', fontSize: 11 } },
    visualMap: { min: -20, max: 20, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: '#6B7280' },
      inRange: { color: ['#065f46', '#10b981', '#86efac', '#E5E7EB', '#fca5a5', '#ef4444', '#991b1b'] } },
    series: [{ type: 'heatmap', data: heatData,
      label: { show: true, color: '#1F2937', fontSize: 11, fontWeight: 500,
        formatter: (params: { data: [number, number, number | null] }) => { const val = params.data[2]; return val !== null ? `${val?.toFixed(1)}%` : ''; } },
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 2 } }],
  };
  return <ReactECharts option={option} style={{ height: Math.max(200, data.length * 44 + 80) }} />;
}
