import { Drawer } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useState } from 'react';
import { get } from '../services/api';
import type { ExchangeRateRecord } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
  pair: string;
}

export default function ExchangeRateDrawer({ open, onClose, pair }: Props) {
  const [data, setData] = useState<ExchangeRateRecord[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !pair) return;
    setLoading(true);
    get<ExchangeRateRecord[]>('/market-data/exchange-rate/history', { pair }).then((r) => {
      if (r.success) setData(r.data);
      setLoading(false);
    });
  }, [open, pair]);

  const latest = data.length > 0 ? data[data.length - 1].rate : 0;
  const high = data.length > 0 ? Math.max(...data.map((d) => d.rate)) : 0;
  const low = data.length > 0 ? Math.min(...data.map((d) => d.rate)) : 0;

  const option = data.length > 0 ? {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#E5E7EB',
      textStyle: { color: '#1F2937', fontSize: 12 },
      formatter: (params: Array<{ axisValue: string; data: number }>) => {
        const p = params[0];
        return `${p.axisValue}<br/>${pair}: <b>${p.data.toFixed(4)}</b>`;
      },
    },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '5%', containLabel: true },
    dataZoom: [
      {
        type: 'slider', start: 80, end: 100, bottom: 8,
        borderColor: '#E5E7EB', backgroundColor: '#F9FAFB',
        fillerColor: 'rgba(217,70,239,0.08)',
        handleStyle: { color: '#D946EF', borderColor: '#D946EF' },
        textStyle: { color: '#6B7280' },
      },
      { type: 'inside' },
    ],
    xAxis: {
      type: 'category', data: data.map((d) => d.date), boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#9CA3AF', fontSize: 11 },
    },
    yAxis: {
      type: 'value', scale: true, axisLine: { show: false },
      axisLabel: { color: '#9CA3AF', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F3F4F6' } },
    },
    series: [{
      type: 'line', data: data.map((d) => d.rate), showSymbol: false,
      lineStyle: { width: 2, color: '#D946EF' },
      itemStyle: { color: '#D946EF' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(217,70,239,0.12)' },
            { offset: 1, color: 'rgba(217,70,239,0)' },
          ],
        },
      },
    }],
  } : null;

  return (
    <Drawer
      title={`${pair} 汇率走势`}
      open={open}
      onClose={onClose}
      width={680}
    >
      {/* Stats */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 20 }}>
        {[
          { label: '最新', value: latest.toFixed(4), color: '#1F2937' },
          { label: '最高', value: high.toFixed(4), color: '#EF4444' },
          { label: '最低', value: low.toFixed(4), color: '#22C55E' },
          { label: '数据量', value: `${data.length} 条`, color: '#6B7280' },
        ].map((s) => (
          <div key={s.label}>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFeatureSettings: "'tnum'" }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Chart */}
      {loading ? (
        <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>加载中...</div>
      ) : option ? (
        <ReactECharts option={option} style={{ height: 400 }} />
      ) : (
        <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无数据</div>
      )}
    </Drawer>
  );
}
