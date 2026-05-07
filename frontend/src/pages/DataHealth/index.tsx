import { ReloadOutlined, RobotOutlined, ToolOutlined } from '@ant-design/icons';
import { Alert, Button, Table, Tag, Timeline, message } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { get, post } from '../../services/api';

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

interface RepairResult {
  total: number;
  repaired: number;
  details: Array<{
    fund_code: string;
    fund_name: string;
    old_gap: number;
    new_gap: number | null;
    status: string;
    error?: string;
  }>;
}

interface AIDiagnoseResult {
  status: string;
  diagnosis: string;
  explanation?: string;
  actions_taken: Array<{ action: string; status: string; detail: string }>;
  anomaly_summary?: { error_jobs: number; error_funds: number; failed_runs: number };
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
  const [repairing, setRepairing] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnoseResult, setDiagnoseResult] = useState<AIDiagnoseResult | null>(null);
  const autoTriggered = useRef(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, f, h] = await Promise.all([
        get<SourceHealth[]>('/data-health/overview'),
        get<FundCoverage[]>('/data-health/fund-coverage'),
        get<JobHistoryItem[]>('/data-health/job-history', { limit: 30 }),
      ]);
      if (s.success) setSources(s.data);
      if (f.success) setFunds(f.data);
      if (h.success) setHistory(h.data);

      // 检测到异常时自动触发 AI 诊断（每次进入页面仅一次）
      const hasErrors =
        (s.success && s.data.some((x) => x.status === 'error')) ||
        (f.success && f.data.some((x) => x.status === 'error'));
      if (hasErrors && !autoTriggered.current) {
        autoTriggered.current = true;
        triggerDiagnose();
      }
    } catch {
      // network error
    } finally {
      setLoading(false);
    }
  }, []);

  const triggerDiagnose = async () => {
    setDiagnosing(true);
    setDiagnoseResult(null);
    try {
      const r = await post<AIDiagnoseResult>('/data-health/ai-diagnose', undefined);
      if (r.success) {
        setDiagnoseResult(r.data);
        if (r.data.status === 'healthy') {
          message.success('系统正常，无需修复');
        } else {
          message.info('AI 诊断完成');
          loadAll(); // 刷新数据
        }
      } else {
        message.error(r.error || 'AI 诊断失败');
      }
    } catch {
      message.error('AI 诊断请求失败');
    } finally {
      setDiagnosing(false);
    }
  };

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleRepair = async () => {
    setRepairing(true);
    try {
      const r = await post<RepairResult>('/data-health/repair', undefined);
      if (r.success) {
        const { total, repaired, details } = r.data;
        if (total === 0) {
          message.info('没有需要修复的基金');
        } else {
          const failed = details.filter((d) => d.status === 'failed');
          if (failed.length > 0) {
            message.warning(`修复完成: ${repaired}/${total} 成功，${failed.length} 失败`);
          } else {
            message.success(`修复完成: ${repaired}/${total} 基金已修复`);
          }
        }
        loadAll();
      } else {
        message.error(r.error || '修复失败');
      }
    } catch {
      message.error('修复请求失败');
    } finally {
      setRepairing(false);
    }
  };

  const healthyCnt = sources.filter((s) => s.status === 'healthy').length;
  const warnCnt = sources.filter((s) => s.status === 'warning').length;
  const errCnt = sources.filter((s) => s.status === 'error').length;
  const fundErrCnt = funds.filter((f) => f.status === 'error').length;

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>数据源健康监控</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="small" icon={<RobotOutlined />} onClick={triggerDiagnose} loading={diagnosing} type="primary">
            AI 诊断修复
          </Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>
            刷新
          </Button>
        </div>
      </div>

      {/* -- 概览卡片 -- */}
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

      {/* -- AI 诊断结果 -- */}
      {diagnoseResult && diagnoseResult.status !== 'healthy' && (
        <Alert
          type={diagnoseResult.actions_taken.some((a) => a.status === 'failed') ? 'warning' : 'info'}
          showIcon
          icon={<RobotOutlined />}
          style={{ marginBottom: 12 }}
          message="AI 诊断结果"
          description={
            <div style={{ fontSize: 12 }}>
              <div style={{ marginBottom: 4 }}>{diagnoseResult.diagnosis}</div>
              {diagnoseResult.explanation && (
                <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>{diagnoseResult.explanation}</div>
              )}
              {diagnoseResult.actions_taken.length > 0 && (
                <div>
                  <strong>执行动作:</strong>
                  {diagnoseResult.actions_taken.map((a, i) => (
                    <Tag key={i} color={a.status === 'done' ? 'green' : a.status === 'failed' ? 'red' : 'default'} style={{ marginLeft: 4 }}>
                      {a.action}: {a.detail}
                    </Tag>
                  ))}
                </div>
              )}
            </div>
          }
          closable
          onClose={() => setDiagnoseResult(null)}
        />
      )}

      {/* -- 数据源状态 -- */}
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

      {/* -- 基金数据覆盖 -- */}
      <div className="section-card" style={{ marginBottom: 12 }}>
        <div className="section-card-header">
          <span className="section-card-title">基金数据覆盖</span>
          {fundErrCnt > 0 && (
            <Button
              size="small"
              type="primary"
              danger
              icon={<ToolOutlined />}
              loading={repairing}
              onClick={handleRepair}
              style={{ marginLeft: 8 }}
            >
              修复异常 ({fundErrCnt})
            </Button>
          )}
        </div>
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

      {/* -- 执行历史 -- */}
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
