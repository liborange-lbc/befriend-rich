import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, Col, Row, Select, Spin, message } from 'antd';
import ReactECharts from 'echarts-for-react';
import type { MaTimingData, Fund } from '../../types';
import { get } from '../../services/api';

const statusColors: Record<string, string> = {
  green: '#52c41a',
  yellow: '#faad14',
  red: '#ff4d4f',
  gray: '#d9d9d9',
};

const rules = [
  { color: '#52c41a', label: '定投买入', condition: '收盘价 < 年线（250日均线）', desc: '价格低于年线，处于低估区间，适合定期买入' },
  { color: '#faad14', label: '持仓不动', condition: '收盘价 ≥ 年线', desc: '价格回到年线上方，停止定投，耐心持有' },
  { color: '#ff4d4f', label: '分批卖出', condition: '收盘价 ≥ 年线 × 1.10（涨超10%）', desc: '价格显著高于年线，逐步止盈' },
];

export default function MaTiming() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [fundId, setFundId] = useState<number | null>(null);
  const [data, setData] = useState<MaTimingData | null>(null);
  const [loading, setLoading] = useState(false);

  // Load fund list
  useEffect(() => {
    get<Fund[]>('/funds').then((res) => {
      if (res.success && res.data) {
        setFunds(res.data);
        // Default to 红利低波 if exists
        const target = res.data.find((f) => f.code === '005561');
        setFundId(target?.id ?? res.data[0]?.id ?? null);
      }
    });
  }, []);

  // Load MA timing data
  const loadData = useCallback(async (fid: number) => {
    setLoading(true);
    const res = await get<MaTimingData>(`/analysis/ma-timing/${fid}`);
    if (res.success && res.data) {
      setData(res.data);
    } else {
      message.error('加载均线择时数据失败');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (fundId) loadData(fundId);
  }, [fundId, loadData]);

  const latest = data?.latest;
  const devDisplay = latest?.dev_250 != null ? `${latest.dev_250 >= 0 ? '+' : ''}${latest.dev_250.toFixed(2)}%` : '--';

  // Chart option
  const chartOption = useMemo(() => {
    if (!data?.history.length) return {};

    const dates: string[] = [];
    const devData: (number | null)[] = [];
    const priceData: (number | null)[] = [];

    for (const h of data.history) {
      dates.push(h.date);
      devData.push(h.dev_250 != null ? Math.round(h.dev_250 * 100) / 100 : null);
      priceData.push(h.close_price);
    }

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#fff',
        borderColor: '#E5E7EB',
        textStyle: { color: '#1F2937', fontSize: 12 },
        formatter: (params: { axisValue: string; marker: string; seriesName: string; value: number | null }[]) => {
          const date = params[0]?.axisValue ?? '';
          let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`;
          for (const p of params) {
            if (p.value == null) continue;
            const val = p.seriesName === '年线偏离度' ? `${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%` : p.value.toFixed(4);
            html += `<div>${p.marker} ${p.seriesName}: <b>${val}</b></div>`;
          }
          return html;
        },
      },
      legend: {
        data: ['年线偏离度', '收盘价'],
        top: 6,
        textStyle: { fontSize: 12, color: '#6B7280' },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '12%',
        containLabel: true,
      },
      dataZoom: [
        { type: 'slider', start: 0, end: 100, bottom: 10, height: 24, borderColor: 'transparent', backgroundColor: '#F3F4F6', fillerColor: 'rgba(59,130,246,0.12)', handleStyle: { color: '#3B82F6' } },
        { type: 'inside' },
      ],
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { fontSize: 11, color: '#9CA3AF' },
        axisLine: { lineStyle: { color: '#E5E7EB' } },
      },
      yAxis: [
        {
          type: 'value',
          name: '偏离度 %',
          position: 'left',
          axisLabel: { fontSize: 11, color: '#9CA3AF', formatter: '{value}%' },
          splitLine: { lineStyle: { color: '#F3F4F6' } },
        },
        {
          type: 'value',
          name: '收盘价',
          position: 'right',
          axisLabel: { fontSize: 11, color: '#9CA3AF' },
          splitLine: { show: false },
        },
      ],
      visualMap: {
        show: false,
        seriesIndex: 0,
        pieces: [
          { lte: 0, color: '#52c41a' },
          { gt: 0, lt: 10, color: '#faad14' },
          { gte: 10, color: '#ff4d4f' },
        ],
      },
      series: [
        {
          name: '年线偏离度',
          type: 'line',
          yAxisIndex: 0,
          data: devData,
          symbol: 'none',
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.08 },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { type: 'dashed', width: 1 },
            data: [
              { yAxis: 0, label: { formatter: '0%', fontSize: 10, color: '#52c41a' }, lineStyle: { color: '#52c41a' } },
              { yAxis: 10, label: { formatter: '10%', fontSize: 10, color: '#ff4d4f' }, lineStyle: { color: '#ff4d4f' } },
            ],
          },
        },
        {
          name: '收盘价',
          type: 'line',
          yAxisIndex: 1,
          data: priceData,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#374151' },
          itemStyle: { color: '#374151' },
        },
      ],
    };
  }, [data]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>均线择时</h1>
        <Select
          value={fundId}
          onChange={setFundId}
          style={{ width: 320 }}
          showSearch
          optionFilterProp="label"
          options={funds.map((f) => ({ value: f.id, label: `${f.code} ${f.name}` }))}
        />
        {latest && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: '#6B7280' }}>{latest.date}</span>
            <span style={{
              fontSize: 22,
              fontWeight: 700,
              fontFeatureSettings: "'tnum'",
              color: statusColors[latest.color] ?? '#374151',
            }}>
              {devDisplay}
            </span>
            <span style={{
              padding: '3px 12px',
              borderRadius: 12,
              fontSize: 13,
              fontWeight: 600,
              color: '#fff',
              background: statusColors[latest.color] ?? '#d9d9d9',
            }}>
              {latest.status_label}
            </span>
          </div>
        )}
      </div>

      {/* Strategy Rules */}
      <Card style={{ marginBottom: 20 }} styles={{ body: { padding: '16px 24px' } }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary, #111827)' }}>
          策略规则 — 年线（250日均线）择时
        </div>
        <Row gutter={16}>
          {rules.map((r, i) => (
            <Col span={8} key={i}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8,
                  background: `${r.color}18`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, marginTop: 2,
                }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: r.color }}>R{i + 1}</span>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: r.color, marginBottom: 2 }}>{r.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary, #374151)', marginBottom: 2 }}>{r.condition}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary, #9CA3AF)' }}>{r.desc}</div>
                </div>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      {/* Chart */}
      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : data?.history.length ? (
        <Card styles={{ body: { padding: '12px 16px' } }}>
          <ReactECharts option={chartOption} style={{ height: 480 }} notMerge />
        </Card>
      ) : (
        <Card><div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>暂无数据</div></Card>
      )}
    </div>
  );
}
