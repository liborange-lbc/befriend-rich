import { Table, Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

interface FundStats {
  fund_id: number;
  fund_code: string;
  fund_name: string;
  currency: string;
  annualized_return: number | null;
  max_drawdown: number | null;
  volatility: number | null;
  sharpe_ratio: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_12m: number | null;
  total_days: number;
}

interface NormalizedPoint {
  date: string;
  value: number;
}

interface RankingGroup {
  category_id: number;
  category_name: string;
  funds: FundStats[];
}

const pct = (v: number | null) => v !== null ? `${(v * 100).toFixed(2)}%` : '-';
const pctColor = (v: number | null) => {
  if (v === null) return undefined;
  return v >= 0 ? 'var(--success)' : 'var(--error)';
};

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#fc8452', '#9a60b4', '#ea7ccc'];

export default function FundCompare() {
  const [stats, setStats] = useState<FundStats[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [priceData, setPriceData] = useState<Record<string, NormalizedPoint[]>>({});
  const [ranking, setRanking] = useState<RankingGroup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      get<FundStats[]>('/fund-compare/stats'),
      get<RankingGroup[]>('/fund-compare/ranking'),
    ]).then(([s, r]) => {
      if (s.success) setStats(s.data);
      if (r.success) setRanking(r.data);
    }).catch(() => {
      // network error
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (selectedIds.length === 0) {
      setPriceData({});
      return;
    }
    get<Record<string, NormalizedPoint[]>>('/fund-compare/prices', { fund_ids: selectedIds.join(',') })
      .then((r) => r.success && setPriceData(r.data));
  }, [selectedIds]);

  const fundMap = useMemo(() => {
    const m: Record<number, FundStats> = {};
    stats.forEach((s) => { m[s.fund_id] = s; });
    return m;
  }, [stats]);

  const chartOption = useMemo(() => {
    const series = selectedIds.map((id, i) => {
      const points = priceData[String(id)] || [];
      const name = fundMap[id]?.fund_name || `Fund ${id}`;
      return {
        name,
        type: 'line',
        showSymbol: false,
        lineStyle: { width: 1.5 },
        color: COLORS[i % COLORS.length],
        data: points.map((p) => [p.date, p.value]),
      };
    });
    return {
      tooltip: { trigger: 'axis' as const },
      legend: { top: 0, textStyle: { fontSize: 11 } },
      grid: { top: 30, bottom: 30, left: 50, right: 20 },
      xAxis: { type: 'time' as const },
      yAxis: { type: 'value' as const, axisLabel: { formatter: (v: number) => v.toFixed(2) } },
      series,
    };
  }, [selectedIds, priceData, fundMap]);

  const statColumns = [
    { title: '代码', dataIndex: 'fund_code', width: 70, render: (v: string) => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v}</span> },
    { title: '名称', dataIndex: 'fund_name', width: 150, ellipsis: true },
    { title: '年化', dataIndex: 'annualized_return', width: 75, sorter: (a: FundStats, b: FundStats) => (a.annualized_return ?? -999) - (b.annualized_return ?? -999), render: (v: number | null) => <span style={{ color: pctColor(v) }}>{pct(v)}</span> },
    { title: '最大回撤', dataIndex: 'max_drawdown', width: 80, sorter: (a: FundStats, b: FundStats) => (a.max_drawdown ?? 999) - (b.max_drawdown ?? 999), render: (v: number | null) => <span style={{ color: 'var(--error)' }}>{pct(v)}</span> },
    { title: '波动率', dataIndex: 'volatility', width: 75, sorter: (a: FundStats, b: FundStats) => (a.volatility ?? 999) - (b.volatility ?? 999), render: (v: number | null) => pct(v) },
    { title: '夏普', dataIndex: 'sharpe_ratio', width: 65, sorter: (a: FundStats, b: FundStats) => (a.sharpe_ratio ?? -999) - (b.sharpe_ratio ?? -999), render: (v: number | null) => v !== null ? v.toFixed(2) : '-' },
    { title: '近1月', dataIndex: 'return_1m', width: 70, render: (v: number | null) => <span style={{ color: pctColor(v) }}>{pct(v)}</span> },
    { title: '近3月', dataIndex: 'return_3m', width: 70, render: (v: number | null) => <span style={{ color: pctColor(v) }}>{pct(v)}</span> },
    { title: '近6月', dataIndex: 'return_6m', width: 70, render: (v: number | null) => <span style={{ color: pctColor(v) }}>{pct(v)}</span> },
    { title: '近12月', dataIndex: 'return_12m', width: 70, render: (v: number | null) => <span style={{ color: pctColor(v) }}>{pct(v)}</span> },
  ];

  return (
    <div style={{ maxWidth: 1100 }}>
      <h2 style={{ fontSize: 15, margin: '0 0 12px' }}>基金筛选 / 比较</h2>

      {/* ── 指标概览表格 ── */}
      <div className="section-card" style={{ marginBottom: 12 }}>
        <div className="section-card-header"><span className="section-card-title">风险收益指标</span></div>
        <div className="section-card-body">
          <Table
            dataSource={stats}
            rowKey="fund_id"
            size="small"
            pagination={false}
            scroll={{ y: 300, x: 900 }}
            loading={loading}
            columns={statColumns}
            rowSelection={{
              selectedRowKeys: selectedIds,
              onChange: (keys) => setSelectedIds(keys as number[]),
            }}
          />
        </div>
      </div>

      {/* ── 归一化净值对比图 ── */}
      {selectedIds.length > 0 && (
        <div className="section-card" style={{ marginBottom: 12 }}>
          <div className="section-card-header">
            <span className="section-card-title">净值走势对比（归一化）</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
              已选 {selectedIds.length} 只基金
            </span>
          </div>
          <div className="section-card-body">
            <ReactECharts option={chartOption} notMerge style={{ height: 350 }} />
          </div>
        </div>
      )}

      {/* ── 同类排名 ── */}
      {ranking.length > 0 && (
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">同类排名（良田模型）</span></div>
          <div className="section-card-body">
            {ranking.map((group) => (
              <div key={group.category_id} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                  <Tag>{group.category_name}</Tag>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>({group.funds.length} 只)</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {group.funds.map((f, i) => (
                    <div key={f.fund_id} style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      background: 'var(--bg-group)',
                      fontSize: 11,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}>
                      <span style={{ fontWeight: 600, color: i === 0 ? 'var(--success)' : undefined }}>#{i + 1}</span>
                      <span>{f.fund_name}</span>
                      <span style={{ color: pctColor(f.annualized_return) }}>{pct(f.annualized_return)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
