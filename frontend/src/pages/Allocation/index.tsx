import { ReloadOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Spin, Statistic, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { get, post } from '../../services/api';

interface AllocationTarget {
  category_id: number;
  category_name: string;
  parent_name: string;
  target_weight: number;
  current_weight: number;
  deviation: number;
  annual_return: number | null;
  volatility: number | null;
  max_drawdown: number | null;
  sharpe_ratio: number | null;
  calculated_at: string;
  status: string;
}

interface DeviationSummary {
  max_deviation_pct: number;
  needs_rebalance: boolean;
  total_capital: number;
  deviations: Array<{
    category_id: number;
    category_name: string;
    parent_name: string;
    target_weight: number;
    current_weight: number;
    deviation: number;
    deviation_pct: number;
    amount_diff_cny: number;
  }>;
  suggestions: Suggestion[];
}

interface Suggestion {
  category_name: string;
  action: string;
  amount: number;
  deviation: number;
  target_weight: number;
  current_weight: number;
}

interface SnapshotMeta {
  portfolio_expected_return: number | null;
  portfolio_volatility: number | null;
  portfolio_sharpe: number | null;
}

const pct = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(2)}%` : '-';

const fmtAmount = (v: number | null | undefined) => {
  if (v == null) return '-';
  return v >= 10000
    ? `${(v / 10000).toFixed(1)}万`
    : v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
};

function deviationStatus(dev: number): { color: string; label: string } {
  const abs = Math.abs(dev);
  if (abs <= 0.03) return { color: 'green', label: 'ok' };
  if (abs <= 0.05) return { color: 'orange', label: 'warn' };
  return { color: 'red', label: 'alert' };
}

export default function Allocation() {
  const [targets, setTargets] = useState<AllocationTarget[]>([]);
  const [deviation, setDeviation] = useState<DeviationSummary | null>(null);
  const [snapshotMeta, setSnapshotMeta] = useState<SnapshotMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [calculating, setCalculating] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [targetsResp, devResp] = await Promise.all([
        get<AllocationTarget[]>('/allocation/current'),
        get<DeviationSummary>('/allocation/deviation'),
      ]);
      if (targetsResp.success) setTargets(targetsResp.data);
      if (devResp.success) setDeviation(devResp.data);

      // Try to get snapshot metrics from history
      const histResp = await get<{
        items: Array<SnapshotMeta>;
      }>('/allocation/history', { page: 1, page_size: 1 });
      if (histResp.success && histResp.data) {
        const items = Array.isArray(histResp.data) ? histResp.data : (histResp.data as any).items || [];
        if (items.length > 0) {
          setSnapshotMeta(items[0] as SnapshotMeta);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRecalculate = async () => {
    setCalculating(true);
    try {
      const resp = await post('/allocation/calculate', { trigger: 'manual' });
      if (resp.success) {
        message.success('配比重新计算完成');
        loadData();
      } else {
        message.error(resp.error || '计算失败');
      }
    } catch {
      message.error('计算请求失败');
    } finally {
      setCalculating(false);
    }
  };

  const columns: ColumnsType<AllocationTarget> = [
    {
      title: '父类(L1)',
      dataIndex: 'parent_name',
      width: 100,
      filters: [...new Set(targets.map((t) => t.parent_name))].map((v) => ({
        text: v,
        value: v,
      })),
      onFilter: (value, record) => record.parent_name === value,
    },
    {
      title: '类别(L2)',
      dataIndex: 'category_name',
      width: 120,
    },
    {
      title: '目标配比',
      dataIndex: 'target_weight',
      width: 100,
      align: 'right',
      render: (v: number) => pct(v),
      sorter: (a, b) => a.target_weight - b.target_weight,
    },
    {
      title: '实际配比',
      dataIndex: 'current_weight',
      width: 100,
      align: 'right',
      render: (v: number) => pct(v),
      sorter: (a, b) => a.current_weight - b.current_weight,
    },
    {
      title: '偏离',
      dataIndex: 'deviation',
      width: 100,
      align: 'right',
      sorter: (a, b) => Math.abs(a.deviation) - Math.abs(b.deviation),
      defaultSortOrder: 'descend',
      render: (v: number) => {
        const { color } = deviationStatus(v);
        return (
          <span style={{ color, fontWeight: 600 }}>
            {v > 0 ? '+' : ''}
            {pct(v)}
          </span>
        );
      },
    },
    {
      title: '年化收益',
      dataIndex: 'annual_return',
      width: 100,
      align: 'right',
      render: (v: number | null) => pct(v),
    },
    {
      title: '波动率',
      dataIndex: 'volatility',
      width: 90,
      align: 'right',
      render: (v: number | null) => pct(v),
    },
    {
      title: 'Sharpe',
      dataIndex: 'sharpe_ratio',
      width: 80,
      align: 'right',
      render: (v: number | null) => (v != null ? v.toFixed(2) : '-'),
    },
    {
      title: '状态',
      width: 70,
      align: 'center',
      render: (_, record) => {
        const { color, label } = deviationStatus(record.deviation);
        const icon = label === 'ok' ? 'ok' : label === 'warn' ? 'warn' : 'alert';
        return <Tag color={color}>{icon}</Tag>;
      },
    },
  ];

  return (
    <Spin spinning={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>良田模型配比</h2>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          loading={calculating}
          onClick={handleRecalculate}
        >
          重新计算
        </Button>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="组合预期收益"
            value={snapshotMeta?.portfolio_expected_return != null ? snapshotMeta.portfolio_expected_return * 100 : '-'}
            suffix={snapshotMeta?.portfolio_expected_return != null ? '%' : ''}
            precision={2}
          />
        </Card>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="波动率"
            value={snapshotMeta?.portfolio_volatility != null ? snapshotMeta.portfolio_volatility * 100 : '-'}
            suffix={snapshotMeta?.portfolio_volatility != null ? '%' : ''}
            precision={2}
          />
        </Card>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="Sharpe"
            value={snapshotMeta?.portfolio_sharpe ?? '-'}
            precision={2}
          />
        </Card>
        <Card size="small" style={{ flex: 1 }}>
          <Statistic
            title="健康评分"
            value={deviation ? Math.max(0, Math.round(100 - deviation.max_deviation_pct * 5)) : '-'}
            valueStyle={{
              color: deviation && deviation.health_score >= 80
                ? 'green'
                : deviation && deviation.health_score >= 60
                  ? 'orange'
                  : 'red',
            }}
          />
        </Card>
      </div>

      {/* Main table */}
      <Card size="small" style={{ marginBottom: 20 }}>
        <Table
          dataSource={targets}
          columns={columns}
          rowKey="category_id"
          pagination={false}
          size="small"
          scroll={{ x: 860 }}
        />
      </Card>

      {/* Rebalance suggestions */}
      {deviation && deviation.suggestions && deviation.suggestions.length > 0 && (
        <Card size="small" title="调仓建议">
          {deviation.suggestions.map((s, i) => (
            <Alert
              key={i}
              type={s.action === '加仓' ? 'success' : 'warning'}
              showIcon
              style={{ marginBottom: 8 }}
              message={
                <span>
                  <Tag color={s.action === '加仓' ? 'green' : 'red'}>
                    {s.action}
                  </Tag>
                  <strong>{s.category_name}</strong>{' '}
                  {fmtAmount(s.amount)}
                  <span style={{ marginLeft: 12, color: '#999', fontSize: 12 }}>
                    偏离 {pct(s.deviation)} (目标 {pct(s.target_weight)} / 实际{' '}
                    {pct(s.current_weight)})
                  </span>
                </span>
              }
            />
          ))}
        </Card>
      )}

      {deviation && (!deviation.suggestions || deviation.suggestions.length === 0) && !deviation.needs_rebalance && (
        <Alert
          type="success"
          showIcon
          message="当前配比健康，无需调仓"
          style={{ marginBottom: 20 }}
        />
      )}
    </Spin>
  );
}
