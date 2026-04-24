import { CaretRightOutlined, CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined, HistoryOutlined, LoadingOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Drawer, message, Table, Tag, Timeline } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { get, post } from '../../services/api';

interface LatestRun {
  started_at: string | null;
  finished_at: string | null;
  status: string | null;
  summary: string | null;
}

interface SchedulerJob {
  id: string;
  name: string;
  description: string;
  trigger: string;
  next_run_time: string | null;
  latest_run: LatestRun | null;
}

interface JobRunRecord {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  summary: string | null;
}

function formatTrigger(trigger: string): string {
  // Parse APScheduler cron trigger string to human-readable
  // e.g. "cron[minute='0']" → "每小时整点"
  const m = trigger.match(/cron\[(.+)\]/);
  if (!m) return trigger;
  const parts = m[1];

  const has = (key: string) => parts.includes(`${key}=`);
  const val = (key: string) => {
    const mm = parts.match(new RegExp(`${key}='([^']+)'`));
    return mm ? mm[1] : null;
  };

  if (has('day') && val('day')) return `每月${val('day')}日 ${val('hour') ?? '0'}:${(val('minute') ?? '0').padStart(2, '0')}`;
  if (has('day_of_week') && val('day_of_week') === 'mon') return `每周一 ${val('hour') ?? '0'}:${(val('minute') ?? '0').padStart(2, '0')}`;
  if (has('hour') && val('hour') && val('hour')!.includes(',')) return `每天 ${val('hour')} 点`;
  if (has('hour') && val('hour')) return `每天 ${val('hour')}:${(val('minute') ?? '0').padStart(2, '0')}`;
  if (has('minute') && val('minute') === '0') return '每小时整点';
  return trigger;
}

function formatTime(t: string | null): string {
  if (!t || t === 'None') return '-';
  const d = new Date(t);
  if (isNaN(d.getTime())) return t;
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const pad = (n: number) => String(n).padStart(2, '0');
  const timeStr = `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;

  if (diffMs > 0) {
    const hours = Math.floor(diffMs / 3600000);
    const mins = Math.floor((diffMs % 3600000) / 60000);
    if (hours > 24) return `${timeStr} (${Math.floor(hours / 24)}天后)`;
    if (hours > 0) return `${timeStr} (${hours}h${mins}m后)`;
    return `${timeStr} (${mins}m后)`;
  }
  return timeStr;
}

function StatusTag({ status }: { status: string | null }) {
  if (!status) return <Tag>未运行</Tag>;
  if (status === 'success') return <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>;
  if (status === 'failed') return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>;
  if (status === 'running') return <Tag icon={<LoadingOutlined />} color="processing">运行中</Tag>;
  return <Tag>{status}</Tag>;
}

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  // History drawer
  const [historyJobId, setHistoryJobId] = useState<string | null>(null);
  const [historyJobName, setHistoryJobName] = useState('');
  const [history, setHistory] = useState<JobRunRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    const resp = await get<SchedulerJob[]>('/scheduler/jobs');
    if (resp.success) setJobs(resp.data);
    setLoading(false);
  }, []);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  const handleTrigger = useCallback(async (jobId: string) => {
    setTriggering(jobId);
    const resp = await post<{ triggered: boolean }>(`/scheduler/jobs/${jobId}/run`);
    if (resp.success) {
      message.success('任务已触发');
      loadJobs();
    } else {
      message.error('触发失败');
    }
    setTriggering(null);
  }, [loadJobs]);

  const openHistory = useCallback(async (jobId: string, jobName: string) => {
    setHistoryJobId(jobId);
    setHistoryJobName(jobName);
    setHistoryLoading(true);
    const resp = await get<JobRunRecord[]>(`/scheduler/jobs/${jobId}/history`);
    if (resp.success) setHistory(resp.data);
    setHistoryLoading(false);
  }, []);

  const columns = [
    {
      title: '任务', key: 'name', width: 200,
      render: (_: unknown, r: SchedulerJob) => (
        <div>
          <div style={{ fontWeight: 500 }}>{r.name}</div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{r.description}</div>
        </div>
      ),
    },
    {
      title: '执行周期', dataIndex: 'trigger', key: 'trigger', width: 160,
      render: (v: string) => <span style={{ fontSize: 12 }}><ClockCircleOutlined style={{ marginRight: 4, color: '#9CA3AF' }} />{formatTrigger(v)}</span>,
    },
    {
      title: '下次运行', dataIndex: 'next_run_time', key: 'next_run_time', width: 180,
      render: (v: string | null) => <span style={{ fontSize: 12, fontFeatureSettings: "'tnum'" }}>{formatTime(v)}</span>,
    },
    {
      title: '最近运行', key: 'latest_run', width: 200,
      render: (_: unknown, r: SchedulerJob) => {
        if (!r.latest_run) return <span style={{ color: '#D1D5DB', fontSize: 12 }}>从未运行</span>;
        return (
          <div style={{ fontSize: 12 }}>
            <StatusTag status={r.latest_run.status} />
            <span style={{ marginLeft: 6, color: '#9CA3AF', fontFeatureSettings: "'tnum'" }}>{formatTime(r.latest_run.started_at)}</span>
          </div>
        );
      },
    },
    {
      title: '运行结果', key: 'summary', ellipsis: true,
      render: (_: unknown, r: SchedulerJob) => {
        if (!r.latest_run?.summary) return <span style={{ color: '#D1D5DB' }}>-</span>;
        return <span style={{ fontSize: 12, color: r.latest_run.status === 'failed' ? '#EF4444' : '#6B7280' }}>{r.latest_run.summary}</span>;
      },
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_: unknown, r: SchedulerJob) => (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="small" type="primary" ghost
            icon={<CaretRightOutlined />}
            loading={triggering === r.id}
            onClick={() => handleTrigger(r.id)}
          >
            运行
          </Button>
          <Button
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => openHistory(r.id, r.name)}
          >
            记录
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>定时任务</h1>
        <Button icon={<ReloadOutlined />} onClick={loadJobs} loading={loading}>刷新</Button>
      </div>

      <div className="section-card">
        <div className="section-card-body" style={{ padding: 0 }}>
          <Table
            dataSource={jobs}
            columns={columns}
            rowKey="id"
            size="small"
            loading={loading}
            pagination={false}
          />
        </div>
      </div>

      {/* History Drawer */}
      <Drawer
        title={`${historyJobName} - 运行记录`}
        open={!!historyJobId}
        onClose={() => setHistoryJobId(null)}
        width={480}
      >
        {historyLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><LoadingOutlined style={{ fontSize: 24 }} /></div>
        ) : history.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>暂无运行记录</div>
        ) : (
          <Timeline
            items={history.map((r) => ({
              color: r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'blue',
              children: (
                <div style={{ fontSize: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <StatusTag status={r.status} />
                    <span style={{ color: '#374151', fontFeatureSettings: "'tnum'" }}>{formatTime(r.started_at)}</span>
                    {r.finished_at && (
                      <span style={{ color: '#9CA3AF' }}>
                        耗时 {Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000)}s
                      </span>
                    )}
                  </div>
                  {r.summary && (
                    <div style={{
                      color: r.status === 'failed' ? '#EF4444' : '#6B7280',
                      background: r.status === 'failed' ? '#FEF2F2' : '#F9FAFB',
                      padding: '4px 8px', borderRadius: 4, marginTop: 4,
                      wordBreak: 'break-all',
                    }}>
                      {r.summary}
                    </div>
                  )}
                </div>
              ),
            }))}
          />
        )}
      </Drawer>
    </div>
  );
}
