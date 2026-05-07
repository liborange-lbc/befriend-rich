import {
  CalendarOutlined,
  CaretRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  LoadingOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Button, Drawer, message, Tag, Timeline, Tooltip } from 'antd';
import dayjs from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';
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

// ── Trigger Parsing ──

interface ParsedSchedule {
  type: 'hourly' | 'daily' | 'weekly' | 'monthly';
  hour?: string;
  minute?: string;
  day?: string;
  dayOfWeek?: string;
  label: string;
}

function parseTrigger(trigger: string): ParsedSchedule {
  const m = trigger.match(/cron\[(.+)\]/);
  if (!m) return { type: 'daily', label: trigger };
  const parts = m[1];

  const val = (key: string) => {
    const mm = parts.match(new RegExp(`${key}='([^']+)'`));
    return mm ? mm[1] : null;
  };

  const hour = val('hour');
  const minute = val('minute') ?? '0';
  const day = val('day');
  const dow = val('day_of_week');

  if (day) {
    return { type: 'monthly', day, hour: hour ?? '0', minute, label: `每月${day}日 ${hour ?? '0'}:${minute.padStart(2, '0')}` };
  }
  if (dow) {
    const dowLabels: Record<string, string> = { mon: '一', tue: '二', wed: '三', thu: '四', fri: '五', sat: '六', sun: '日' };
    return { type: 'weekly', dayOfWeek: dow, hour: hour ?? '0', minute, label: `每周${dowLabels[dow] ?? dow} ${hour ?? '0'}:${minute.padStart(2, '0')}` };
  }
  if (hour && hour.includes(',')) {
    return { type: 'daily', hour, minute, label: `每天 ${hour} 点` };
  }
  if (hour) {
    return { type: 'daily', hour, minute, label: `每天 ${hour}:${minute.padStart(2, '0')}` };
  }
  if (minute === '0') {
    return { type: 'hourly', minute: '0', label: '每小时整点' };
  }
  return { type: 'daily', label: trigger };
}

function shouldRunOnDay(schedule: ParsedSchedule, date: dayjs.Dayjs): boolean {
  if (schedule.type === 'hourly' || schedule.type === 'daily') return true;
  if (schedule.type === 'monthly') {
    return date.date() === Number(schedule.day);
  }
  if (schedule.type === 'weekly') {
    const dowMap: Record<string, number> = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 0 };
    return date.day() === (dowMap[schedule.dayOfWeek!] ?? -1);
  }
  return false;
}

// ── Formatting Helpers ──

