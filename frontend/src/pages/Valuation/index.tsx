import { Select, Table, Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

interface IndexInfo {
  code: string;
  name: string;
}

interface ValuationData {
  index_code: string;
  index_name: string;
  current_pe: number;
  current_date: string;
  pe_percentile: number;
  temperature: number;
  dca_coefficient: number;
  dca_label: string;
  pe_min: number;
  pe_max: number;
  pe_median: number;
  pe_mean: number;
  data_points: number;
  pe_history: { date: string; pe: number }[];
}

interface DCARow {
  range: string;
  coefficient: number;
  label: string;
}

const tempColor = (t: number) => {
  if (t <= 20) return '#2166ac';
  if (t <= 40) return '#67a9cf';
  if (t <= 60) return '#f7f7f7';
  if (t <= 80) return '#ef8a62';
  return '#b2182b';
};

const tempBg = (t: number) => {
  if (t <= 20) return 'rgba(33,102,172,0.15)';
  if (t <= 40) return 'rgba(103,169,207,0.15)';
  if (t <= 60) return 'rgba(247,247,247,0.3)';
  if (t <= 80) return 'rgba(239,138,98,0.15)';
  return 'rgba(178,24,43,0.15)';
};

export default function Valuation() {
  const [indices, setIndices] = useState<IndexInfo[]>([]);
  const [selectedCode, setSelectedCode] = useState<string>('000300');
  const [valuation, setValuation] = useState<ValuationData | null>(null);
  const [dcaTable, setDcaTable] = useState<DCARow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    get<IndexInfo[]>('/valuation/indices').then((r) => r.success && setIndices(r.data));
    get<DCARow[]>('/valuation/dca-coefficient').then((r) => r.success && setDcaTable(r.data));
  }, []);

  useEffect(() => {
    if (!selectedCode) return;
    setLoading(true);
    setValuation(null);
    get<ValuationData>(`/valuation/history/${selectedCode}`).then((r) => {
      if (r.success && r.data) setValuation(r.data);
      setLoading(false);
    });
  }, [selectedCode]);

  const gaugeOption = useMemo(() => {
    if (!valuation) return null;
    return {
      series: [{
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        pointer: { show: true, length: '60%', width: 4 },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [[0.2, '#2166ac'], [0.4, '#67a9cf'], [0.6, '#d1e5f0'], [0.8, '#ef8a62'], [1, '#b2182b']],
          },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { fontSize: 10, distance: -30 },
        detail: {
          valueAnimation: true,
          formatter: (v: number) => `${v.toFixed(0)}°`,
          fontSize: 24,
          offsetCenter: [0, '20%'],
        },
        data: [{ value: valuation.temperature }],
      }],
    };
  }, [valuation]);

  const peChartOption = useMemo(() => {
    if (!valuation?.pe_history) return null;
    const pe = valuation.pe_history;
    return {
      tooltip: { trigger: 'axis' as const },
      grid: { top: 20, bottom: 30, left: 50, right: 20 },
      xAxis: { type: 'time' as const },
      yAxis: { type: 'value' as const, name: 'PE', nameTextStyle: { fontSize: 10 } },
      series: [{
        type: 'line',
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#5470c6' },
        areaStyle: { opacity: 0.1, color: '#5470c6' },
        data: pe.map((p) => [p.date, p.pe]),
        markLine: {
          silent: true,
          data: [
            { yAxis: valuation.pe_median, label: { formatter: `中位数 ${valuation.pe_median}`, fontSize: 10 }, lineStyle: { type: 'dashed' as const, color: '#999' } },
            { yAxis: valuation.current_pe, label: { formatter: `当前 ${valuation.current_pe}`, fontSize: 10 }, lineStyle: { color: tempColor(valuation.temperature) } },
          ],
        },
      }],
    };
  }, [valuation]);

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>估值指标</h2>
        <Select
          value={selectedCode}
          onChange={setSelectedCode}
          size="small"
          style={{ width: 160 }}
          options={indices.map((i) => ({ value: i.code, label: `${i.name} (${i.code})` }))}
        />
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 12 }}>
          正在获取 PE 数据（约需 10-30 秒）...
        </div>
      )}

      {valuation && (
        <>
          {/* ── 温度计 + 概览 ── */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            <div className="section-card" style={{ flex: 1, minWidth: 250 }}>
              <div className="section-card-header"><span className="section-card-title">{valuation.index_name} 估值温度计</span></div>
              <div className="section-card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {gaugeOption && <ReactECharts option={gaugeOption} style={{ height: 200, width: '100%' }} />}
                <Tag color={tempColor(valuation.temperature)} style={{ fontSize: 13, padding: '2px 12px' }}>
                  {valuation.dca_label}
                </Tag>
              </div>
            </div>

            <div style={{ flex: 1, minWidth: 250, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="stat-card" style={{ textAlign: 'center', background: tempBg(valuation.temperature) }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>PE {valuation.current_pe}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>当前 PE · 分位 {valuation.pe_percentile}%</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{valuation.pe_min}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>最低 PE</div>
                </div>
                <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{valuation.pe_median}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>中位 PE</div>
                </div>
                <div className="stat-card" style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{valuation.pe_max}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>最高 PE</div>
                </div>
              </div>
              <div className="stat-card" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--primary)' }}>{valuation.dca_coefficient}x</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>建议定投系数</div>
              </div>
            </div>
          </div>

          {/* ── PE 历史图 ── */}
          <div className="section-card" style={{ marginBottom: 12 }}>
            <div className="section-card-header">
              <span className="section-card-title">PE 历史走势</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8 }}>{valuation.data_points} 数据点</span>
            </div>
            <div className="section-card-body">
              {peChartOption && <ReactECharts option={peChartOption} style={{ height: 280 }} />}
            </div>
          </div>
        </>
      )}

      {/* ── 定投系数对照表 ── */}
      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">定投系数对照表</span></div>
        <div className="section-card-body">
          <Table
            dataSource={dcaTable}
            rowKey="range"
            size="small"
            pagination={false}
            columns={[
              { title: '估值温度', dataIndex: 'range' },
              { title: '定投系数', dataIndex: 'coefficient', render: (v: number) => <span style={{ fontWeight: 700 }}>{v}x</span> },
              { title: '状态', dataIndex: 'label', render: (v: string) => <Tag>{v}</Tag> },
            ]}
          />
        </div>
      </div>
    </div>
  );
}
