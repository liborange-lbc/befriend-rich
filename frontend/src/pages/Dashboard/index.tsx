import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';
import { List, Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import HeatmapChart from '../../components/Charts/HeatmapChart';
import PriceChart from '../../components/Charts/PriceChart';
import ExchangeRateDrawer from '../../components/ExchangeRateDrawer';
import { get } from '../../services/api';
import type { AlertLogItem, DashboardOverview, DeviationSummary, FundDailyPrice, FundQuote } from '../../types';

export default function Dashboard() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [quotes, setQuotes] = useState<FundQuote[]>([]);
  const [deviation, setDeviation] = useState<DeviationSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertLogItem[]>([]);
  const [selectedFundId, setSelectedFundId] = useState<number | null>(null);
  const [priceData, setPriceData] = useState<FundDailyPrice[]>([]);
  const [ratePair, setRatePair] = useState<string>('');

  useEffect(() => {
    get<DashboardOverview>('/dashboard/overview').then((r) => r.success && setOverview(r.data));
    get<FundQuote[]>('/dashboard/fund-quotes').then((r) => r.success && setQuotes(r.data));
    get<DeviationSummary[]>('/analysis/deviation-summary').then((r) => r.success && setDeviation(r.data));
    get<AlertLogItem[]>('/dashboard/alerts/recent').then((r) => r.success && setAlerts(r.data));
  }, []);

  useEffect(() => {
    if (selectedFundId) get<FundDailyPrice[]>(`/analysis/prices/${selectedFundId}`).then((r) => r.success && setPriceData(r.data));
  }, [selectedFundId]);

  const quoteColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '净值', dataIndex: 'close_price', key: 'close_price', width: 100, render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>{v?.toFixed(4)}</span> },
    { title: '涨跌', dataIndex: 'change_pct', key: 'change_pct', width: 100,
      render: (v: number) => <span style={{ color: v >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500, fontFeatureSettings: "'tnum'" }}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}%</span> },
  ];

  const rateStyle: React.CSSProperties = {
    cursor: 'pointer',
    transition: 'color 0.15s',
    borderBottom: '1px dashed #D1D5DB',
    paddingBottom: 1,
  };

  return (
    <div>
      <h1 style={{ marginBottom: 20 }}>大盘看板</h1>

      <div className="stat-cards" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-card-label">总资产 (CNY)</div>
          <div className="stat-card-value">¥{(overview?.total_amount_cny || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">较上期变化</div>
          <div className="stat-card-value" style={{ color: overview && overview.change_amount >= 0 ? '#EF4444' : '#22C55E' }}>
            {overview && overview.change_amount >= 0 ? <ArrowUpOutlined style={{ fontSize: 16, marginRight: 4 }} /> : <ArrowDownOutlined style={{ fontSize: 16, marginRight: 4 }} />}
            ¥{Math.abs(overview?.change_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">变化幅度</div>
          <div className="stat-card-value" style={{ color: overview && overview.change_pct >= 0 ? '#EF4444' : '#22C55E' }}>
            {overview?.change_pct !== undefined && overview.change_pct >= 0 ? '+' : ''}{(overview?.change_pct || 0).toFixed(2)}%
          </div>
        </div>
        {/* 汇率卡片：USD/CNY + HKD/CNY */}
        <div className="stat-card">
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div className="stat-card-label">USD/CNY</div>
              <div
                className="stat-card-value"
                style={rateStyle}
                onClick={() => setRatePair('USD/CNY')}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#D946EF'; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.color = ''; }}
              >
                {(overview?.usd_cny_rate || 7.25).toFixed(4)}
              </div>
            </div>
            <div style={{ width: 1, background: '#E5E7EB' }} />
            <div style={{ flex: 1 }}>
              <div className="stat-card-label">HKD/CNY</div>
              <div
                className="stat-card-value"
                style={rateStyle}
                onClick={() => setRatePair('HKD/CNY')}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#D946EF'; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.color = ''; }}
              >
                {(overview?.hkd_cny_rate || 0.93).toFixed(4)}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 16, marginBottom: 16 }}>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">基金行情</span></div>
          <div style={{ padding: 0 }}>
            <Table dataSource={quotes} columns={quoteColumns} rowKey="fund_id" size="small" pagination={false} scroll={{ y: 340 }}
              onRow={(record) => ({ onClick: () => setSelectedFundId(record.fund_id),
                style: { cursor: 'pointer', background: selectedFundId === record.fund_id ? '#FDF4FF' : undefined } })} />
          </div>
        </div>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">K线图</span></div>
          <div className="section-card-body">
            {selectedFundId ? <PriceChart data={priceData} title="" /> :
              <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>点击左侧基金查看走势</div>}
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">均值偏差热力图</span></div>
        <div className="section-card-body"><HeatmapChart data={deviation} /></div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">策略提醒</span></div>
        <div className="section-card-body">
          <List dataSource={alerts} locale={{ emptyText: '暂无策略提醒' }}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={<span><Tag color="purple" style={{ fontSize: 11 }}>{item.triggered_at?.slice(0, 16)}</Tag>{item.fund_name}</span>}
                  description={<span style={{ color: '#6B7280' }}>{item.condition_desc}</span>} />
              </List.Item>)} />
        </div>
      </div>

      <ExchangeRateDrawer open={!!ratePair} onClose={() => setRatePair('')} pair={ratePair} />
    </div>
  );
}
