import { Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

interface Summary {
  current_value: number;
  total_invested: number;
  total_profit: number;
  total_return_pct: number | null;
  total_weekly_investments: number;
  first_date: string;
  latest_date: string;
  weeks_tracked: number;
}

interface FundAttribution {
  fund_id: number;
  fund_code: string;
  fund_name: string;
  channel: string;
  current_amount: number;
  profit: number;
  invested: number;
  return_pct: number | null;
  contribution_pct: number;
}

interface CategoryAttribution {
  category_id: number;
  category_name: string;
  current_amount: number;
  profit: number;
  invested: number;
  return_pct: number | null;
  contribution_pct: number;
  fund_count: number;
}

interface TWRPoint {
  date: string;
  twr: number;
}

const fmt = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
const pct = (v: number | null) => v !== null ? `${v.toFixed(2)}%` : '-';
const profitColor = (v: number) => v >= 0 ? 'var(--success)' : 'var(--error)';

export default function Attribution() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [byFund, setByFund] = useState<FundAttribution[]>([]);
  const [byCat, setByCat] = useState<CategoryAttribution[]>([]);
  const [twr, setTwr] = useState<TWRPoint[]>([]);

  useEffect(() => {
    Promise.all([
      get<Summary>('/attribution/summary'),
      get<FundAttribution[]>('/attribution/by-fund'),
      get<CategoryAttribution[]>('/attribution/by-category'),
      get<TWRPoint[]>('/attribution/twr'),
    ]).then(([s, f, c, t]) => {
      if (s.success) setSummary(s.data);
      if (f.success) setByFund(f.data);
      if (c.success) setByCat(c.data);
      if (t.success) setTwr(t.data);
    });
  }, []);

  const twrOption = useMemo(() => ({
    tooltip: { trigger: 'axis' as const, formatter: (params: { data: [string, number] }[]) => {
      const p = params[0];
      return `${p.data[0]}<br/>TWR: ${p.data[1].toFixed(2)}%`;
    }},
    grid: { top: 20, bottom: 30, left: 60, right: 20 },
    xAxis: { type: 'time' as const },
    yAxis: { type: 'value' as const, axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%` } },
    series: [{
      type: 'line',
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.15 },
      data: twr.map((p) => [p.date, p.twr]),
    }],
  }), [twr]);

  const fundBarOption = useMemo(() => {
    const top = byFund.slice(0, 15);
    return {
      tooltip: { trigger: 'axis' as const },
      grid: { top: 10, bottom: 30, left: 100, right: 60 },
      xAxis: { type: 'value' as const, axisLabel: { formatter: (v: number) => `¥${(v / 1000).toFixed(0)}k` } },
      yAxis: { type: 'category' as const, data: top.map((f) => f.fund_name.slice(0, 10)).reverse(), axisLabel: { fontSize: 10 } },
      series: [{
        type: 'bar',
        data: top.map((f) => ({
          value: f.profit,
          itemStyle: { color: f.profit >= 0 ? '#91cc75' : '#ee6666' },
        })).reverse(),
        label: { show: true, position: 'right' as const, fontSize: 10, formatter: (p: { value: number }) => `¥${fmt(p.value)}` },
      }],
    };
  }, [byFund]);

  const catPieOption = useMemo(() => ({
    tooltip: { trigger: 'item' as const, formatter: (p: { name: string; value: number; percent: number }) => `${p.name}: ¥${fmt(p.value)} (${p.percent}%)` },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      label: { fontSize: 10 },
      data: byCat.map((c) => ({ name: c.category_name, value: Math.abs(c.profit) })),
    }],
  }), [byCat]);

  return (
    <div style={{ maxWidth: 960 }}>
      <h2 style={{ fontSize: 15, margin: '0 0 12px' }}>收益归因分析</h2>

      {/* ── 概览卡片 ── */}
      {summary && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <div className="stat-card" style={{ flex: 1, minWidth: 120, textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>¥{fmt(summary.current_value)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>当前总值</div>
          </div>
          <div className="stat-card" style={{ flex: 1, minWidth: 120, textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>¥{fmt(summary.total_invested)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>累计投入</div>
          </div>
          <div className="stat-card" style={{ flex: 1, minWidth: 120, textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: profitColor(summary.total_profit) }}>
              ¥{fmt(summary.total_profit)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>总收益</div>
          </div>
          <div className="stat-card" style={{ flex: 1, minWidth: 120, textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: profitColor(summary.total_return_pct ?? 0) }}>
              {pct(summary.total_return_pct)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>总收益率</div>
          </div>
          <div className="stat-card" style={{ flex: 1, minWidth: 120, textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{summary.weeks_tracked}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>追踪周数</div>
          </div>
        </div>
      )}

      {/* ── TWR 曲线 ── */}
      {twr.length > 1 && (
        <div className="section-card" style={{ marginBottom: 12 }}>
          <div className="section-card-header"><span className="section-card-title">时间加权收益率 (TWR)</span></div>
          <div className="section-card-body">
            <ReactECharts option={twrOption} style={{ height: 250 }} />
          </div>
        </div>
      )}

      {/* ── 按基金收益贡献 ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div className="section-card" style={{ flex: 2, minWidth: 300 }}>
          <div className="section-card-header"><span className="section-card-title">基金收益贡献</span></div>
          <div className="section-card-body">
            {byFund.length > 0 ? (
              <ReactECharts option={fundBarOption} style={{ height: Math.max(200, byFund.slice(0, 15).length * 28 + 60) }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>暂无数据</div>
            )}
          </div>
        </div>

        {/* ── 按分类收益贡献 ── */}
        <div className="section-card" style={{ flex: 1, minWidth: 250 }}>
          <div className="section-card-header"><span className="section-card-title">分类收益贡献</span></div>
          <div className="section-card-body">
            {byCat.length > 0 ? (
              <>
                <ReactECharts option={catPieOption} style={{ height: 200 }} />
                <div style={{ fontSize: 11 }}>
                  {byCat.map((c) => (
                    <div key={c.category_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <span>{c.category_name} <Tag style={{ fontSize: 10 }}>{c.fund_count}只</Tag></span>
                      <span style={{ color: profitColor(c.profit) }}>¥{fmt(c.profit)} ({pct(c.return_pct)})</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>暂无数据</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
