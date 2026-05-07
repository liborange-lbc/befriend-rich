import { ArrowDownOutlined, ArrowUpOutlined, CalendarOutlined, RollbackOutlined } from '@ant-design/icons';
import { Col, DatePicker, Drawer, Radio, Row, Table } from 'antd';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';
import CopilotSection from '../../components/Assistant/CopilotSection';
import PieChart from '../../components/Charts/PieChart';
import TrendChart from '../../components/Charts/TrendChart';
import { get, getFundHoldings } from '../../services/api';
import type { ClassCategory, ClassModel, FundHolding, PortfolioRecord } from '../../types';

type TrendRange = '3m' | '6m' | '12m' | '3y' | 'all';
type TrendDimension = 'total' | 'channel' | string; // string = model name

const RANGE_LABELS: { key: TrendRange; label: string }[] = [
  { key: '3m', label: '3 个月' },
  { key: '6m', label: '6 个月' },
  { key: '12m', label: '1 年' },
  { key: '3y', label: '3 年' },
  { key: 'all', label: '所有' },
];

function subtractRange(d: Dayjs, range: TrendRange): Dayjs {
  switch (range) {
    case '3m': return d.subtract(3, 'month');
    case '6m': return d.subtract(6, 'month');
    case '12m': return d.subtract(12, 'month');
    case '3y': return d.subtract(3, 'year');
    case 'all': return dayjs('1970-01-01');
  }
}

function buildChildrenMap(tree: ClassCategory[]): Map<string, string[]> {
  const map = new Map<string, string[]>();
  const walk = (nodes: ClassCategory[]) => {
    for (const node of nodes) {
      if (node.children && node.children.length > 0) {
        map.set(node.name, node.children.map((c) => c.name));
        walk(node.children);
      }
    }
  };
  walk(tree);
  return map;
}

function buildParentMap(tree: ClassCategory[]): Map<string, string> {
  const map = new Map<string, string>();
  const walk = (nodes: ClassCategory[], parent: string | null) => {
    for (const node of nodes) {
      if (parent) map.set(node.name, parent);
      if (node.children?.length) walk(node.children, node.name);
    }
  };
  walk(tree, null);
  return map;
}

function hasMultiLevel(tree: ClassCategory[]): boolean {
  return tree.some((n) => n.children && n.children.length > 0);
}

function aggregateToLevel(
  breakdown: Record<string, number>,
  tree: ClassCategory[],
  drillPath: string[],
): { name: string; value: number }[] {
  if (!hasMultiLevel(tree)) {
    return Object.entries(breakdown)
      .filter(([, v]) => v > 0)
      .map(([name, value]) => ({ name, value: Math.round(value) }));
  }

  const childrenMap = buildChildrenMap(tree);
  const parentMap = buildParentMap(tree);

  const getAllLeaves = (name: string): string[] => {
    const ch = childrenMap.get(name);
    if (!ch || ch.length === 0) return [name];
    return ch.flatMap((c) => getAllLeaves(c));
  };

  if (drillPath.length === 0) {
    const topNames = tree.map((n) => n.name);
    return topNames
      .map((topName) => {
        const leaves = getAllLeaves(topName);
        const total = leaves.reduce((s, l) => s + (breakdown[l] || 0), 0);
        return { name: topName, value: Math.round(total) };
      })
      .filter((d) => d.value > 0);
  }

  const current = drillPath[drillPath.length - 1];
  const children = childrenMap.get(current) || [];
  if (children.length === 0) {
    const val = breakdown[current] || 0;
    return val > 0 ? [{ name: current, value: Math.round(val) }] : [];
  }

  return children
    .map((childName) => {
      const leaves = getAllLeaves(childName);
      const total = leaves.reduce((s, l) => s + (breakdown[l] || 0), 0);
      return { name: childName, value: Math.round(total) };
    })
    .filter((d) => d.value > 0);
}

