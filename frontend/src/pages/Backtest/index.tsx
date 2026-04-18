import { Button, Col, DatePicker, Form, Row, Select, Table } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useState } from 'react';
import { get, post } from '../../services/api';
import type { BacktestResult, Fund, Strategy } from '../../types';

export default function Backtest() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    get<Fund[]>('/funds', { page_size: 100, is_active: true }).then((r) => r.success && setFunds(r.data));
    get<Strategy[]>('/strategy').then((r) => r.success && setStrategies(r.data));
  }, []);

  const handleRun = async (values: { strategy_id: number; fund_id: number; dates: [unknown, unknown] }) => {
    setLoading(true);
    try {
      const [start, end] = values.dates as [{ format: (f: string) => string }, { format: (f: string) => string }];
      const resp = await post<BacktestResult>('/backtest/run', { strategy_id: values.strategy_id, fund_id: values.fund_id, start_date: start.format('YYYY-MM-DD'), end_date: end.format('YYYY-MM-DD') });
      if (resp.success) setResult(resp.data);
    } finally { setLoading(false); }
  };

  const equityCurve = result ? JSON.parse(result.equity_curve) as { date: string; value: number }[] : [];
  const tradeLog = result ? JSON.parse(result.trade_log) as Record<string, unknown>[] : [];

  const chartOption = equityCurve.length > 0 ? {
    title: { text: '净值曲线', left: 'center', textStyle: { color: '#1F2937', fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: '#1F2937', fontSize: 12 } },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    dataZoom: [{ type: 'slider', start: 0, end: 100, borderColor: '#E5E7EB', backgroundColor: '#F9FAFB',
      fillerColor: 'rgba(217,70,239,0.08)', handleStyle: { color: '#D946EF', borderColor: '#D946EF' }, textStyle: { color: '#6B7280' } }],
    xAxis: { type: 'category', data: equityCurve.map((e) => e.date), axisLine: { lineStyle: { color: '#E5E7EB' } }, axisLabel: { color: '#9CA3AF', fontSize: 11 } },
    yAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#9CA3AF', fontSize: 11 }, splitLine: { lineStyle: { color: '#F3F4F6' } } },
    series: [{ type: 'line', data: equityCurve.map((e) => e.value), showSymbol: false, lineStyle: { width: 2, color: '#D946EF' }, itemStyle: { color: '#D946EF' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(217,70,239,0.12)' }, { offset: 1, color: 'rgba(217,70,239,0)' }] } } }],
  } : null;

  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '操作', dataIndex: 'action', key: 'action', render: (v: string) => <span style={{ color: v === 'buy' ? '#EF4444' : '#22C55E', fontWeight: 500 }}>{v === 'buy' ? '买入' : '卖出'}</span> },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>{v}</span> },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{v?.toLocaleString()}</span> },
    { title: '份额', dataIndex: 'shares', key: 'shares', render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>{v}</span> },
  ];

  return (
    <div>
      <h1 style={{ marginBottom: 20 }}>回测</h1>
      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">回测配置</span></div>
        <div className="section-card-body">
          <Form form={form} layout="inline" onFinish={handleRun}>
            <Form.Item name="strategy_id" label="策略" rules={[{ required: true }]}><Select style={{ width: 200 }} options={strategies.map((s) => ({ label: s.name, value: s.id }))} /></Form.Item>
            <Form.Item name="fund_id" label="基金" rules={[{ required: true }]}><Select style={{ width: 200 }} options={funds.map((f) => ({ label: f.name, value: f.id }))} /></Form.Item>
            <Form.Item name="dates" label="时间范围" rules={[{ required: true }]}><DatePicker.RangePicker /></Form.Item>
            <Form.Item><Button type="primary" htmlType="submit" loading={loading}>运行回测</Button></Form.Item>
          </Form>
        </div>
      </div>
      {result && (<>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">回测指标</span></div>
          <div className="section-card-body">
            <Row gutter={12}>
              {[
                { label: '总收益率', value: ((result.total_return || 0) * 100).toFixed(2) + '%', color: (result.total_return || 0) >= 0 ? '#EF4444' : '#22C55E' },
                { label: '年化收益率', value: ((result.annual_return || 0) * 100).toFixed(2) + '%', color: (result.annual_return || 0) >= 0 ? '#EF4444' : '#22C55E' },
                { label: '夏普比率', value: (result.sharpe_ratio || 0).toFixed(4), color: '#1F2937' },
                { label: '最大回撤', value: ((result.max_drawdown || 0) * 100).toFixed(2) + '%', color: '#22C55E' },
                { label: '波动率', value: ((result.volatility || 0) * 100).toFixed(2) + '%', color: '#1F2937' },
                { label: '胜率', value: ((result.win_rate || 0) * 100).toFixed(2) + '%', color: '#D946EF' },
              ].map((m) => (
                <Col span={4} key={m.label}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '14px 8px', background: '#F9FAFB', borderRadius: 6, border: '1px solid #E5E7EB' }}>
                    <span style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4, fontWeight: 500 }}>{m.label}</span>
                    <span style={{ fontSize: 18, fontWeight: 700, color: m.color, fontFeatureSettings: "'tnum'" }}>{m.value}</span>
                  </div>
                </Col>))}
            </Row>
          </div>
        </div>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">净值曲线</span></div>
          <div className="section-card-body">{chartOption && <ReactECharts option={chartOption} style={{ height: 400 }} />}</div>
        </div>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">交易明细</span></div>
          <div style={{ padding: 0 }}><Table dataSource={tradeLog} columns={tradeColumns} rowKey={(_, i) => String(i)} size="small" pagination={{ pageSize: 20 }} /></div>
        </div>
      </>)}
    </div>
  );
}