function formatTime(t: string | null): string {
  if (!t || t === 'None') return '-';
  const d = new Date(t);
  if (isNaN(d.getTime())) return t;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatRelative(t: string | null): string {
  if (!t || t === 'None') return '';
  const d = new Date(t);
  if (isNaN(d.getTime())) return '';
  const diff = d.getTime() - Date.now();
  if (diff <= 0) return '';
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (hours > 24) return `${Math.floor(hours / 24)}天后`;
  if (hours > 0) return `${hours}h${mins}m后`;
  return `${mins}m后`;
}

function StatusTag({ status }: { status: string | null }) {
  if (!status) return <Tag>未运行</Tag>;
  if (status === 'success') return <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>;
  if (status === 'failed') return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>;
  if (status === 'running') return <Tag icon={<LoadingOutlined />} color="processing">运行中</Tag>;
  return <Tag>{status}</Tag>;
}

// ── Frequency badge colors ──

const freqColors: Record<string, string> = {
  hourly: '#8B5CF6',
  daily: '#3B82F6',
  weekly: '#10B981',
  monthly: '#F59E0B',
};

const freqLabels: Record<string, string> = {
  hourly: '每时',
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
};

// ── Month Calendar Strip ──

function MonthCalendarStrip({ jobs }: { jobs: SchedulerJob[] }) {
  const today = dayjs();
  const daysInMonth = today.daysInMonth();
  const monthStart = today.startOf('month');

  const jobSchedules = useMemo(() =>
    jobs.map((j) => ({ job: j, schedule: parseTrigger(j.trigger) })),
    [jobs]
  );

  // Build day → jobs mapping
  const dayJobsMap = useMemo(() => {
    const map: Record<number, { job: SchedulerJob; schedule: ParsedSchedule }[]> = {};
    for (let d = 1; d <= daysInMonth; d++) {
      const date = monthStart.date(d);
      const matches = jobSchedules.filter(({ schedule }) => shouldRunOnDay(schedule, date));
      if (matches.length > 0) {
        map[d] = matches;
      }
    }
    return map;
  }, [jobSchedules, daysInMonth, monthStart]);

  const dowLabels = ['日', '一', '二', '三', '四', '五', '六'];

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <CalendarOutlined style={{ fontSize: 16, color: 'var(--text-secondary, #6B7280)' }} />
        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #111827)' }}>
          {today.format('YYYY年M月')} 任务日历
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, fontSize: 12 }}>
          {Object.entries(freqLabels).map(([key, label]) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-secondary, #6B7280)' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: freqColors[key], display: 'inline-block' }} />
              {label}
            </span>
          ))}
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${daysInMonth}, 1fr)`,
        gap: 2,
        overflowX: 'auto',
      }}>
        {Array.from({ length: daysInMonth }, (_, i) => {
          const d = i + 1;
          const date = monthStart.date(d);
          const isToday = d === today.date();
          const isPast = date.isBefore(today, 'day');
          const dayJobs = dayJobsMap[d];
          const hasJobs = !!dayJobs;

          // Count by frequency type
          const freqCounts: Record<string, number> = {};
          if (dayJobs) {
            for (const { schedule } of dayJobs) {
              freqCounts[schedule.type] = (freqCounts[schedule.type] || 0) + 1;
            }
          }

          return (
            <Tooltip
              key={d}
              title={hasJobs ? (
                <div style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{date.format('M月D日')} ({dowLabels[date.day()]})</div>
                  {dayJobs.map(({ job, schedule }) => (
                    <div key={job.id} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: freqColors[schedule.type], display: 'inline-block', flexShrink: 0 }} />
                      <span>{job.name}</span>
                      <span style={{ opacity: 0.6, marginLeft: 'auto', paddingLeft: 8 }}>{schedule.hour ?? ''}:{(schedule.minute ?? '0').padStart(2, '0')}</span>
                    </div>
                  ))}
                </div>
              ) : `${date.format('M月D日')} (${dowLabels[date.day()]}) — 无任务`}
            >
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '6px 0 4px',
                borderRadius: 8,
                cursor: 'default',
                background: isToday ? 'var(--accent-bg, #EFF6FF)' : 'transparent',
                border: isToday ? '1.5px solid var(--accent-color, #3B82F6)' : '1.5px solid transparent',
                opacity: isPast ? 0.45 : 1,
                transition: 'all 0.15s',
                minWidth: 0,
              }}>
                <span style={{
                  fontSize: 10,
                  color: 'var(--text-secondary, #9CA3AF)',
                  lineHeight: 1,
                }}>
                  {dowLabels[date.day()]}
                </span>
                <span style={{
                  fontSize: 14,
                  fontWeight: isToday ? 700 : 500,
                  color: isToday ? 'var(--accent-color, #3B82F6)' : 'var(--text-primary, #374151)',
                  lineHeight: 1.4,
                  fontFeatureSettings: "'tnum'",
                }}>
                  {d}
                </span>
                {/* Frequency dots */}
                <div style={{ display: 'flex', gap: 2, marginTop: 2, height: 6 }}>
                  {hasJobs ? Object.entries(freqCounts).map(([type, count]) => (
                    <span
                      key={type}
                      style={{
                        width: Math.min(count, 3) * 4 + 2,
                        height: 4,
                        borderRadius: 2,
                        background: freqColors[type],
                      }}
                    />
                  )) : <span style={{ width: 4, height: 4 }} />}
                </div>
              </div>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

// ── Job Card ──

function JobCard({ job, onTrigger, onHistory, triggering }: {
  job: SchedulerJob;
  onTrigger: (id: string) => void;
  onHistory: (id: string, name: string) => void;
  triggering: boolean;
}) {
  const schedule = parseTrigger(job.trigger);
  const run = job.latest_run;
  const relTime = formatRelative(job.next_run_time);

  return (
    <div style={{
      borderRadius: 12,
      padding: '20px 22px',
      background: 'var(--card-bg, #fff)',
      border: '1px solid var(--border-color, #E5E7EB)',
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      transition: 'box-shadow 0.2s',
    }}
    onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.06)'; }}
    onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
    >
      {/* Header: name + frequency badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #111827)' }}>{job.name}</span>
        <span style={{
          fontSize: 11,
          padding: '1px 8px',
          borderRadius: 10,
          background: `${freqColors[schedule.type]}18`,
          color: freqColors[schedule.type],
          fontWeight: 500,
          whiteSpace: 'nowrap',
        }}>
          {schedule.label}
        </span>
      </div>

      {/* Description */}
      <div style={{ fontSize: 13, color: 'var(--text-secondary, #6B7280)', lineHeight: 1.5 }}>
        {job.description}
      </div>

      {/* Stats row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '10px 20px',
        fontSize: 12,
        color: 'var(--text-secondary, #9CA3AF)',
      }}>
        <div>
          <div style={{ marginBottom: 2, opacity: 0.7 }}>下次运行</div>
          <div style={{ color: 'var(--text-primary, #374151)', fontWeight: 500, fontFeatureSettings: "'tnum'" }}>
            {job.next_run_time ? formatTime(job.next_run_time) : '-'}
            {relTime && <span style={{ color: 'var(--accent-color, #3B82F6)', marginLeft: 6, fontSize: 11 }}>{relTime}</span>}
          </div>
        </div>
        <div>
          <div style={{ marginBottom: 2, opacity: 0.7 }}>最近运行</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {run ? (
              <>
                <StatusTag status={run.status} />
                <span style={{ fontFeatureSettings: "'tnum'", color: 'var(--text-primary, #374151)' }}>{formatTime(run.started_at)}</span>
              </>
            ) : (
              <span style={{ color: 'var(--text-secondary, #D1D5DB)' }}>从未运行</span>
            )}
          </div>
        </div>
      </div>

      {/* Result summary (if exists) */}
      {run?.summary && (
        <div style={{
          fontSize: 12,
          padding: '8px 12px',
          borderRadius: 8,
          background: run.status === 'failed' ? 'var(--error-bg, #FEF2F2)' : 'var(--subtle-bg, #F9FAFB)',
          color: run.status === 'failed' ? 'var(--error-color, #EF4444)' : 'var(--text-secondary, #6B7280)',
          lineHeight: 1.5,
          wordBreak: 'break-all',
          maxHeight: 60,
          overflow: 'hidden',
        }}>
          {run.summary}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
        <Button
          size="small"
          type="primary"
          ghost
          icon={<CaretRightOutlined />}
          loading={triggering}
          onClick={() => onTrigger(job.id)}
        >
          运行
        </Button>
        <Button
          size="small"
          icon={<HistoryOutlined />}
          onClick={() => onHistory(job.id, job.name)}
        >
          记录
        </Button>
      </div>
    </div>
  );
}

// ── Main Page ──

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

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

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>定时任务</h1>
        <Button icon={<ReloadOutlined />} onClick={loadJobs} loading={loading}>刷新</Button>
      </div>

      {/* Calendar Strip */}
      <MonthCalendarStrip jobs={jobs} />

      {/* Job Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: 16,
      }}>
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            onTrigger={handleTrigger}
            onHistory={openHistory}
            triggering={triggering === job.id}
          />
        ))}
      </div>

      {/* History Drawer */}
      <Drawer
        title={`${historyJobName} — 运行记录`}
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