export default function Portfolio() {
  const [recordDates, setRecordDates] = useState<Set<string>>(new Set());
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [latestRecords, setLatestRecords] = useState<PortfolioRecord[]>([]);
  const [top5, setTop5] = useState<{ rank: number; fund_name: string; amount_cny: number; percentage: number; profit: number }[]>([]);
  const [latestDate, setLatestDate] = useState<string>('');
  const [trendRange, setTrendRange] = useState<TrendRange>('6m');
  const [trendDimension, setTrendDimension] = useState<TrendDimension>('total');
  const [dimensionTrendData, setDimensionTrendData] = useState<Record<string, string | number>[]>([]);
  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [holdingsDrawerOpen, setHoldingsDrawerOpen] = useState(false);
  const [holdingsData, setHoldingsData] = useState<FundHolding[]>([]);
  const [holdingsFundName, setHoldingsFundName] = useState('');

  // Real-time breakdown (no snapshots)
  const [breakdown, setBreakdown] = useState<Record<string, Record<string, number>>>({});
  // Real-time trend data
  const [trendData, setTrendData] = useState<{ date: string; total: number }[]>([]);

  // Classification tree state
  const [categoryTrees, setCategoryTrees] = useState<Record<string, ClassCategory[]>>({});
  const [drillPaths, setDrillPaths] = useState<Record<string, string[]>>({});

  const loadRecordDates = useCallback(async () => {
    const r = await get<string[]>('/portfolio/records/dates');
    if (r.success) {
      setRecordDates(new Set(r.data));
      if (r.data.length > 0 && !selectedDate) {
        setSelectedDate(dayjs(r.data[r.data.length - 1]));
      }
    }
  }, []);

  const loadCategoryTrees = useCallback(async () => {
    const modelsResp = await get<ClassModel[]>('/classification/models');
    if (!modelsResp.success) return;
    const trees: Record<string, ClassCategory[]> = {};
    await Promise.all(
      modelsResp.data.map(async (model) => {
        const treeResp = await get<ClassCategory[]>('/classification/categories/tree', { model_id: model.id });
        if (treeResp.success) trees[model.name] = treeResp.data;
      }),
    );
    setCategoryTrees(trees);
  }, []);

  // Load data for selected date (real-time, no snapshots)
  const loadDateData = useCallback(async (dateStr: string) => {
    const [recordsResp, top5Resp, breakdownResp] = await Promise.all([
      get<PortfolioRecord[]>('/portfolio/records/latest', { target_date: dateStr }),
      get<typeof top5>('/portfolio/top5', { target_date: dateStr }),
      get<Record<string, Record<string, number>>>('/portfolio/breakdown', { target_date: dateStr }),
    ]);
    if (recordsResp.success) {
      setLatestRecords(recordsResp.data);
      setLatestDate((recordsResp.meta as { latest_date?: string })?.latest_date || dateStr);
    }
    if (top5Resp.success) setTop5(top5Resp.data);
    if (breakdownResp.success) setBreakdown(breakdownResp.data);
  }, []);

  // Load trend data based on range + selected date (real-time)
  const loadTrend = useCallback(async (endDate: Dayjs, range: TrendRange) => {
    const startDate = subtractRange(endDate, range);
    const params: Record<string, string> = { end_date: endDate.format('YYYY-MM-DD') };
    if (range !== 'all') params.start_date = startDate.format('YYYY-MM-DD');
    const resp = await get<{ date: string; total: number }[]>('/portfolio/trend', params);
    if (resp.success) setTrendData(resp.data);
  }, []);

  const loadDimensionTrend = useCallback(async (endDate: Dayjs, range: TrendRange, dim: TrendDimension) => {
    if (dim === 'total') return;
    const startDate = subtractRange(endDate, range);
    const params: Record<string, string> = { dimension: dim, end_date: endDate.format('YYYY-MM-DD') };
    if (range !== 'all') params.start_date = startDate.format('YYYY-MM-DD');
    const resp = await get<Record<string, string | number>[]>('/portfolio/trend-by-dimension', params);
    if (resp.success) setDimensionTrendData(resp.data);
  }, []);

  useEffect(() => {
    loadRecordDates();
    loadCategoryTrees();
  }, [loadRecordDates, loadCategoryTrees]);

  useEffect(() => {
    if (selectedDate) {
      loadDateData(selectedDate.format('YYYY-MM-DD'));
      loadTrend(selectedDate, trendRange);
    }
  }, [selectedDate, loadDateData, loadTrend, trendRange]);

  useEffect(() => {
    if (selectedDate && trendDimension !== 'total') {
      loadDimensionTrend(selectedDate, trendRange, trendDimension);
    }
  }, [selectedDate, trendRange, trendDimension, loadDimensionTrend]);

  // Compute totals from records (real-time)
  const totalCny = useMemo(() => latestRecords.reduce((s, r) => s + r.amount_cny, 0), [latestRecords]);
  const totalProfit = useMemo(() => latestRecords.reduce((s, r) => s + (r.profit || 0), 0), [latestRecords]);

  // Change vs previous period from trend data
  const { change, changePct } = useMemo(() => {
    if (trendData.length < 2) return { change: 0, changePct: 0 };
    const currentIdx = trendData.findIndex((d) => d.date === latestDate);
    if (currentIdx <= 0) return { change: 0, changePct: 0 };
    const prevTotal = trendData[currentIdx - 1].total;
    const ch = totalCny - prevTotal;
    return { change: ch, changePct: prevTotal > 0 ? (ch / prevTotal) * 100 : 0 };
  }, [trendData, totalCny, latestDate]);

  // Build pie charts from real-time breakdown (channel first, then models)
  const pieCharts = useMemo(() => {
    const charts: { modelName: string; title: string; data: { name: string; value: number }[]; drillableNames: Set<string>; path: string[] }[] = [];

    // Channel pie chart
    const channelData = breakdown['__channel__'];
    if (channelData) {
      charts.push({
        modelName: '__channel__',
        title: '渠道',
        data: Object.entries(channelData)
          .filter(([, v]) => v > 0)
          .map(([name, value]) => ({ name, value: Math.round(value) })),
        drillableNames: new Set(),
        path: [],
      });
    }

    // Model pie charts
    for (const [modelName, categories] of Object.entries(breakdown)) {
      if (modelName === '__channel__') continue;
      const tree = categoryTrees[modelName] || [];
      const path = drillPaths[modelName] || [];
      const data = aggregateToLevel(categories, tree, path);
      const canDrill = hasMultiLevel(tree);
      const childrenMap = buildChildrenMap(tree);
      const drillableNames = new Set<string>();
      if (canDrill) {
        for (const item of data) {
          if (childrenMap.has(item.name)) drillableNames.add(item.name);
        }
      }
      const titlePath = path.length > 0 ? `${modelName} > ${path.join(' > ')}` : modelName;
      charts.push({ modelName, title: titlePath, data, drillableNames, path });
    }

    return charts;
  }, [breakdown, categoryTrees, drillPaths]);

  const handlePieDrill = useCallback((modelName: string, categoryName: string) => {
    setDrillPaths((prev) => ({ ...prev, [modelName]: [...(prev[modelName] || []), categoryName] }));
  }, []);

  const handlePieBack = useCallback((modelName: string) => {
    setDrillPaths((prev) => {
      const p = prev[modelName] || [];
      return p.length === 0 ? prev : { ...prev, [modelName]: p.slice(0, -1) };
    });
  }, []);

  // Trend chart data + dimension series keys
  const chartTrendData = useMemo(() => {
    if (trendDimension === 'total') {
      return trendData.map((d) => ({ date: d.date, total: d.total }));
    }
    return dimensionTrendData;
  }, [trendData, dimensionTrendData, trendDimension]);

  const trendSeriesKeys = useMemo(() => {
    if (trendDimension === 'total') return ['total'];
    if (dimensionTrendData.length === 0) return [];
    const keys = new Set<string>();
    for (const row of dimensionTrendData) {
      for (const k of Object.keys(row)) {
        if (k !== 'date') keys.add(k);
      }
    }
    return Array.from(keys).sort();
  }, [trendDimension, dimensionTrendData]);

  // Available dimension options (total + channel + model names)
  const dimensionOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [
      { value: 'total', label: '总计' },
      { value: 'channel', label: '渠道' },
    ];
    for (const modelName of Object.keys(breakdown)) {
      if (modelName === '__channel__') continue;
      opts.push({ value: modelName, label: modelName });
    }
    return opts;
  }, [breakdown]);

  const handleFundClick = useCallback(async (record: PortfolioRecord) => {
    setHoldingsFundName(record.fund_name);
    setHoldingsDrawerOpen(true);
    const resp = await getFundHoldings({ fund_id: record.fund_id });
    if (resp.success) setHoldingsData(resp.data);
  }, []);

  const dateCellRender = (current: Dayjs) => {
    if (recordDates.has(current.format('YYYY-MM-DD'))) {
      return (
        <div style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', bottom: -2, left: '50%', transform: 'translateX(-50%)', width: 5, height: 5, borderRadius: '50%', background: '#22C55E' }} />
        </div>
      );
    }
    return null;
  };

  const handleDateChange = (date: Dayjs | null) => {
    if (date) setSelectedDate(date);
    setDatePickerOpen(false);
  };

  const top5Columns = [
    { title: '排名', dataIndex: 'rank', key: 'rank', width: 60,
      render: (v: number) => <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 22, height: 22, borderRadius: '50%',
        background: v <= 3 ? '#FDF4FF' : '#F3F4F6', color: v <= 3 ? '#D946EF' : '#9CA3AF', fontSize: 12, fontWeight: 600 }}>{v}</span> },
    { title: '基金', dataIndex: 'fund_name', key: 'fund_name' },
    { title: '金额 (CNY)', dataIndex: 'amount_cny', key: 'amount_cny',
      render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{v?.toLocaleString()}</span> },
    { title: '占比', dataIndex: 'percentage', key: 'percentage',
      render: (v: number) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, maxWidth: 80, height: 4, borderRadius: 2, background: '#F3F4F6' }}>
            <div style={{ width: `${Math.min(v, 100)}%`, height: '100%', borderRadius: 2, background: '#D946EF' }} />
          </div>
          <span style={{ fontSize: 12, color: '#6B7280' }}>{v}%</span>
        </div>
      ),
    },
    { title: '收益', dataIndex: 'profit', key: 'profit',
      render: (v: number) => v ? <span style={{ color: v >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>¥{v?.toLocaleString()}</span> : <span style={{ color: '#D1D5DB' }}>-</span> },
  ];

  return (
    <div>
      <div style={{ marginBottom: 20 }}><h1>资金大盘</h1></div>

      <div className="stat-cards" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <CopilotSection sectionName="总资产" contextData={{ totalCny, latestDate }}>
          <div className="stat-card">
            <div className="stat-card-label">总资产 (CNY)</div>
            <div className="stat-card-value" style={{ cursor: 'pointer' }} onClick={() => setDetailDrawerOpen(true)} title="点击查看资产明细">¥{totalCny.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            <div style={{ fontSize: 12, marginTop: 4, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, color: '#8B5CF6', borderBottom: '1px dashed #D8B4FE', paddingBottom: 1 }} onClick={() => setDatePickerOpen(true)}>
              <CalendarOutlined />
              <span style={{ color: '#9CA3AF' }}>查看日期:</span> <span style={{ fontWeight: 600 }}>{latestDate || '无'}</span>
              <DatePicker
                open={datePickerOpen}
                value={selectedDate}
                onChange={handleDateChange}
                onOpenChange={setDatePickerOpen}
                cellRender={(current, info) => {
                  if (info.type !== 'date') return info.originNode;
                  const dateNode = current as Dayjs;
                  return (<div className="ant-picker-cell-inner">{dateNode.date()}{dateCellRender(dateNode)}</div>);
                }}
                style={{ position: 'absolute', opacity: 0, width: 0, height: 0, overflow: 'hidden', pointerEvents: 'none' }}
                allowClear={false}
              />
            </div>
          </div>
        </CopilotSection>
        <CopilotSection sectionName="较上期变化" contextData={{ change, changePct }}>
          <div className="stat-card">
            <div className="stat-card-label">较上期变化</div>
            <div className="stat-card-value" style={{ color: change >= 0 ? '#EF4444' : '#22C55E' }}>
              {change >= 0 ? <ArrowUpOutlined style={{ fontSize: 16, marginRight: 4 }} /> : <ArrowDownOutlined style={{ fontSize: 16, marginRight: 4 }} />}
              ¥{Math.abs(change).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div className={`stat-card-change ${change >= 0 ? 'up' : 'down'}`}>{changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%</div>
          </div>
        </CopilotSection>
        <CopilotSection sectionName="持仓数量与总收益" contextData={{ count: latestRecords.length, totalProfit }}>
          <div className="stat-card">
            <div className="stat-card-label">持仓数量 / 总收益</div>
            <div className="stat-card-value" style={{ fontSize: 18 }}>{latestRecords.length} 只</div>
            <div style={{ fontSize: 12, marginTop: 4, color: totalProfit >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>
              收益 ¥{totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
        </CopilotSection>
      </div>

      <CopilotSection sectionName="模型配比" contextData={pieCharts.map((c) => ({ model: c.modelName, data: c.data }))}>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">模型配比</span></div>
          <div className="section-card-body" style={{ overflow: 'visible' }}>
            <Row gutter={16}>
              {pieCharts.map((c) => (
                <Col span={Math.max(6, Math.floor(24 / pieCharts.length))} key={c.modelName} style={{ overflow: 'visible' }}>
                  {c.path.length > 0 && (
                    <div style={{ cursor: 'pointer', fontSize: 12, color: '#6B7280', marginBottom: 4, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      onClick={() => handlePieBack(c.modelName)}>
                      <RollbackOutlined /> 返回上级
                    </div>
                  )}
                  <PieChart
                    title={c.title}
                    data={c.data}
                    onSectorClick={c.drillableNames.size > 0
                      ? (name: string) => { if (c.drillableNames.has(name)) handlePieDrill(c.modelName, name); }
                      : undefined}
                  />
                </Col>
              ))}
              {pieCharts.length === 0 && <Col span={24}><div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>暂无分类数据</div></Col>}
            </Row>
          </div>
        </div>
      </CopilotSection>

      <CopilotSection sectionName="资产趋势" contextData={{ range: trendRange, dimension: trendDimension, dataPoints: trendData.length }}>
        <div className="section-card">
          <div className="section-card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span className="section-card-title">资产趋势</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Radio.Group value={trendDimension} onChange={(e) => setTrendDimension(e.target.value)} size="small" optionType="button">
                {dimensionOptions.map((o) => <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>)}
              </Radio.Group>
              <Radio.Group value={trendRange} onChange={(e) => setTrendRange(e.target.value)} size="small" optionType="button" buttonStyle="solid">
                {RANGE_LABELS.map((r) => <Radio.Button key={r.key} value={r.key}>{r.label}</Radio.Button>)}
              </Radio.Group>
            </div>
          </div>
          <div className="section-card-body">
            <TrendChart
              title={trendDimension === 'total' ? '总资产趋势' : `趋势 — ${dimensionOptions.find((o) => o.value === trendDimension)?.label || trendDimension}`}
              data={chartTrendData}
              seriesKeys={trendSeriesKeys}
            />
          </div>
        </div>
      </CopilotSection>

      <CopilotSection sectionName="持仓 TOP 5" contextData={top5}>
        <div className="section-card">
          <div className="section-card-header"><span className="section-card-title">持仓 TOP 5</span></div>
          <div className="section-card-body" style={{ padding: 0 }}>
            <Table dataSource={top5} columns={top5Columns} rowKey="rank" pagination={false} size="small" />
          </div>
        </div>
      </CopilotSection>

      {/* Asset detail drawer */}
      <Drawer
        title={`资产明细 — ${latestDate || ''}`}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
        width={720}
      >
        <Table
          dataSource={[...latestRecords].sort((a, b) => b.amount_cny - a.amount_cny)}
          rowKey="id"
          size="small"
          pagination={false}
          summary={() => (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={3}><span style={{ fontWeight: 600 }}>合计</span></Table.Summary.Cell>
                <Table.Summary.Cell index={3} align="right">
                  <span style={{ fontWeight: 600, fontFeatureSettings: "'tnum'" }}>
                    ¥{totalCny.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right">
                  <span style={{ fontWeight: 600, fontFeatureSettings: "'tnum'", color: totalProfit >= 0 ? '#EF4444' : '#22C55E' }}>
                    {totalProfit >= 0 ? '+' : ''}{totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} />
              </Table.Summary.Row>
            </Table.Summary>
          )}
          columns={[
            { title: '渠道', dataIndex: 'channel', key: 'channel', width: 80 },
            { title: '基金代码', dataIndex: 'fund_code', key: 'fund_code', width: 90 },
            { title: '基金名称', dataIndex: 'fund_name', key: 'fund_name', ellipsis: true,
              render: (v: string, record: PortfolioRecord) => (
                <a style={{ cursor: 'pointer' }} onClick={() => handleFundClick(record)}>{v}</a>
              ),
            },
            {
              title: '持仓金额(CNY)', dataIndex: 'amount_cny', key: 'amount_cny', width: 150, align: 'right' as const,
              render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{v.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>,
            },
            {
              title: '收益', dataIndex: 'profit', key: 'profit', width: 120, align: 'right' as const,
              render: (v: number | null) => {
                const val = v ?? 0;
                return (
                  <span style={{ color: val >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500, fontFeatureSettings: "'tnum'" }}>
                    {val >= 0 ? '+' : ''}{val.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                );
              },
            },
            {
              title: '占比', key: 'pct', width: 80, align: 'right' as const,
              render: (_: unknown, record: PortfolioRecord) => (
                <span style={{ fontFeatureSettings: "'tnum'", color: '#9CA3AF' }}>
                  {totalCny > 0 ? ((record.amount_cny / totalCny) * 100).toFixed(1) : '0.0'}%
                </span>
              ),
            },
          ]}
        />
      </Drawer>

      {/* Fund holdings drawer (nested) */}
      <Drawer
        title={`成分股 — ${holdingsFundName}`}
        open={holdingsDrawerOpen}
        onClose={() => { setHoldingsDrawerOpen(false); setHoldingsData([]); }}
        width={600}
      >
        {holdingsData.length > 0 && (
          <div style={{ marginBottom: 12, fontSize: 12, color: '#9CA3AF' }}>
            披露期: {holdingsData[0].quarter} ({holdingsData[0].disclosure_date})
          </div>
        )}
        <Table
          dataSource={holdingsData}
          rowKey="id"
          size="small"
          pagination={false}
          columns={[
            { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
            { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name' },
            { title: '占净值比(%)', dataIndex: 'holding_ratio', key: 'holding_ratio', width: 110, align: 'right' as const,
              render: (v: number | null) => v != null ? `${v.toFixed(2)}%` : '-',
            },
            { title: '持仓市值(万元)', dataIndex: 'holding_value', key: 'holding_value', width: 130, align: 'right' as const,
              render: (v: number | null) => v != null ? v.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '-',
            },
          ]}
        />
      </Drawer>
    </div>
  );
}
