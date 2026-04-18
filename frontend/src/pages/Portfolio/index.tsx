import { ArrowDownOutlined, ArrowUpOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Col, InputNumber, Modal, Row, Table } from 'antd';
import { useEffect, useState } from 'react';
import PieChart from '../../components/Charts/PieChart';
import TrendChart from '../../components/Charts/TrendChart';
import { get, post } from '../../services/api';
import type { Fund, PortfolioRecord, PortfolioSnapshot } from '../../types';

export default function Portfolio() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [latestRecords, setLatestRecords] = useState<PortfolioRecord[]>([]);
  const [top5, setTop5] = useState<{ rank: number; fund_name: string; amount_cny: number; percentage: number; profit: number }[]>([]);
  const [latestDate, setLatestDate] = useState<string>('');
  const [modalVisible, setModalVisible] = useState(false);
  const [editRecords, setEditRecords] = useState<{ fund_id: number; amount: number; profit: number }[]>([]);

  const loadData = () => {
    get<Fund[]>('/funds', { page_size: 100 }).then((r) => r.success && setFunds(r.data));
    get<PortfolioSnapshot[]>('/portfolio/snapshots').then((r) => r.success && setSnapshots(r.data));
    get<PortfolioRecord[]>('/portfolio/records/latest').then((r) => {
      if (r.success) { setLatestRecords(r.data); setLatestDate((r.meta as { latest_date?: string })?.latest_date || ''); }
    });
    get<typeof top5>('/portfolio/top5').then((r) => r.success && setTop5(r.data));
  };
  useEffect(loadData, []);

  const latestSnapshot = snapshots[snapshots.length - 1];
  const prevSnapshot = snapshots[snapshots.length - 2];
  const totalCny = latestSnapshot?.total_amount_cny || 0;
  const prevTotal = prevSnapshot?.total_amount_cny || 0;
  const change = totalCny - prevTotal;
  const changePct = prevTotal > 0 ? (change / prevTotal) * 100 : 0;

  const parseBreakdown = (s: PortfolioSnapshot | undefined) => { if (!s) return {}; try { return JSON.parse(s.model_breakdown); } catch { return {}; } };
  const breakdown = parseBreakdown(latestSnapshot);
  const pieCharts = Object.entries(breakdown).map(([modelName, categories]) => ({
    title: modelName, data: Object.entries(categories as Record<string, number>).map(([name, value]) => ({ name, value: Math.round(value) })),
  }));

  const trendData = snapshots.map((s) => {
    const bd = parseBreakdown(s);
    const row: { date: string; [key: string]: string | number } = { date: s.snapshot_date, total: s.total_amount_cny };
    Object.entries(bd).forEach(([, cats]) => { Object.entries(cats as Record<string, number>).forEach(([cat, val]) => { row[cat] = val; }); });
    return row;
  });
  const allCategories = [...new Set(trendData.flatMap((d) => Object.keys(d).filter((k) => k !== 'date' && k !== 'total')))];

  const openModal = () => {
    const records = latestRecords.length > 0
      ? latestRecords.map((r) => ({ fund_id: r.fund_id, amount: r.amount, profit: r.profit || 0 }))
      : funds.filter((f) => f.is_active).map((f) => ({ fund_id: f.id, amount: 0, profit: 0 }));
    setEditRecords(records); setModalVisible(true);
  };

  const handleSubmit = async () => {
    const today = new Date().toISOString().split('T')[0];
    await post('/portfolio/records/batch', { records: editRecords.filter((r) => r.amount > 0).map((r) => ({ fund_id: r.fund_id, record_date: today, amount: r.amount, profit: r.profit })) });
    setModalVisible(false); loadData();
  };

  const top5Columns = [
    { title: '排名', dataIndex: 'rank', key: 'rank', width: 60,
      render: (v: number) => <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 22, height: 22, borderRadius: '50%',
        background: v <= 3 ? '#FDF4FF' : '#F3F4F6', color: v <= 3 ? '#D946EF' : '#9CA3AF', fontSize: 12, fontWeight: 600 }}>{v}</span> },
    { title: '基金', dataIndex: 'fund_name', key: 'fund_name' },
    { title: '金额 (CNY)', dataIndex: 'amount_cny', key: 'amount_cny', render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{v?.toLocaleString()}</span> },
    { title: '占比', dataIndex: 'percentage', key: 'percentage',
      render: (v: number) => (<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, maxWidth: 80, height: 4, borderRadius: 2, background: '#F3F4F6' }}><div style={{ width: `${Math.min(v, 100)}%`, height: '100%', borderRadius: 2, background: '#D946EF' }} /></div>
        <span style={{ fontSize: 12, color: '#6B7280' }}>{v}%</span></div>) },
    { title: '收益', dataIndex: 'profit', key: 'profit',
      render: (v: number) => v ? <span style={{ color: v >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>¥{v?.toLocaleString()}</span> : <span style={{ color: '#D1D5DB' }}>-</span> },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1>资产总览</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>录入本周数据</Button>
      </div>

      <div className="stat-cards" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-card-label">总资产 (CNY)</div>
          <div className="stat-card-value">¥{totalCny.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>最近录入: {latestDate || '无'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">较上期变化</div>
          <div className="stat-card-value" style={{ color: change >= 0 ? '#EF4444' : '#22C55E' }}>
            {change >= 0 ? <ArrowUpOutlined style={{ fontSize: 16, marginRight: 4 }} /> : <ArrowDownOutlined style={{ fontSize: 16, marginRight: 4 }} />}
            ¥{Math.abs(change).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className={`stat-card-change ${change >= 0 ? 'up' : 'down'}`}>{changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%</div>
        </div>
        <div className="stat-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 8 }}>快速操作</div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>录入本周数据</Button>
        </div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">模型配比</span></div>
        <div className="section-card-body">
          <Row gutter={16}>
            {pieCharts.map((c) => <Col span={8} key={c.title}><PieChart title={c.title} data={c.data} /></Col>)}
            {pieCharts.length === 0 && <Col span={24}><div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>请先配置分类模型和映射</div></Col>}
          </Row>
        </div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">资产趋势</span></div>
        <div className="section-card-body">
          <TrendChart title="总资产趋势" data={trendData} seriesKeys={['total']} />
          {allCategories.length > 0 && <div style={{ marginTop: 16 }}><TrendChart title="分类趋势" data={trendData} seriesKeys={allCategories} /></div>}
        </div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">持仓 TOP 5</span></div>
        <div className="section-card-body" style={{ padding: 0 }}><Table dataSource={top5} columns={top5Columns} rowKey="rank" pagination={false} size="small" /></div>
      </div>

      <Modal title="录入本周持仓" open={modalVisible} onOk={handleSubmit} onCancel={() => setModalVisible(false)} width={600}>
        {editRecords.map((record, idx) => {
          const fund = funds.find((f) => f.id === record.fund_id);
          return (<Row key={record.fund_id} gutter={8} style={{ marginBottom: 8, alignItems: 'center' }}>
            <Col span={8}><span style={{ fontSize: 13 }}>{fund?.name || `基金 ${record.fund_id}`}</span></Col>
            <Col span={8}><InputNumber style={{ width: '100%' }} placeholder="金额" value={record.amount} onChange={(v) => { const n = [...editRecords]; n[idx] = { ...record, amount: v || 0 }; setEditRecords(n); }} /></Col>
            <Col span={8}><InputNumber style={{ width: '100%' }} placeholder="收益" value={record.profit} onChange={(v) => { const n = [...editRecords]; n[idx] = { ...record, profit: v || 0 }; setEditRecords(n); }} /></Col>
          </Row>);
        })}
      </Modal>
    </div>
  );
}
