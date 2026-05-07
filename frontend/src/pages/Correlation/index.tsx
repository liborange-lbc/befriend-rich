import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

interface FundLabel {
  fund_id: number;
  fund_code: string;
  fund_name: string;
}

interface MatrixData {
  labels: FundLabel[];
  matrix: (number | null)[][];
}

interface DiversificationData {
  score: number | null;
  avg_correlation: number | null;
  fund_count: number;
}

function buildHeatmapOption(data: MatrixData, title: string) {
  const names = data.labels.map((l) => l.fund_name.slice(0, 8));
  const heatData: [number, number, number | string][] = [];
  for (let i = 0; i < data.matrix.length; i++) {
    for (let j = 0; j < data.matrix[i].length; j++) {
      const v = data.matrix[i][j];
      heatData.push([j, i, v !== null ? Math.round(v * 100) / 100 : 0]);
    }
  }

  return {
    title: { text: title, left: 'center', textStyle: { fontSize: 13 } },
    tooltip: {
      position: 'top' as const,
      formatter: (p: { data: [number, number, number | string] }) => {
        const [x, y, v] = p.data;
        return `${names[y]} × ${names[x]}: ${v}`;
      },
    },
    grid: { top: 40, bottom: 60, left: 80, right: 20 },
    xAxis: { type: 'category' as const, data: names, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'category' as const, data: names, axisLabel: { fontSize: 10 } },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: 'horizontal' as const,
      left: 'center',
      bottom: 0,
      inRange: { color: ['#2166ac', '#f7f7f7', '#b2182b'] },
      textStyle: { fontSize: 10 },
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: { show: data.labels.length <= 10, fontSize: 10 },
      itemStyle: { borderWidth: 1, borderColor: '#fff' },
    }],
  };
}

export default function Correlation() {
  const [corrMatrix, setCorrMatrix] = useState<MatrixData | null>(null);
  const [overlapMatrix, setOverlapMatrix] = useState<MatrixData | null>(null);
  const [diversification, setDiversification] = useState<DiversificationData | null>(null);

  useEffect(() => {
    Promise.all([
      get<MatrixData>('/correlation/matrix'),
      get<MatrixData>('/correlation/overlap'),
      get<DiversificationData>('/correlation/diversification-score'),
    ]).then(([c, o, d]) => {
      if (c.success) setCorrMatrix(c.data);
      if (o.success) setOverlapMatrix(o.data);
      if (d.success) setDiversification(d.data);
    }).catch(() => {
      // network error
    });
  }, []);

  const corrOption = useMemo(() => corrMatrix ? buildHeatmapOption(corrMatrix, '收益率相关性') : null, [corrMatrix]);

  const overlapOption = useMemo(() => {
    if (!overlapMatrix) return null;
    const opt = buildHeatmapOption(overlapMatrix, '持仓重叠度 (Jaccard)');
    opt.visualMap.min = 0;
    return opt;
  }, [overlapMatrix]);

  const scoreColor = diversification != null && diversification.score != null
    ? diversification.score > 0.6 ? 'var(--success)' : diversification.score > 0.3 ? 'var(--warning)' : 'var(--error)'
    : undefined;

  return (
    <div style={{ maxWidth: 960 }}>
      <h2 style={{ fontSize: 15, margin: '0 0 12px' }}>相关性分析</h2>

      {/* ── 分散度评分 ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: scoreColor }}>
            {diversification != null && diversification.score != null ? diversification.score.toFixed(2) : '-'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>分散度评分</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>1 = 完全分散, 0 = 完全相关</div>
        </div>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {diversification != null && diversification.avg_correlation != null ? diversification.avg_correlation.toFixed(2) : '-'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>平均相关系数</div>
        </div>
        <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {diversification?.fund_count ?? '-'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>参与基金数</div>
        </div>
      </div>

      {/* ── 相关性热力图 ── */}
      <div className="section-card" style={{ marginBottom: 12 }}>
        <div className="section-card-body">
          {corrOption ? (
            <ReactECharts option={corrOption} style={{ height: Math.max(350, (corrMatrix?.labels.length || 5) * 35 + 100) }} />
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>
              需要至少2只基金有20天以上价格数据
            </div>
          )}
        </div>
      </div>

      {/* ── 持仓重叠热力图 ── */}
      <div className="section-card">
        <div className="section-card-body">
          {overlapOption ? (
            <ReactECharts option={overlapOption} style={{ height: Math.max(350, (overlapMatrix?.labels.length || 5) * 35 + 100) }} />
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>
              需要至少2只基金有持仓数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
