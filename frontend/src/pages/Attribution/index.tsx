import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

interface SnapshotPoint {
  date: string;
  total: number;
  categories: Record<string, number>;
}

interface AssetHistory {
  series: SnapshotPoint[];
  category_keys: string[];
}

const MODELS = ['良田模型', '全天候策略', '地区分布'];

const PALETTE = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8d0',
  '#f6b26b', '#a4c2f4',
];

const fmt = (v: number) => `¥${(v / 10000).toFixed(1)}万`;
const fmtFull = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });

export default function Attribution() {
  const [model, setModel] = useState('良田模型');
  const [data, setData] = useState<AssetHistory | null>(null);

  useEffect(() => {
    get<AssetHistory>(`/attribution/asset-history?model=${encodeURIComponent(model)}&weeks=12`)
      .then((r) => { if (r.success) setData(r.data); });
  }, [model]);

  const series = data?.series ?? [];
  const keys = data?.category_keys ?? [];

  const stackedOption = useMemo(() => {
    const dates = series.map((s) => s.date);
    return {
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'shadow' as const },
        formatter: (params: { seriesName: string; value: number; color: string }[]) => {
          const date = dates[params[0] ? (params as unknown as { dataIndex: number }[])[0].dataIndex : 0];
          const total = params.reduce((s, p) => s + (p.value || 0), 0);
          const rows = params
            .filter((p) => p.value > 0)
            .sort((a, b) => b.value - a.value)
            .map((p) => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:4px"></span>${p.seriesName}: ${fmt(p.value)}`)
            .join('<br/>');
          return `${date}<br/><b>合计: ${fmt(total)}</b><br/>${rows}`;
        },
      },
      legend: { type: 'scroll' as const, bottom: 0, textStyle: { fontSize: 11 } },
      grid: { top: 16, bottom: 60, left: 72, right: 16 },
      xAxis: {
        type: 'category' as const,
        data: dates,
        axisLabel: { fontSize: 11, rotate: 30 },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: { fontSize: 11, formatter: (v: number) => `${(v / 10000).toFixed(0)}万` },
      },
      series: keys.map((key, i) => ({
        name: key,
        type: 'bar',
        stack: 'total',
        itemStyle: { color: PALETTE[i % PALETTE.length] },
        data: series.map((s) => s.categories[key] ?? 0),
      })),
    };
  }, [series, keys]);

  // 最新两周的环比变化
  const latest = series[series.length - 1];
  const prev = series[series.length - 2];

  const changeRows = useMemo(() => {
    if (!latest) return [];
    return keys.map((key) => {
      const cur = latest.categories[key] ?? 0;
      const pre = prev?.categories[key] ?? 0;
      const delta = cur - pre;
      const deltaPct = pre > 0 ? (delta / pre) * 100 : null;
      return { key, cur, pre, delta, deltaPct };
    }).sort((a, b) => b.cur - a.cur);
  }, [latest, prev, keys]);

  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>资产变化</h2>
        <div style={{ display: 'flex', gap: 6 }}>
          {MODELS.map((m) => (
            <button
              key={m}
              onClick={() => setModel(m)}
              style={{
                padding: '3px 12px',
                fontSize: 12,
                borderRadius: 4,
                border: '1px solid',
                cursor: 'pointer',
                borderColor: model === m ? '#7c3aed' : '#d1d5db',
                background: model === m ? '#f5f3ff' : '#fff',
                color: model === m ? '#7c3aed' : '#374151',
                fontWeight: model === m ? 600 : 400,
              }}
            >
              {m}
            </button>
          ))}
        </div>
        {latest && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#6b7280' }}>
            最新快照：{latest.date} &nbsp;总计 <b style={{ color: '#111' }}>¥{fmtFull(latest.total)}</b>
          </span>
        )}
      </div>

      {/* 堆叠柱状图 */}
      <div className="section-card" style={{ marginBottom: 16 }}>
        <div className="section-card-header">
          <span className="section-card-title">各类资产每周金额</span>
        </div>
        <div className="section-card-body">
          {series.length > 0
            ? <ReactECharts option={stackedOption} style={{ height: 340 }} />
            : <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af', fontSize: 12 }}>暂无数据</div>}
        </div>
      </div>

      {/* 环比变化表 */}
      {changeRows.length > 0 && (
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">
              环比变化&ensp;
              <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 400 }}>
                {prev?.date} → {latest?.date}
              </span>
            </span>
          </div>
          <div className="section-card-body" style={{ padding: 0 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #f3f4f6', color: '#6b7280' }}>
                  <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>类别</th>
                  <th style={{ padding: '8px 16px', textAlign: 'right', fontWeight: 500 }}>上期</th>
                  <th style={{ padding: '8px 16px', textAlign: 'right', fontWeight: 500 }}>本期</th>
                  <th style={{ padding: '8px 16px', textAlign: 'right', fontWeight: 500 }}>变化</th>
                  <th style={{ padding: '8px 16px', textAlign: 'right', fontWeight: 500 }}>涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                {changeRows.map(({ key, cur, pre, delta, deltaPct }, i) => (
                  <tr
                    key={key}
                    style={{ borderBottom: '1px solid #f9fafb', background: i % 2 === 0 ? '#fff' : '#fafafa' }}
                  >
                    <td style={{ padding: '7px 16px', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                          background: PALETTE[keys.indexOf(key) % PALETTE.length],
                          flexShrink: 0,
                        }}
                      />
                      {key}
                    </td>
                    <td style={{ padding: '7px 16px', textAlign: 'right', color: '#6b7280' }}>
                      {pre > 0 ? `¥${fmtFull(pre)}` : '-'}
                    </td>
                    <td style={{ padding: '7px 16px', textAlign: 'right', fontWeight: 500 }}>
                      ¥{fmtFull(cur)}
                    </td>
                    <td style={{ padding: '7px 16px', textAlign: 'right', color: delta >= 0 ? '#ef4444' : '#22c55e', fontWeight: 500 }}>
                      {delta >= 0 ? '+' : ''}¥{fmtFull(delta)}
                    </td>
                    <td style={{ padding: '7px 16px', textAlign: 'right', color: (deltaPct ?? 0) >= 0 ? '#ef4444' : '#22c55e' }}>
                      {deltaPct !== null ? `${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(2)}%` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
