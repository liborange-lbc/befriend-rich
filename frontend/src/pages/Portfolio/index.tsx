import { ArrowDownOutlined, ArrowUpOutlined, CalendarOutlined, RollbackOutlined } from '@ant-design/icons';
import { Col, DatePicker, Radio, Row, Table } from 'antd';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';
import PieChart from '../../components/Charts/PieChart';
import TrendChart from '../../components/Charts/TrendChart';
import { get } from '../../services/api';
import type { ClassCategory, ClassModel, PortfolioRecord } from '../../types';

type TrendRange = '3m' | '6m' | '12m' | '3y' | 'all';

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
  const [datePickerOpen, setDatePickerOpen] = useState(false);

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

  // Build pie charts from real-time breakdown
  const pieCharts = useMemo(() => {
    return Object.entries(breakdown).map(([modelName, categories]) => {
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
      return { modelName, title: titlePath, data, drillableNames, path };
    });
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

  // Trend chart data
  const chartTrendData = useMemo(() => trendData.map((d) => ({ date: d.date, total: d.total })), [trendData]);

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
        <div className="stat-card">
          <div className="stat-card-label">总资产 (CNY)</div>
          <div className="stat-card-value">¥{totalCny.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
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
        <div className="stat-card">
          <div className="stat-card-label">较上期变化</div>
          <div className="stat-card-value" style={{ color: change >= 0 ? '#EF4444' : '#22C55E' }}>
            {change >= 0 ? <ArrowUpOutlined style={{ fontSize: 16, marginRight: 4 }} /> : <ArrowDownOutlined style={{ fontSize: 16, marginRight: 4 }} />}
            ¥{Math.abs(change).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className={`stat-card-change ${change >= 0 ? 'up' : 'down'}`}>{changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">持仓数量 / 总收益</div>
          <div className="stat-card-value" style={{ fontSize: 18 }}>{latestRecords.length} 只</div>
          <div style={{ fontSize: 12, marginTop: 4, color: totalProfit >= 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>
            收益 ¥{totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>

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

      <div className="section-card">
        <div className="section-card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span className="section-card-title">资产趋势</span>
          <Radio.Group value={trendRange} onChange={(e) => setTrendRange(e.target.value)} size="small" optionType="button" buttonStyle="solid">
            {RANGE_LABELS.map((r) => <Radio.Button key={r.key} value={r.key}>{r.label}</Radio.Button>)}
          </Radio.Group>
        </div>
        <div className="section-card-body">
          <TrendChart title="总资产趋势" data={chartTrendData} seriesKeys={['total']} />
        </div>
      </div>

      <div className="section-card">
        <div className="section-card-header"><span className="section-card-title">持仓 TOP 5</span></div>
        <div className="section-card-body" style={{ padding: 0 }}>
          <Table dataSource={top5} columns={top5Columns} rowKey="rank" pagination={false} size="small" />
        </div>
      </div>
    </div>
  );
}
