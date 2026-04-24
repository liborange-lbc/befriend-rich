import { ReloadOutlined } from '@ant-design/icons';
import { Button, Table, Tag, Timeline } from 'antd';
import { useEffect, useState } from 'react';
import { get } from '../../services/api';

interface SourceHealth {
  job_id: string;
  status: string;
  detail: string;
  last_run_at: string | null;
  last_run_status: string | null;
  last_success_at: string | null;
}

interface FundCoverage {
  fund_id: number;
  fund_code: string;
  fund_name: string;
  data_source: string;
  total_records: number;
  latest_date: string | null;
  gap_days: number | null;
  status: string;
}

interface JobHistoryItem {
  job_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_s: number | null;
  summary: string | null;
}

const JOB_LABELS: Record<string, string> = {
  fetch_market_data: '行情数据',
  strategy_check: '策略检查',
  webank_auto_import: '微众导入',
  alipay_auto_import: '支付宝导入',
  weekly_data_completion: '周数据补全',
  fetch_fund_holdings: '持仓数据',
  refresh_market_insight: '大盘洞察',
  auto_backup: '自动备份',
};

const STATUS_COLOR: Record<string, string> = {
  healthy: 'green',
  warning: 'orange',
  error: 'red',
  unknown: 'default',
};

const STATUS_LABEL: Record<string, string> = {
  healthy: '正常',
  warning: '警告',
  error: '异常',
  unknown: '未知',
};

export default function DataHealth() {
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [funds, setFunds] = useState<FundCoverage[]>([]);
  const [history, setHistory] = useState<JobHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    const [s, f, h] = await Promise.all([
      get<SourceHealth[]>('/data-health/overview'),
      get<FundCoverage[]>('/data-health/fund-coverage'),
      get<JobHistoryItem[]>('/data-health/job-history', { limit: 30 }),
    ]);
    if (s.success) setSources(s.data);
    if (f.success) setFunds(f.data);
    if (h.success) setHistory(h.data);
    setLoading(false);
  };

  useEffect(() => { loadAll(); }, []);

  const healthyCnt = sources.filter((s) => s.status === 'healthy').length;
  const warnCnt = sources.filter((s) => s.status === 'warning').length;
  const errCnt = sources.filter((s) => s.status === 'error').length;

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>数据源健康监控</h2>
        <Button size="small" icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>
          刷新
        </Button>
      </div>

      {/* ── 概览卡片 ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--success)' }}>{healthyCnt}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>正常</div>
        </div>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--warning)' }}>{warnCnt}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>警告</div>
        </div>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--error)' }}>{errCnt}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>异常</div>
        </div>
      </div>

      {/* ── 数据源状态 ── */}
      <div className="section-card" style={{ marginBottom: 12 }}>
        <div className="section-card-header"><span className="section-card-title">数据源状态</span></div>
        <div className="section-card-body">
          <Table
            dataSource={sources}
            rowKey="job_id"
            size="small"
            pagination={false}
            columns={[
              {
                title: '任务',
                dataIndex: 'job_id',
                render: (v: string) => <span style={{ fontSize: 12 }}>{JOB_LABELS[v] || v}</span>,
              },
              {
                title: '状态',
                dataIndex: 'status',
                width: 80,
                render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v]}</Tag>,
              },
              {
                title: '详情',
                dataIndex: 'detail',
                render: (v: string) => <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{v}</span>,
              },
              {
                title: '上次运行',
                dataIndex: 'last_run_at',
                width: 160,
                render: (v: string | null) => v ? <span style={{ fontSize: 11 }}>{v.replace('T', ' ').slice(0, 19)}</span> : '-',
              },
            ]}
          />
        </div>
      </div>

      {/* ── 基金数据覆盖 ── */}
      <div className="section-card" style={{ marginBottom: 12 }}>
        <div className="section-card-header"><span className="section-card-title">基金数据覆盖</span></div>
        <div className="section-card-body">
          <Table
            dataSource={funds}
            rowKey="fund_id"
            size="small"
            pagination={false}
            scroll={{ y: 300 }}
            columns={[
              { title: '代码', dataIndex: 'fund_code', width: 80, render: (v: string) => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v}</span> },
              { title: '名称', dataIndex: 'fund_name', ellipsis: true },
              { title: '数据源', dataIndex: 'data_source', width: 80 },
              { title: '记录数', dataIndex: 'total_records', width: 70, render: (v: number) => v.toLocaleString() },
              { title: '最新日期', dataIndex: 'latest_date', width: 100 },
              {
                title: '延迟(天)',
                dataIndex: 'gap_days',
                width: 80,
                render: (v: number | null) => v !== null ? v : '-',
              },
              {
                title: '状态',
                dataIndex: 'status',
                width: 70,
                render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v]}</Tag>,
              },
            ]}
          />
        </div>
      </div>

      {/* ── 执行历史 ── */}
      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">最近执行历史</span></div>
        <div className="section-card-body" style={{ maxHeight: 300, overflow: 'auto' }}>
          <Timeline
            items={history.map((h) => ({
              color: h.status === 'success' ? 'green' : 'red',
              children: (
                <div style={{ fontSize: 11 }}>
                  <span style={{ fontWeight: 600 }}>{JOB_LABELS[h.job_id] || h.job_id}</span>
                  <Tag color={h.status === 'success' ? 'green' : 'red'} style={{ marginLeft: 6, fontSize: 10 }}>
                    {h.status}
                  </Tag>
                  {h.duration_s !== null && (
                    <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>{h.duration_s.toFixed(1)}s</span>
                  )}
                  <div style={{ color: 'var(--text-muted)' }}>
                    {h.started_at.replace('T', ' ').slice(0, 19)}
                    {h.summary && h.summary !== 'OK' && (
                      <span style={{ marginLeft: 8, color: 'var(--text-secondary)' }}>{h.summary.slice(0, 100)}</span>
                    )}
                  </div>
                </div>
              ),
            }))}
          />
        </div>
      </div>
    </div>
  );
}
