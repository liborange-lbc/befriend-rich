import { QuestionCircleOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  InputNumber,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tooltip,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import ReactECharts from 'echarts-for-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { get, post } from '../../services/api';

/* ── Types ── */

interface ICPriceRow {
  date: string;
  index?: number;
  current_month?: number;
  next_month?: number;
  current_quarter?: number;
  next_quarter?: number;
}

interface ICStatRow {
  contract_type: string;
  label: string;
  spread_current?: number;
  annual_current?: number;
  annual_1m?: number;
  annual_1y?: number;
  annual_3y?: number;
  annual_all?: number;
}

interface ICRollPath {
  from: string;
  from_code: string;
  to: string;
  to_code: string;
  spread_pts: number;
  annual: number;
  hist_avg: number | null;
  vs_hist: number | null;
  day_diff: number;
}

interface ICRollGuidance {
  expiry: string;
  days_left: number;
  timing: string;
  timing_text: string;
  recommend: string;
  paths: ICRollPath[];
}

interface ICPositionCalc {
  entry_point: number;
  entry_capital: number;
  margin_rate: number;
  multiplier: number;
  contract_value: number;
  margin_per_contract: number;
  num_contracts: number;
  total_margin: number;
  remaining_capital: number;
  margin_call_point: number;
  liquidation_point: number;
}

/* ── Helpers ── */

/** 计算某月第三个周五（IC期货到期日 = 换仓日）。month: 1-12 */
function getThirdFriday(year: number, month: number): string {
  // 1st day of month
  const d = new Date(year, month - 1, 1);
  const dow = d.getDay(); // 0=Sun
  // first Friday: if dow<=5 → (5-dow+1), else (5+7-dow+1)
  const firstFri = dow <= 5 ? 5 - dow + 1 : 12 - dow + 1;
  const thirdFri = firstFri + 14;
  const dd = new Date(year, month - 1, thirdFri);
  return dd.toISOString().slice(0, 10);
}

/** 生成日期范围内所有交割日及标记（区分换月/换季）。
 *  换季月 = 1/4/7/10（到期后下月跨过季月，当季合约跳变）。 */
function getRollDates(dates: string[]): { date: string; label: string; isQuarter: boolean }[] {
  if (!dates.length) return [];
  const start = new Date(dates[0]);
  const end = new Date(dates[dates.length - 1]);
  const dateSet = new Set(dates);
  const results: { date: string; label: string; isQuarter: boolean }[] = [];
  const quarterRollMonths = new Set([1, 4, 7, 10]);

  const d = new Date(start.getFullYear(), start.getMonth(), 1);
  while (d <= end) {
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const fri = getThirdFriday(y, m);
    if (fri >= dates[0] && fri <= dates[dates.length - 1]) {
      let actual = fri;
      if (!dateSet.has(fri)) {
        for (let off = 1; off <= 5; off++) {
          const nd = new Date(y, m - 1, parseInt(fri.slice(8)) + off);
          const ns = nd.toISOString().slice(0, 10);
          if (dateSet.has(ns)) { actual = ns; break; }
        }
      }
      const isQ = quarterRollMonths.has(m);
      const label = isQ ? '换季' : '换月';
      results.push({ date: actual, label, isQuarter: isQ });
    }
    d.setMonth(d.getMonth() + 1);
  }
  return results;
}

/** 根据日期计算当月/下月/当季/下季合约代码 */
function getContractCodes(dateStr: string): Record<string, string> {
  const d = new Date(dateStr);
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const thirdFri = new Date(getThirdFriday(y, m));
  let cy = y, cm = m;
  if (d > thirdFri) {
    cm++;
    if (cm > 12) { cm = 1; cy++; }
  }
  const fmt = (yy: number, mm: number) => `IC${(yy % 100).toString().padStart(2, '0')}${mm.toString().padStart(2, '0')}`;
  const m1 = [cy, cm] as const;
  let ny = cy, nm = cm + 1;
  if (nm > 12) { nm = 1; ny++; }
  const m2 = [ny, nm] as const;
  const qms = [3, 6, 9, 12];
  let cqy = cy, cqm = qms.find((q) => (cy === ny && q > nm) || (cy < ny && q > 0)) ?? 0;
  if (!cqm) { cqy = ny + 1; cqm = 3; }
  if (cqy === cy && cqm <= nm) { cqy = ny; cqm = qms.find((q) => q > nm) ?? 0; if (!cqm) { cqy++; cqm = 3; } }
  const qi = qms.indexOf(cqm);
  let nqy = cqy, nqm = qi + 1 < qms.length ? qms[qi + 1] : 0;
  if (!nqm) { nqy = cqy + 1; nqm = 3; }
  return {
    current_month: fmt(...m1),
    next_month: fmt(...m2),
    current_quarter: fmt(cqy, cqm),
    next_quarter: fmt(nqy, nqm),
  };
}

/* ── Constants ── */

const SERIES_CONFIG = [
  { key: 'index', name: '中证500', color: '#E74C3C', width: 3 },
  { key: 'current_month', name: '当月', color: '#3498DB', width: 1.5 },
  { key: 'next_month', name: '下月', color: '#2ECC71', width: 1.5 },
  { key: 'current_quarter', name: '当季', color: '#F39C12', width: 1.5 },
  { key: 'next_quarter', name: '下季', color: '#9B59B6', width: 1.5 },
] as const;

const SPREAD_SERIES = SERIES_CONFIG.slice(1); // 期货合约的价差

const fmtPct = (v?: number) =>
  v != null ? `${v >= 0 ? '+' : ''}${(v * 1).toFixed(2)}%` : '-';
const fmtNum = (v?: number) =>
  v != null ? v.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : '-';

/* ── Component ── */

export default function ICOption() {
  const [prices, setPrices] = useState<ICPriceRow[]>([]);
  const [stats, setStats] = useState<ICStatRow[]>([]);
  const [roll, setRoll] = useState<ICRollGuidance | null>(null);
  const [loading, setLoading] = useState(false);
  const [backfilling, setBackfilling] = useState(false);

  const [entryPoint, setEntryPoint] = useState<number>(5500);
  const [entryCapital, setEntryCapital] = useState<number>(500000);
  const [marginRate, setMarginRate] = useState<number>(12);
  const [numContracts, setNumContracts] = useState<number>(1);
  const [position, setPosition] = useState<ICPositionCalc | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const priceChartRef = useRef<ReactECharts>(null);
  const spreadChartRef = useRef<ReactECharts>(null);
  const syncing = useRef(false);

  const loadData = useCallback(() => {
    setLoading(true);
    get<{ prices: ICPriceRow[]; stats: ICStatRow[]; roll: ICRollGuidance }>('/ic-option/prices')
      .then((r) => {
        if (r.success) {
          setPrices(r.data.prices);
          setStats(r.data.stats);
          setRoll(r.data.roll);
          const latest = r.data.prices[r.data.prices.length - 1];
          if (latest?.index) setEntryPoint(Math.round(latest.index));
        }
      })
      .finally(() => setLoading(false));
  }, []);

  /** 从外部源拉取最新数据，成功后刷新页面数据并更新时间戳 */
  const refreshData = useCallback(() => {
    post('/ic-option/fetch?days=1', undefined).then((r) => {
      if (r.success) {
        setLastRefresh(new Date());
        loadData();
      }
    });
  }, [loadData]);

  useEffect(() => {
    loadData();
    const timer = setInterval(refreshData, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, [loadData, refreshData]);

  useEffect(() => {
    if (!entryPoint || entryPoint < 100) return;
    get<ICPositionCalc>('/ic-option/position', {
      entry_point: entryPoint,
      entry_capital: entryCapital,
      margin_rate: marginRate / 100,
      num_contracts: numContracts,
    }).then((r) => {
      if (r.success) setPosition(r.data);
    });
  }, [entryPoint, entryCapital, marginRate, numContracts]);

  const handleBackfill = () => {
    setBackfilling(true);
    post('/ic-option/backfill', undefined)
      .then((r) => {
        if (r.success) { message.success('历史数据回填完成'); loadData(); }
        else { message.error(r.error || '回填失败'); }
      })
      .finally(() => setBackfilling(false));
  };

  const handleFetchLatest = () => {
    post('/ic-option/fetch?days=7', undefined).then((r) => {
      if (r.success) { message.success('最新数据获取完成'); loadData(); }
    });
  };

  /* ── 联动 dataZoom + tooltip ── */

  const syncZoom = useCallback((source: 'price' | 'spread', params: { start: number; end: number }) => {
    if (syncing.current) return;
    syncing.current = true;
    const target = source === 'price' ? spreadChartRef.current : priceChartRef.current;
    if (target) {
      target.getEchartsInstance().dispatchAction({ type: 'dataZoom', start: params.start, end: params.end });
    }
    syncing.current = false;
  }, []);

  // 通过 onChartReady 绑定 updateAxisPointer 事件实现联动
  const bindTooltipSync = useCallback((source: 'price' | 'spread', chart: { on: Function; }) => {
    chart.on('updateAxisPointer', (e: { dataIndex?: number; seriesIndex?: number }) => {
      if (syncing.current || e.dataIndex == null) return;
      syncing.current = true;
      const target = source === 'price' ? spreadChartRef.current : priceChartRef.current;
      if (target) {
        target.getEchartsInstance().dispatchAction({
          type: 'showTip', seriesIndex: 0, dataIndex: e.dataIndex,
        });
      }
      syncing.current = false;
    });
  }, []);


  /** 当前合约代码（用于图例和 tooltip 显示） */
  const currentCodes = useMemo(() => {
    if (!prices.length) return {} as Record<string, string>;
    const latest = prices[prices.length - 1];
    return getContractCodes(latest.date);
  }, [prices]);

  /** 默认显示最近一年：计算 dataZoom start % */
  const defaultZoomStart = useMemo(() => {
    if (!prices.length) return 0;
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const cutoff = oneYearAgo.toISOString().slice(0, 10);
    const idx = prices.findIndex((p) => p.date >= cutoff);
    return idx > 0 ? Math.round((idx / prices.length) * 100) : 0;
  }, [prices]);

  /* ── 换仓标记线 ── */

  const rollDates = useMemo(() => {
    if (!prices.length) return [];
    return getRollDates(prices.map((p) => p.date));
  }, [prices]);

  /** 换仓标记：x 轴圆点 + 换月/换季标签，换季用红色三角 */
  const rollMarkPoint = useMemo(() => ({
    silent: true,
    label: {
      show: true,
      formatter: (p: { name: string }) => p.name,
      fontSize: 9,
      fontWeight: 'bold' as const,
      color: '#333',
      position: 'top' as const,
      distance: 4,
    },
    data: rollDates.map((r) => ({
      name: r.label,
      xAxis: r.date,
      yAxis: 'min',
      symbol: r.isQuarter ? 'diamond' : 'circle',
      symbolSize: r.isQuarter ? 8 : 5,
      itemStyle: { color: r.isQuarter ? '#ff4d4f' : '#F57C00' },
      label: { color: r.isQuarter ? '#ff4d4f' : '#999' },
    })),
  }), [rollDates]);

  /* ── 价格趋势图 ── */

  const priceLegendNames = useMemo(() =>
    SERIES_CONFIG.map((s) => {
      const code = currentCodes[s.key];
      return code ? `${s.name}(${code})` : s.name;
    }),
  [currentCodes]);

  const priceChartOption = useMemo(() => {
    if (!prices.length) return null;
    const dates = prices.map((p) => p.date);
    return {
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'line', triggerTooltip: true },
        formatter: (params: Array<{ seriesIndex: number; value: number; color: string; axisValueLabel: string }>) => {
          if (!params.length) return '';
          const dateStr = params[0].axisValueLabel;
          const codes = getContractCodes(dateStr);
          let html = `<strong>${dateStr}</strong><br/>`;
          for (const p of params) {
            if (p.value == null) continue;
            const cfg = SERIES_CONFIG[p.seriesIndex];
            const code = codes[cfg.key];
            const label = code ? `${cfg.name}(${code})` : cfg.name;
            html += `<span style="color:${p.color}">●</span> ${label}: ${fmtNum(p.value)}<br/>`;
          }
          return html;
        },
      },
      legend: { data: priceLegendNames, top: 4 },
      grid: { left: '3%', right: '3%', bottom: '5%', top: '10%', containLabel: true },
      dataZoom: [
        { type: 'inside', start: defaultZoomStart, end: 100 },
      ],
      xAxis: { type: 'category' as const, data: dates, axisLabel: { fontSize: 11 } },
      yAxis: {
        type: 'value' as const,
        scale: true,
        boundaryGap: ['5%', '5%'],
        axisLabel: { formatter: (v: number) => v.toLocaleString() },
      },
      series: SERIES_CONFIG.map((s, i) => ({
        name: priceLegendNames[i],
        type: 'line',
        data: prices.map((p) => (p as Record<string, unknown>)[s.key] ?? null),
        showSymbol: false,
        lineStyle: { width: s.width, color: s.color },
        itemStyle: { color: s.color },
        connectNulls: true,
        ...(i === 0 ? { markPoint: rollMarkPoint } : {}),
      })),
    };
  }, [prices, priceLegendNames, rollMarkPoint, defaultZoomStart]);

  /* ── 价差趋势图 ── */

  const spreadChartOption = useMemo(() => {
    if (!prices.length) return null;
    const dates = prices.map((p) => p.date);
    return {
      tooltip: { trigger: 'axis' as const, axisPointer: { type: 'line', triggerTooltip: true } },
      legend: { data: SPREAD_SERIES.map((s) => s.name + '价差'), top: 0, textStyle: { fontSize: 11 } },
      grid: { left: '3%', right: '3%', bottom: '15%', top: '14%', containLabel: true },
      dataZoom: [
        { type: 'slider', start: defaultZoomStart, end: 100, bottom: 4, height: 20 },
        { type: 'inside', start: defaultZoomStart, end: 100 },
      ],
      xAxis: { type: 'category' as const, data: dates, axisLabel: { fontSize: 11 } },
      yAxis: {
        type: 'value' as const,
        scale: true,
        axisLabel: { fontSize: 11 },
        name: '贴水点数',
        nameTextStyle: { fontSize: 11 },
      },
      series: SPREAD_SERIES.map((s, i) => ({
        name: s.name + '价差',
        type: 'line',
        data: prices.map((p) => {
          const idx = p.index;
          const fut = (p as Record<string, unknown>)[s.key] as number | undefined;
          return idx && fut ? Math.round((idx - fut) * 100) / 100 : null;
        }),
        showSymbol: false,
        lineStyle: { width: 1.2, color: s.color },
        itemStyle: { color: s.color },
        connectNulls: true,
        ...(i === 0 ? { markPoint: { ...rollMarkPoint, label: { ...rollMarkPoint.label, show: false } } } : {}),
      })),
    };
  }, [prices, rollMarkPoint, defaultZoomStart]);

  /* ── Stats Table ── */

  const tipIcon = (tip: string) => (
    <Tooltip title={tip}>
      <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999', cursor: 'help' }} />
    </Tooltip>
  );

  const statColumns: ColumnsType<ICStatRow> = [
    { title: '合约', dataIndex: 'label', width: 64, fixed: 'left' },
    { title: <span>价差{tipIcon('中证500指数 − 期货收盘价\n正数 = 期货贴水')}</span>, dataIndex: 'spread_current', width: 80, render: fmtNum },
    { title: <span>年化{tipIcon('(价差 / 指数) ÷ (剩余天数 / 365) × 100%\n持有到期的年化贴水收益')}</span>, dataIndex: 'annual_current', width: 80, render: fmtPct },
    { title: <span>1月{tipIcon('近 22 交易日年化均值')}</span>, dataIndex: 'annual_1m', width: 72, render: fmtPct },
    { title: <span>1年{tipIcon('近 252 交易日年化均值')}</span>, dataIndex: 'annual_1y', width: 72, render: fmtPct },
    { title: <span>3年{tipIcon('近 756 交易日年化均值')}</span>, dataIndex: 'annual_3y', width: 72, render: fmtPct },
    { title: <span>全部{tipIcon('全部历史年化均值')}</span>, dataIndex: 'annual_all', width: 72, render: fmtPct },
  ];

  /* ── Roll Guidance ── */

  const timingColor = roll?.timing === 'urgent' ? '#ff4d4f' : roll?.timing === 'optimal' ? '#faad14' : '#52c41a';

  /* ── Render ── */

  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>IC期权 · 中证500股指期货</h2>
        <Space>
          <Button onClick={handleFetchLatest} size="small">获取最新</Button>
          <Button onClick={handleBackfill} loading={backfilling} size="small" type="primary">
            回填历史数据
          </Button>
        </Space>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
      ) : (
        <>
          {/* 趋势图 + 价差图 */}
          {priceChartOption && (
            <Card size="small" style={{ marginBottom: 16 }}>
              <ReactECharts
                ref={priceChartRef}
                option={priceChartOption}
                style={{ height: 360 }}
                onChartReady={(chart) => bindTooltipSync('price', chart)}
                onEvents={{
                  dataZoom: (_: unknown, chart: { getOption: () => { dataZoom: { start: number; end: number }[] } }) => {
                    const z = chart.getOption().dataZoom[0];
                    syncZoom('price', { start: z.start, end: z.end });
                  },
                }}
              />
            </Card>
          )}
          {spreadChartOption && (
            <Card size="small" title="贴水走势" style={{ marginBottom: 16 }}>
              <ReactECharts
                ref={spreadChartRef}
                option={spreadChartOption}
                style={{ height: 180 }}
                onChartReady={(chart) => bindTooltipSync('spread', chart)}
                onEvents={{
                  dataZoom: (_: unknown, chart: { getOption: () => { dataZoom: { start: number; end: number }[] } }) => {
                    const z = chart.getOption().dataZoom[0];
                    syncZoom('spread', { start: z.start, end: z.end });
                  },
                }}
              />
            </Card>
          )}
          {/* 实时数据横条 */}
          {prices.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {SERIES_CONFIG.map((s) => {
                  const latest = prices[prices.length - 1];
                  const price = (latest as Record<string, unknown>)[s.key] as number | undefined;
                  const stat = stats.find((st) => st.contract_type === s.key);
                  const code = currentCodes[s.key];
                  const label = code ? `${s.name}(${code})` : s.name;
                  return (
                    <div key={s.key} style={{
                      flex: 1, minWidth: 150,
                      background: '#fafafa', borderLeft: `3px solid ${s.color}`,
                      padding: '6px 10px', borderRadius: 4,
                    }}>
                      <div style={{ fontSize: 12, color: s.color, fontWeight: 600 }}>{label}</div>
                      <div style={{ fontSize: 15, fontWeight: 700 }}>{fmtNum(price)}</div>
                      {s.key !== 'index' && stat != null && (
                        <div style={{ fontSize: 11, color: '#666' }}>
                          基差 {fmtNum(stat.spread_current)} · 年化 {fmtPct(stat.annual_current)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {lastRefresh && (
                <div style={{ textAlign: 'right', fontSize: 11, color: '#999', marginTop: 4 }}>
                  最近刷新: {lastRefresh.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
              )}
            </div>
          )}
          {!priceChartOption && !loading && (
            <Card size="small" style={{ marginBottom: 16, textAlign: 'center', padding: 40 }}>
              暂无数据，请先点击「回填历史数据」获取 10 年历史
            </Card>
          )}

          {/* 基差年化统计 + 换仓指引 */}
          {stats.length > 0 && (
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={24} lg={12}>
                <Card size="small" title="基差年化统计">
                  <Table<ICStatRow>
                    dataSource={stats}
                    columns={statColumns}
                    rowKey="contract_type"
                    pagination={false}
                    size="small"
                    scroll={{ x: 520 }}
                  />
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card size="small" title="当前换仓指引">
                  {roll?.paths?.length ? (
                    <div>
                      {/* 到期倒计时 */}
                      <div style={{ padding: '6px 0 10px', borderBottom: '1px solid #f0f0f0', marginBottom: 10 }}>
                        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: timingColor, marginRight: 6, verticalAlign: 'middle' }} />
                        <span style={{ fontSize: 13 }}>{roll.timing_text}</span>
                      </div>
                      {/* 路径对比 */}
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ color: '#999', fontSize: 12 }}>
                            <th style={{ padding: '4px 0', textAlign: 'left' }}>换仓路径</th>
                            <th style={{ padding: '4px 0', textAlign: 'right' }}>价差</th>
                            <th style={{ padding: '4px 0', textAlign: 'right' }}>
                              年化{tipIcon('展期年化 = (近月价−远月价) / 指数 ÷ (到期间隔天数/365) × 100%')}
                            </th>
                            <th style={{ padding: '4px 0', textAlign: 'right' }}>
                              1年均值{tipIcon('过去252个交易日同路径年化均值')}
                            </th>
                            <th style={{ padding: '4px 0', textAlign: 'right' }}>
                              偏离{tipIcon('当前年化 − 历史均值\n正=高于均值，展期时机较好')}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {roll.paths.map((p) => {
                            const best = roll.paths.reduce((a, b) => a.annual > b.annual ? a : b);
                            const isBest = p.to_code === best.to_code;
                            return (
                              <tr key={p.to_code} style={{ background: isBest ? '#f6ffed' : undefined }}>
                                <td style={{ padding: '6px 0', fontWeight: 500 }}>
                                  {p.from_code} → {p.to_code}
                                  <span style={{ color: '#999', fontSize: 11, marginLeft: 4 }}>({p.to}·{p.day_diff}天)</span>
                                  {isBest && <span style={{ color: '#52c41a', fontSize: 11, marginLeft: 4 }}>推荐</span>}
                                </td>
                                <td style={{ padding: '6px 0', textAlign: 'right' }}>{p.spread_pts.toFixed(1)}</td>
                                <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600, color: p.annual >= 0 ? '#52c41a' : '#ff4d4f' }}>
                                  {p.annual >= 0 ? '+' : ''}{p.annual.toFixed(2)}%
                                </td>
                                <td style={{ padding: '6px 0', textAlign: 'right', color: '#666' }}>
                                  {p.hist_avg != null ? `${p.hist_avg >= 0 ? '+' : ''}${p.hist_avg.toFixed(2)}%` : '-'}
                                </td>
                                <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 500, color: (p.vs_hist ?? 0) > 0 ? '#52c41a' : '#ff4d4f' }}>
                                  {p.vs_hist != null ? `${p.vs_hist >= 0 ? '+' : ''}${p.vs_hist.toFixed(2)}` : '-'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {/* 综合建议 */}
                      <div style={{ marginTop: 10, padding: '8px 10px', background: '#fafafa', borderRadius: 4, fontSize: 12, color: '#555', lineHeight: 1.6 }}>
                        {roll.recommend}
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>暂无数据</div>
                  )}
                </Card>
              </Col>
            </Row>
          )}

          {/* 持仓计算器 */}
          <Card size="small" title="持仓计算器（做多）">
            <Row gutter={[16, 12]}>
              <Col xs={12} sm={6}>
                <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>当前点位</div>
                <InputNumber value={entryPoint} onChange={(v) => v && setEntryPoint(v)} min={100} step={10} style={{ width: '100%' }} addonAfter="点" />
              </Col>
              <Col xs={12} sm={6}>
                <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>开仓手数</div>
                <InputNumber value={numContracts} onChange={(v) => v && setNumContracts(v)} min={1} max={100} step={1} style={{ width: '100%' }} addonAfter="手" />
              </Col>
              <Col xs={12} sm={6}>
                <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>入场本金</div>
                <InputNumber
                  value={entryCapital} onChange={(v) => v && setEntryCapital(v)} min={10000} step={10000} style={{ width: '100%' }}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                  parser={(v) => Number((v || '').replace(/,/g, ''))}
                  addonAfter="元"
                />
              </Col>
              <Col xs={12} sm={6}>
                <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>保证金比例</div>
                <InputNumber value={marginRate} onChange={(v) => v && setMarginRate(v)} min={5} max={50} step={1} style={{ width: '100%' }} addonAfter="%" />
              </Col>
            </Row>

            {position && (
              <>
                {position.total_margin > position.entry_capital && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4, color: '#ff4d4f', fontSize: 13 }}>
                    保证金 {fmtNum(position.total_margin)} 元已超过本金 {fmtNum(position.entry_capital)} 元，请减少持仓手数或增加本金
                  </div>
                )}
                <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                  <Col xs={12} sm={6}>
                    <Statistic title="每手价值" value={position.contract_value} precision={0} suffix="元" valueStyle={{ fontSize: 18 }} />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="每手保证金" value={position.margin_per_contract} precision={0} suffix="元" valueStyle={{ fontSize: 18 }} />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="持仓手数" value={position.num_contracts} suffix="手" valueStyle={{ fontSize: 18, color: '#1677ff' }} />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic
                      title="剩余资金"
                      value={position.remaining_capital}
                      precision={0}
                      suffix="元"
                      valueStyle={{ fontSize: 18, color: position.remaining_capital < 0 ? '#ff4d4f' : undefined }}
                    />
                  </Col>
                  <Col xs={12} sm={8}>
                    <Statistic
                      title="总保证金"
                      value={position.total_margin}
                      precision={0}
                      suffix="元"
                      valueStyle={{ fontSize: 18, color: position.total_margin > position.entry_capital ? '#ff4d4f' : undefined }}
                    />
                  </Col>
                  <Col xs={12} sm={8}>
                    <Statistic title="最低保证金点位" value={position.margin_call_point} precision={0} suffix="点" valueStyle={{ fontSize: 18, color: '#faad14' }} />
                  </Col>
                  <Col xs={12} sm={8}>
                    <Statistic title="爆仓点位" value={position.liquidation_point} precision={0} suffix="点" valueStyle={{ fontSize: 18, color: '#ff4d4f' }} />
                  </Col>
                </Row>
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
