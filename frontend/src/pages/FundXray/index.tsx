import { DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons';
import { Button, message, Radio, Select, Table, Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { get, getAggregatedHoldings, getFundHoldings, getHoldingQuarters, getStockExposure, triggerHoldingsFetch } from '../../services/api';
import type { AggregatedHolding, ClassCategory, ClassModel, Fund, FundClassMap, FundHolding, StockExposure } from '../../types';

const PIE_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8d0',
  '#c4ccd3', '#f9c859', '#61a0a8', '#d48265', '#749f83',
];

const L1_STYLES = [
  { bg: '#FFFBEB', border: '#F59E0B', label: '#92400E' },
  { bg: '#ECFDF5', border: '#10B981', label: '#065F46' },
  { bg: '#EFF6FF', border: '#3B82F6', label: '#1E40AF' },
  { bg: '#FDF2F8', border: '#EC4899', label: '#9D174D' },
];

/* ── Classification types ── */
interface ClassL2 { name: string; funds: Fund[] }
interface ClassGroup { name: string; children: ClassL2[] }
interface ClassTree { groups: ClassGroup[]; uncategorized: Fund[] }

type Selection =
  | { type: 'fund'; fundId: number }
  | { type: 'group'; name: string; fundIds: number[] }
  | null;

/* ── FundClassPanel ── */
function FundClassPanel({ tree, selection, onSelectFund, onSelectGroup }: {
  tree: ClassTree;
  selection: Selection;
  onSelectFund: (id: number) => void;
  onSelectGroup: (name: string, fundIds: number[]) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const allFunds = useMemo(() => {
    const result: Fund[] = [];
    for (const g of tree.groups)
      for (const c of g.children)
        result.push(...c.funds);
    result.push(...tree.uncategorized);
    return result;
  }, [tree]);

  // Check if a group is currently selected
  const isGroupActive = (name: string) => selection?.type === 'group' && selection.name === name;
  const isFundActive = (id: number) => {
    if (!selection) return false;
    if (selection.type === 'fund') return selection.fundId === id;
    if (selection.type === 'group') return selection.fundIds.includes(id);
    return false;
  };

  const renderPill = (f: Fund) => {
    const active = isFundActive(f.id);
    return (
      <span
        key={f.id}
        onClick={(e) => { e.stopPropagation(); onSelectFund(f.id); }}
        title={f.name}
        style={{
          display: 'inline-block', fontSize: 11,
          cursor: 'pointer', padding: '2px 7px', borderRadius: 4, lineHeight: 1.5,
          background: active ? '#6366F120' : '#fff',
          border: active ? '1.5px solid #6366F1' : '1px solid #E5E7EB',
          fontWeight: active ? 600 : 400,
          color: active ? '#4338CA' : '#374151',
          transition: 'all 0.15s',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          maxWidth: '100%',
        }}
      >
        {f.name}
      </span>
    );
  };

  if (!expanded) {
    return (
      <div className="section-card" style={{ padding: '8px 12px', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            onClick={() => { const ids = allFunds.map((f) => f.id); if (ids.length) onSelectGroup('良田模型', ids); }}
            style={{
              fontSize: 12, flexShrink: 0, cursor: 'pointer',
              color: isGroupActive('良田模型') ? '#4338CA' : '#9CA3AF',
              fontWeight: isGroupActive('良田模型') ? 600 : 400,
            }}
          >
            良田模型 <span style={{ fontSize: 10 }}>({allFunds.length})</span>
          </span>
          <div style={{ display: 'flex', gap: 5, alignItems: 'center', overflow: 'hidden', flex: 1 }}>
            {allFunds.slice(0, 8).map(renderPill)}
            {allFunds.length > 8 && <span style={{ fontSize: 11, color: '#9CA3AF' }}>+{allFunds.length - 8}</span>}
          </div>
          <span onClick={() => setExpanded(true)} style={{ fontSize: 12, color: '#6366F1', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
            展开 <DownOutlined style={{ fontSize: 10 }} />
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="section-card" style={{ padding: '8px 12px', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <span
          onClick={() => { const ids = allFunds.map((f) => f.id); if (ids.length) onSelectGroup('良田模型', ids); }}
          style={{
            fontSize: 12, cursor: 'pointer',
            color: isGroupActive('良田模型') ? '#4338CA' : '#9CA3AF',
            fontWeight: isGroupActive('良田模型') ? 600 : 400,
          }}
        >
          良田模型 <span style={{ fontSize: 10 }}>({allFunds.length})</span>
        </span>
        <span style={{ flex: 1 }} />
        <span onClick={() => setExpanded(false)} style={{ fontSize: 12, color: '#6366F1', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2 }}>
          收起 <UpOutlined style={{ fontSize: 10 }} />
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {tree.groups.map((g, gi) => {
          const fundCount = g.children.reduce((s, c) => s + c.funds.length, 0);
          const style = L1_STYLES[gi % L1_STYLES.length];
          const l1FundIds = g.children.flatMap((c) => c.funds.map((f) => f.id));
          const l1Active = isGroupActive(g.name);
          // L2 with funds vs empty
          const activeCats = g.children.filter((c) => c.funds.length > 0);
          const emptyCats = g.children.filter((c) => c.funds.length === 0);
          return (
            <div key={g.name} style={{
              flex: `${Math.max(fundCount, 2)} 1 240px`,
              minWidth: 240,
              background: l1Active ? style.border + '15' : style.bg,
              border: l1Active ? `2px solid ${style.border}` : `1px solid ${style.border}30`,
              borderRadius: 8, padding: '8px 10px',
              transition: 'all 0.15s',
            }}>
              <div
                onClick={() => l1FundIds.length > 0 && onSelectGroup(g.name, l1FundIds)}
                style={{
                  fontSize: 12, fontWeight: 600, color: style.label, marginBottom: 6,
                  cursor: l1FundIds.length > 0 ? 'pointer' : 'default',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                {g.name}
                <span style={{ fontSize: 10, fontWeight: 400, color: style.label + 'AA' }}>({fundCount})</span>
                {emptyCats.length > 0 && (
                  <span style={{ fontSize: 10, fontWeight: 400, color: '#D1D5DB', marginLeft: 4 }}>
                    {emptyCats.map((c) => c.name).join('·')}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {activeCats.map((l2) => {
                  const l2FundIds = l2.funds.map((f) => f.id);
                  const l2Active = isGroupActive(l2.name);
                  return (
                    <div key={l2.name} style={{
                      flex: `${Math.max(l2.funds.length, 1)} 1 110px`,
                      minWidth: 110,
                      background: l2Active ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.7)',
                      borderRadius: 6, padding: '5px 8px',
                      border: l2Active ? '1.5px solid #6366F1' : '1px solid rgba(0,0,0,0.04)',
                      transition: 'all 0.15s',
                    }}>
                      <div
                        onClick={() => onSelectGroup(l2.name, l2FundIds)}
                        style={{
                          fontSize: 11, color: l2Active ? '#4338CA' : '#6B7280',
                          marginBottom: 4, fontWeight: l2Active ? 600 : 500,
                          cursor: 'pointer',
                        }}
                      >
                        {l2.name} <span style={{ fontSize: 10 }}>({l2.funds.length})</span>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                        {l2.funds.map(renderPill)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {tree.uncategorized.length > 0 && (
          <div style={{
            flex: `${Math.max(tree.uncategorized.length, 1)} 1 200px`, minWidth: 200,
            background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 8, padding: '8px 10px',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9CA3AF', marginBottom: 6 }}>未分类</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {tree.uncategorized.map(renderPill)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main component ── */
export default function FundXray() {
  const [tab, setTab] = useState<'exposure' | 'holdings'>('exposure');

  // Stock exposure
  const [exposure, setExposure] = useState<StockExposure[]>([]);
  const [exposureLoading, setExposureLoading] = useState(false);

  // Selection state
  const [selection, setSelection] = useState<Selection>(null);
  const selectedFundId = selection?.type === 'fund' ? selection.fundId : undefined;

  // Holdings browser (single fund)
  const [funds, setFunds] = useState<Fund[]>([]);
  const [quarters, setQuarters] = useState<string[]>([]);
  const [selectedQuarter, setSelectedQuarter] = useState<string | undefined>();
  const [holdings, setHoldings] = useState<FundHolding[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);

  // Aggregated holdings (group)
  const [aggHoldings, setAggHoldings] = useState<AggregatedHolding[]>([]);
  const [aggLoading, setAggLoading] = useState(false);

  // Fund position from meta
  const [fundPosition, setFundPosition] = useState<number | null>(null);

  const [fetching, setFetching] = useState(false);

  // Classification tree
  const [classTree, setClassTree] = useState<ClassTree | null>(null);

  // Load funds list
  useEffect(() => {
    get<Fund[]>('/funds', { is_active: true, page_size: 100 }).then((r) => {
      if (r.success) setFunds(r.data);
    });
  }, []);

  // Load classification tree
  useEffect(() => {
    (async () => {
      const modelsRes = await get<ClassModel[]>('/classification/models');
      if (!modelsRes.success) return;
      const ltModel = modelsRes.data.find((m) => m.name === '良田模型');
      if (!ltModel) return;

      const [treeRes, mapRes, fundsRes] = await Promise.all([
        get<ClassCategory[]>('/classification/categories/tree', { model_id: ltModel.id }),
        get<FundClassMap[]>('/classification/mappings'),
        get<Fund[]>('/funds', { is_active: true, page_size: 100 }),
      ]);
      if (!treeRes.success || !mapRes.success || !fundsRes.success) return;

      const allFunds = fundsRes.data;
      const fundById = new Map(allFunds.map((f) => [f.id, f]));
      const fundCat = new Map<number, number>();
      for (const m of mapRes.data) {
        if (m.model_id === ltModel.id) fundCat.set(m.fund_id, m.category_id);
      }
      const flatCats: ClassCategory[] = [];
      const flatten = (nodes: ClassCategory[]) => { nodes.forEach((n) => { flatCats.push(n); if (n.children) flatten(n.children); }); };
      flatten(treeRes.data);

      const classified = new Set<number>();
      const groups: ClassGroup[] = treeRes.data.map((l1) => {
        const l2s = (l1.children ?? []).map((l2) => {
          const catIds = new Set([l2.id]);
          for (const c of flatCats) if (c.parent_id === l2.id) catIds.add(c.id);
          const l2Funds: Fund[] = [];
          for (const [fid, cid] of fundCat) {
            if (catIds.has(cid)) {
              const fund = fundById.get(fid);
              if (fund) { l2Funds.push(fund); classified.add(fid); }
            }
          }
          return { name: l2.name, funds: l2Funds };
        });
        return { name: l1.name, children: l2s };
      });
      const uncategorized = allFunds.filter((f) => !classified.has(f.id));
      setClassTree({ groups, uncategorized });
    })();
  }, []);

  // Load stock exposure
  const loadExposure = useCallback(async () => {
    setExposureLoading(true);
    const resp = await getStockExposure();
    if (resp.success) setExposure(resp.data);
    setExposureLoading(false);
  }, []);
  useEffect(() => { loadExposure(); }, [loadExposure]);

  // ── Single fund: load quarters ──
  useEffect(() => {
    if (selection?.type !== 'fund') {
      setQuarters([]); setSelectedQuarter(undefined); setHoldings([]);
      return;
    }
    getHoldingQuarters(selection.fundId).then((r) => {
      if (r.success) {
        setQuarters(r.data);
        setSelectedQuarter(r.data[0] || undefined);
      }
    });
  }, [selection]);

  // ── Single fund: load holdings ──
  useEffect(() => {
    if (selection?.type !== 'fund') return;
    setHoldingsLoading(true);
    const params: { fund_id: number; quarter?: string } = { fund_id: selection.fundId };
    if (selectedQuarter) params.quarter = selectedQuarter;
    getFundHoldings(params).then((r) => {
      if (r.success) {
        setHoldings(r.data);
        setFundPosition((r.meta?.fund_position as number) ?? null);
      }
      setHoldingsLoading(false);
    });
  }, [selection, selectedQuarter]);

  // ── Group: load aggregated holdings ──
  useEffect(() => {
    if (selection?.type !== 'group') { setAggHoldings([]); return; }
    setAggLoading(true);
    getAggregatedHoldings(selection.fundIds).then((r) => {
      if (r.success) {
        setAggHoldings(r.data);
        setFundPosition((r.meta?.fund_position as number) ?? null);
      }
      setAggLoading(false);
    });
  }, [selection]);

  // Selection handlers
  const handleSelectFund = useCallback((id: number) => {
    setSelection((prev) => (prev?.type === 'fund' && prev.fundId === id) ? null : { type: 'fund', fundId: id });
  }, []);

  const handleSelectGroup = useCallback((name: string, fundIds: number[]) => {
    setSelection((prev) => (prev?.type === 'group' && prev.name === name) ? null : { type: 'group', name, fundIds });
  }, []);

  const handleSelectFromDropdown = useCallback((v: number | undefined) => {
    if (v === undefined) setSelection(null);
    else setSelection({ type: 'fund', fundId: v });
  }, []);

  const handleFetch = useCallback(async () => {
    setFetching(true);
    const resp = await triggerHoldingsFetch(selectedFundId);
    if (resp.success) {
      message.success(`已获取 ${resp.data.fetched_count} 条持仓数据`);
      loadExposure();
      if (selectedFundId) {
        const qr = await getHoldingQuarters(selectedFundId);
        if (qr.success) {
          setQuarters(qr.data);
          if (qr.data[0]) setSelectedQuarter(qr.data[0]);
        }
      }
    } else {
      message.error('获取持仓数据失败');
    }
    setFetching(false);
  }, [selectedFundId, loadExposure]);

  /* ── Columns ── */
  const exposureColumns = [
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
    { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name' },
    {
      title: '实际敞口(CNY)', dataIndex: 'total_exposure_cny', key: 'total_exposure_cny',
      width: 160, align: 'right' as const,
      sorter: (a: StockExposure, b: StockExposure) => a.total_exposure_cny - b.total_exposure_cny,
      defaultSortOrder: 'descend' as const,
      render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'", fontWeight: 500 }}>¥{v.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>,
    },
    {
      title: '涉及基金', dataIndex: 'funds', key: 'funds',
      render: (fs: StockExposure['funds']) => <span>{fs.map((f) => <Tag key={f.fund_id} style={{ marginBottom: 2 }}>{f.fund_name} ({f.holding_ratio}%)</Tag>)}</span>,
    },
  ];

  const holdingColumns = [
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 80 },
    { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name', width: 90 },
    { title: '占比(%)', dataIndex: 'holding_ratio', key: 'holding_ratio', width: 80, align: 'right' as const,
      render: (v: number | null) => v != null ? `${v.toFixed(2)}%` : '-' },
    { title: '市值(万)', dataIndex: 'holding_value', key: 'holding_value', width: 100, align: 'right' as const,
      render: (v: number | null) => v != null ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-' },
    { title: '持仓金额', dataIndex: 'holding_amount', key: 'holding_amount', width: 110, align: 'right' as const,
      render: (v: number | null) => v != null ? `¥${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-' },
  ];

  const aggColumns = [
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 80 },
    { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name', width: 90 },
    { title: '合计占比(%)', dataIndex: 'total_holding_ratio', key: 'total_holding_ratio', width: 100, align: 'right' as const,
      sorter: (a: AggregatedHolding, b: AggregatedHolding) => a.total_holding_ratio - b.total_holding_ratio,
      render: (v: number) => `${v.toFixed(2)}%` },
    { title: '合计市值(万)', dataIndex: 'total_holding_value', key: 'total_holding_value', width: 110, align: 'right' as const,
      sorter: (a: AggregatedHolding, b: AggregatedHolding) => a.total_holding_value - b.total_holding_value,
      render: (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
    { title: '持仓金额', dataIndex: 'total_holding_amount', key: 'total_holding_amount', width: 120, align: 'right' as const,
      sorter: (a: AggregatedHolding, b: AggregatedHolding) => a.total_holding_amount - b.total_holding_amount,
      defaultSortOrder: 'descend' as const,
      render: (v: number) => `¥${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}` },
    { title: '基金数', dataIndex: 'fund_count', key: 'fund_count', width: 60, align: 'center' as const },
  ];

  /* ── Charts data ── */
  // Active data for charts: either single fund or aggregated
  const chartData = useMemo(() => {
    if (selection?.type === 'fund' && holdings.length > 0) {
      return holdings.map((h) => ({ name: h.stock_name, ratio: h.holding_ratio ?? 0, value: h.holding_value ?? 0, amount: h.holding_amount ?? 0 }));
    }
    if (selection?.type === 'group' && aggHoldings.length > 0) {
      return aggHoldings.map((h) => ({ name: h.stock_name, ratio: h.total_holding_ratio, value: h.total_holding_value, amount: h.total_holding_amount }));
    }
    return [];
  }, [selection, holdings, aggHoldings]);

  const ratioPieData = useMemo(() => {
    if (!chartData.length) return [];
    const top10 = chartData.slice(0, 10);
    const rest = chartData.slice(10);
    const items = top10.map((h) => ({ name: h.name, value: h.ratio }));
    if (rest.length) items.push({ name: `其他(${rest.length}只)`, value: Math.round(rest.reduce((s, h) => s + h.ratio, 0) * 100) / 100 });
    return items;
  }, [chartData]);

  const valuePieData = useMemo(() => {
    if (!chartData.length) return [];
    const top10 = chartData.slice(0, 10);
    const rest = chartData.slice(10);
    const items = top10.map((h) => ({ name: h.name, value: h.value }));
    if (rest.length) items.push({ name: `其他(${rest.length}只)`, value: Math.round(rest.reduce((s, h) => s + h.value, 0) * 100) / 100 });
    return items;
  }, [chartData]);

  const concentrationData = useMemo(() => {
    if (!chartData.length) return [];
    const total = chartData.reduce((s, h) => s + h.ratio, 0);
    const top5 = chartData.slice(0, 5).reduce((s, h) => s + h.ratio, 0);
    const top10 = chartData.slice(0, 10).reduce((s, h) => s + h.ratio, 0);
    return [
      { name: 'Top 5', value: Math.round(top5 * 100) / 100 },
      { name: 'Top 6-10', value: Math.round((top10 - top5) * 100) / 100 },
      { name: '其他', value: Math.round((total - top10) * 100) / 100 },
    ].filter((d) => d.value > 0);
  }, [chartData]);

  const exposurePieData = useMemo(() => {
    if (!exposure.length) return [];
    const top10 = exposure.slice(0, 10);
    const rest = exposure.slice(10);
    const items = top10.map((e) => ({ name: e.stock_name, value: Math.round(e.total_exposure_cny) }));
    if (rest.length) items.push({ name: `其他(${rest.length}只)`, value: Math.round(rest.reduce((s, e) => s + e.total_exposure_cny, 0)) });
    return items;
  }, [exposure]);

  const exposureByFundData = useMemo(() => {
    if (!exposure.length) return [];
    const fundMap: Record<string, number> = {};
    for (const e of exposure) for (const f of e.funds) fundMap[f.fund_name] = (fundMap[f.fund_name] ?? 0) + f.exposure_cny;
    return Object.entries(fundMap).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name, value: Math.round(value) }));
  }, [exposure]);

  // Exposure summary: total portfolio & total exposure
  const exposureSummary = useMemo(() => {
    if (!exposure.length) return { portfolio: 0, exposed: 0 };
    const fundPos: Record<number, number> = {};
    for (const e of exposure) for (const f of e.funds) fundPos[f.fund_id] = f.amount_cny;
    const portfolio = Object.values(fundPos).reduce((s, v) => s + v, 0);
    const exposed = exposure.reduce((s, e) => s + e.total_exposure_cny, 0);
    return { portfolio, exposed };
  }, [exposure]);

  /* ── Chart builders ── */
  function makePieOption(title: string, data: { name: string; value: number }[], fmt?: string) {
    return {
      title: { text: title, left: 'center', top: 4, textStyle: { fontSize: 13, fontWeight: 600 } },
      tooltip: { trigger: 'item', formatter: fmt || '{b}: {c} ({d}%)', confine: true },
      legend: { orient: 'horizontal' as const, bottom: 0, left: 'center', textStyle: { fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
      color: PIE_COLORS,
      series: [{
        type: 'pie', radius: ['35%', '60%'], center: ['50%', '48%'], data,
        label: { formatter: '{b}\n{d}%', fontSize: 10, overflow: 'truncate', width: 60 },
        labelLine: { length: 8, length2: 6 },
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 3 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.12)' } },
      }],
    };
  }

  function makeHBarOption(title: string, data: { name: string; value: number }[]) {
    const sorted = [...data].reverse();
    const barHeight = Math.max(data.length * 32 + 60, 200);
    return {
      _height: barHeight,
      title: { text: title, left: 'center', top: 4, textStyle: { fontSize: 13, fontWeight: 600 } },
      tooltip: { trigger: 'axis' as const, confine: true, formatter: (params: any) => `${params[0].name}<br/>敞口: ¥${Number(params[0].value).toLocaleString()}` },
      grid: { left: 16, right: 60, bottom: 12, top: 36, containLabel: true },
      yAxis: { type: 'category', data: sorted.map((d) => d.name), axisLabel: { fontSize: 11, width: 120, overflow: 'truncate', color: '#374151' }, axisTick: { show: false }, axisLine: { show: false } },
      xAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : `${v}` }, splitLine: { lineStyle: { type: 'dashed' as const, opacity: 0.3 } } },
      series: [{ type: 'bar', data: sorted.map((d) => d.value), itemStyle: { borderRadius: [0, 3, 3, 0], color: { type: 'linear' as const, x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#818CF8' }, { offset: 1, color: '#5470c6' }] } }, barMaxWidth: 24, barMinWidth: 14, label: { show: true, position: 'right', fontSize: 10, color: '#6B7280', formatter: (p: any) => `¥${Number(p.value).toLocaleString()}` } }],
    };
  }

  /* ── Derived display info ── */
  const selectionTitle = useMemo(() => {
    if (!selection) return '';
    if (selection.type === 'fund') return funds.find((f) => f.id === selection.fundId)?.name ?? '基金';
    return selection.name;
  }, [selection, funds]);

  const isGroup = selection?.type === 'group';
  const currentLoading = isGroup ? aggLoading : holdingsLoading;
  const currentDataCount = isGroup ? aggHoldings.length : holdings.length;

  // Stock-level total: sum of holding_amount
  const stockTotal = useMemo(() => {
    if (isGroup) return aggHoldings.reduce((s, h) => s + (h.total_holding_amount ?? 0), 0);
    return holdings.reduce((s, h) => s + (h.holding_amount ?? 0), 0);
  }, [isGroup, holdings, aggHoldings]);

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ margin: 0 }}>基金透视</h1>
          <Radio.Group value={tab} onChange={(e) => setTab(e.target.value)} buttonStyle="solid" size="small">
            <Radio.Button value="exposure">股票敞口</Radio.Button>
            <Radio.Button value="holdings">基金持仓</Radio.Button>
          </Radio.Group>
        </div>
        <Button icon={<ReloadOutlined />} loading={fetching} onClick={handleFetch}>
          {selectedFundId ? '刷新该基金' : '刷新全部'}
        </Button>
      </div>

      {/* ═══ Tab: 股票敞口 ═══ */}
      {tab === 'exposure' && (
        <div style={{ display: 'flex', gap: 16 }}>
          <div className="section-card" style={{ flex: 1, minWidth: 0 }}>
            <div className="section-card-header" style={{ justifyContent: 'space-between' }}>
              <span className="section-card-title">股票敞口明细</span>
              {exposureSummary.portfolio > 0 && (
                <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                  <span style={{ color: '#6B7280' }}>
                    持仓总额 <span style={{ fontWeight: 600, color: '#374151', fontFeatureSettings: "'tnum'" }}>¥{exposureSummary.portfolio.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </span>
                  <span style={{ color: '#6B7280' }}>
                    可透视总额 <span style={{ fontWeight: 600, color: '#374151', fontFeatureSettings: "'tnum'" }}>¥{exposureSummary.exposed.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </span>
                  <span style={{ color: '#9CA3AF' }}>
                    覆盖率 {(exposureSummary.exposed / exposureSummary.portfolio * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
            <div className="section-card-body" style={{ padding: 0 }}>
              <Table dataSource={exposure} columns={exposureColumns} rowKey="stock_code" size="small" loading={exposureLoading}
                pagination={{ pageSize: 20, showSizeChanger: false }}
                expandable={{
                  expandedRowRender: (record) => (
                    <Table dataSource={record.funds} rowKey="fund_id" size="small" pagination={false} columns={[
                      { title: '基金名称', dataIndex: 'fund_name', key: 'fund_name' },
                      { title: '基金持仓(CNY)', dataIndex: 'amount_cny', key: 'amount_cny', align: 'right' as const, render: (v: number) => `¥${v.toLocaleString()}` },
                      { title: '该股占比(%)', dataIndex: 'holding_ratio', key: 'holding_ratio', align: 'right' as const, render: (v: number) => `${v}%` },
                      { title: '实际敞口(CNY)', dataIndex: 'exposure_cny', key: 'exposure_cny', align: 'right' as const, render: (v: number) => `¥${v.toLocaleString()}` },
                    ]} />
                  ),
                }}
              />
            </div>
          </div>
          <div style={{ width: 380, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="section-card"><div className="section-card-body" style={{ padding: 8 }}>
              <ReactECharts option={makePieOption('敞口分布 Top10', exposurePieData, '{b}: ¥{c} ({d}%)')} style={{ height: 300 }} />
            </div></div>
            {exposureByFundData.length > 0 && (() => {
              const opt = makeHBarOption('各基金敞口合计', exposureByFundData);
              return <div className="section-card"><div className="section-card-body" style={{ padding: 8 }}>
                <ReactECharts option={opt} style={{ height: opt._height }} />
              </div></div>;
            })()}
          </div>
        </div>
      )}

      {/* ═══ Tab: 基金持仓 ═══ */}
      {tab === 'holdings' && (
        <>
          {/* Classification quick-pick */}
          {classTree && (
            <FundClassPanel tree={classTree} selection={selection} onSelectFund={handleSelectFund} onSelectGroup={handleSelectGroup} />
          )}

          {/* Selector row */}
          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
            <Select
              placeholder="搜索基金..."
              value={selectedFundId}
              onChange={handleSelectFromDropdown}
              allowClear showSearch optionFilterProp="label" style={{ width: 280 }}
              options={funds.map((f) => ({ value: f.id, label: `${f.code} ${f.name}` }))}
            />
            {selection?.type === 'fund' && quarters.length > 0 && (
              <Select value={selectedQuarter} onChange={(v) => setSelectedQuarter(v)} style={{ width: 140 }}
                options={quarters.map((q) => ({ value: q, label: q }))} />
            )}
            {selection && currentDataCount > 0 && (
              <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                {isGroup && <Tag color="purple" style={{ marginRight: 4 }}>{selectionTitle}</Tag>}
                共 {currentDataCount} 只持仓股票
              </span>
            )}
          </div>

          {!selection ? (
            <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>
              点击上方分类或基金，或搜索选择基金查看持仓分析
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 16 }}>
              {/* Left: table */}
              <div className="section-card" style={{ flex: 1, minWidth: 0 }}>
                <div className="section-card-header" style={{ justifyContent: 'space-between' }}>
                  <span className="section-card-title">{selectionTitle} 持仓明细</span>
                  {fundPosition != null && currentDataCount > 0 && (
                    <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                      <span style={{ color: '#6B7280' }}>
                        基金持仓 <span style={{ fontWeight: 600, color: '#374151', fontFeatureSettings: "'tnum'" }}>¥{fundPosition.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                      </span>
                      <span style={{ color: '#6B7280' }}>
                        股票合计 <span style={{ fontWeight: 600, color: '#374151', fontFeatureSettings: "'tnum'" }}>¥{stockTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                      </span>
                      {fundPosition > 0 && (
                        <span style={{ color: '#9CA3AF' }}>
                          覆盖率 {(stockTotal / fundPosition * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="section-card-body" style={{ padding: 0 }}>
                  {isGroup ? (
                    <Table
                      dataSource={aggHoldings} columns={aggColumns} rowKey="stock_code" size="small"
                      loading={aggLoading} pagination={false} scroll={{ y: 600 }}
                      locale={{ emptyText: '暂无持仓数据' }}
                      expandable={{
                        expandedRowRender: (record) => (
                          <Table dataSource={record.funds} rowKey="fund_id" size="small" pagination={false} columns={[
                            { title: '基金', dataIndex: 'fund_name', key: 'fund_name' },
                            { title: '占比(%)', dataIndex: 'holding_ratio', key: 'holding_ratio', align: 'right' as const, render: (v: number | null) => v != null ? `${v.toFixed(2)}%` : '-' },
                            { title: '市值(万)', dataIndex: 'holding_value', key: 'holding_value', align: 'right' as const, render: (v: number | null) => v != null ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '-' },
                            { title: '持仓金额', dataIndex: 'holding_amount', key: 'holding_amount', align: 'right' as const, render: (v: number | null) => v != null ? `¥${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-' },
                            { title: '季度', dataIndex: 'quarter', key: 'quarter', width: 80 },
                          ]} />
                        ),
                      }}
                    />
                  ) : (
                    <Table
                      dataSource={holdings} columns={holdingColumns} rowKey="id" size="small"
                      loading={holdingsLoading} pagination={false} scroll={{ y: 600 }}
                      locale={{ emptyText: '暂无持仓数据，请点击刷新获取' }}
                    />
                  )}
                </div>
              </div>

              {/* Right: charts */}
              <div style={{ width: 420, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="section-card"><div className="section-card-body" style={{ padding: 8 }}>
                  <ReactECharts option={makePieOption('持仓占比 Top10', ratioPieData, '{b}: {c}% ({d}%)')} style={{ height: 300 }} />
                </div></div>
                <div className="section-card"><div className="section-card-body" style={{ padding: 8 }}>
                  <ReactECharts option={makePieOption('持仓市值 Top10 (万元)', valuePieData, '{b}: {c}万 ({d}%)')} style={{ height: 300 }} />
                </div></div>
                <div className="section-card"><div className="section-card-body" style={{ padding: 8 }}>
                  <ReactECharts option={makePieOption('持仓集中度', concentrationData, '{b}: {c}% ({d}%)')} style={{ height: 260 }} />
                </div></div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
