import ReactECharts from 'echarts-for-react';
import type { FundDailyPrice } from '../../types';

interface Props { data: FundDailyPrice[]; title?: string; }

const TIP = { backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: '#1F2937', fontSize: 12 } };

export default function PriceChart({ data, title = '价格走势' }: Props) {
  if (!data.length) return <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无数据</div>;

  const option = {
    title: title ? { text: title, left: 'center', textStyle: { color: '#1F2937', fontSize: 14, fontWeight: 600 } } : undefined,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross', crossStyle: { color: '#9CA3AF' } }, ...TIP },
    legend: { data: ['收盘价', 'MA30', 'MA60', 'MA120'], bottom: 0, textStyle: { color: '#6B7280', fontSize: 11 }, inactiveColor: '#D1D5DB' },
    grid: { left: '3%', right: '4%', bottom: '15%', top: title ? '12%' : '5%', containLabel: true },
    dataZoom: [
      { type: 'slider', start: 70, end: 100, bottom: 26, borderColor: '#E5E7EB', backgroundColor: '#F9FAFB',
        fillerColor: 'rgba(217,70,239,0.08)', handleStyle: { color: '#D946EF', borderColor: '#D946EF' }, textStyle: { color: '#6B7280' },
        dataBackground: { lineStyle: { color: '#E5E7EB' }, areaStyle: { color: '#F3F4F6' } } },
      { type: 'inside' },
    ],
    xAxis: { type: 'category', data: data.map((d) => d.date), boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 11 } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false },
      axisLabel: { color: '#9CA3AF', fontSize: 11 }, splitLine: { lineStyle: { color: '#F3F4F6' } } },
    series: [
      { name: '收盘价', type: 'line', data: data.map((d) => d.close_price), lineStyle: { width: 2, color: '#D946EF' }, itemStyle: { color: '#D946EF' }, showSymbol: false,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(217,70,239,0.12)' }, { offset: 1, color: 'rgba(217,70,239,0)' }] } } },
      { name: 'MA30', type: 'line', data: data.map((d) => d.ma_30), lineStyle: { width: 1, color: '#3B82F6' }, itemStyle: { color: '#3B82F6' }, showSymbol: false },
      { name: 'MA60', type: 'line', data: data.map((d) => d.ma_60), lineStyle: { width: 1, color: '#F59E0B' }, itemStyle: { color: '#F59E0B' }, showSymbol: false },
      { name: 'MA120', type: 'line', data: data.map((d) => d.ma_120), lineStyle: { width: 1, color: '#10B981' }, itemStyle: { color: '#10B981' }, showSymbol: false },
    ],
  };
  return <ReactECharts option={option} style={{ height: 400 }} />;
}
