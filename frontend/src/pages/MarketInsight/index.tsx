import { CloudDownloadOutlined, DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons';
import { Button, Spin, message } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { get, post } from '../../services/api';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface GridStock { code: string; name: string; market_cap: number; industry?: string }
interface GridCell { row: number; col: number; stocks: GridStock[]; indices: string[] }
interface IndexRange { start_cell: number; end_cell: number; stock_count: number }
interface FundMeta { name: string; code: string; stock_count: number }
interface ClassL2 { name: string; funds: FundMeta[] }
interface ClassGroup { name: string; children: ClassL2[] }
interface FundClassification { model_name: string; groups: ClassGroup[]; uncategorized: FundMeta[] }
interface MarketGridData {
  grid_size: number;
  total_market_cap: number;
  cell_value: number;
  stock_count: number;
  snapshot_date: string;
  cells: GridCell[];
  index_ranges: Record<string, IndexRange>;
  fund_ranges?: Record<string, IndexRange>;
  fund_meta?: FundMeta[];
  fund_classification?: FundClassification;
}
interface KlinePoint { date: string; close: number; pe: number | null }

/* ------------------------------------------------------------------ */
/*  Index configuration — 3 rows                                       */
/* ------------------------------------------------------------------ */

interface IndexGroup { label: string; items: { name: string; code: string }[] }
const INDEX_GROUPS: IndexGroup[] = [
  {
    label: '宽基',
    items: [
      { name: '上证50', code: '000016' }, { name: '沪深300', code: '000300' },
      { name: '中证500', code: '000905' }, { name: '中证1000', code: '000852' },
      { name: '中证2000', code: '932000' }, { name: '创业板指', code: '399006' },
      { name: '科创50', code: '000688' },
    ],
  },
  {
    label: '行业',
    items: [
      { name: '中证消费', code: '000932' }, { name: '中证医药', code: '000933' },
      { name: '中证银行', code: '399986' }, { name: '中证新能源', code: '399808' },
      { name: '全指信息', code: '000993' },
    ],
  },
  {
    label: '红利',
    items: [
      { name: '中证红利', code: '000922' }, { name: '上证红利', code: '000015' },
      { name: '深证红利', code: '399324' },
    ],
  },
];

const ALL_STATIC_INDEX_NAMES = INDEX_GROUPS.flatMap((g) => g.items.map((i) => i.name));
const INDEX_NAME_TO_CODE: Record<string, string> = {};
INDEX_GROUPS.forEach((g) => g.items.forEach((i) => { INDEX_NAME_TO_CODE[i.name] = i.code; }));

// Row-based color palette
const ROW_PALETTES: string[][] = [
  ['#EF4444', '#F97316', '#EAB308', '#84CC16', '#22C55E', '#6366F1', '#8B5CF6'], // 宽基 warm→cool
  ['#0EA5E9', '#06B6D4', '#14B8A6', '#10B981', '#059669'],                        // 行业 cyan→green
  ['#F43F5E', '#E11D48', '#BE123C'],                                               // 红利 rose
];
const FUND_PALETTE = ['#A855F7', '#7C3AED', '#6D28D9', '#5B21B6', '#4C1D95', '#C084FC', '#D946EF', '#E879F9', '#818CF8', '#6366F1'];
const INDEX_COLORS: Record<string, string> = {};
INDEX_GROUPS.forEach((g, gi) => {
  g.items.forEach((item, ii) => {
    INDEX_COLORS[item.name] = ROW_PALETTES[gi][ii % ROW_PALETTES[gi].length];
  });
});

function getFundColor(idx: number): string {
  return FUND_PALETTE[idx % FUND_PALETTE.length];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function stockColor(code: string): string {
  let h = 0;
  for (let i = 0; i < code.length; i++) h = (h * 31 + code.charCodeAt(i)) & 0xffffff;
  return `hsl(${h % 360},${45 + (h >> 8) % 25}%,${50 + (h >> 16) % 20}%)`;
}

function formatCap(cap: number): string {
  if (cap >= 1e12) return `${(cap / 1e12).toFixed(1)}万亿`;
  if (cap >= 1e8) return `${(cap / 1e8).toFixed(0)}亿`;
  return `${(cap / 1e4).toFixed(0)}万`;
}

type RangeKey = '1y' | '3y' | '5y' | 'all';
const RANGE_LABELS: { key: RangeKey; label: string }[] = [
  { key: '1y', label: '1年' }, { key: '3y', label: '3年' },
  { key: '5y', label: '5年' }, { key: 'all', label: '全部' },
];

function filterByRange(data: KlinePoint[], range: RangeKey): KlinePoint[] {
  if (range === 'all' || data.length === 0) return data;
  const years = range === '1y' ? 1 : range === '3y' ? 3 : 5;
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - years);
  const cutStr = cutoff.toISOString().slice(0, 10);
  return data.filter((k) => k.date >= cutStr);
}

/* ------------------------------------------------------------------ */
/*  L1 color palette for classification groups                         */
/* ------------------------------------------------------------------ */

const L1_STYLES: { bg: string; border: string; label: string }[] = [
  { bg: '#FFFBEB', border: '#F59E0B', label: '#92400E' },  // 粮食作物 — amber
  { bg: '#ECFDF5', border: '#10B981', label: '#065F46' },  // 经济作物 — emerald
  { bg: '#EFF6FF', border: '#3B82F6', label: '#1E40AF' },  // 水库 — blue
  { bg: '#FDF2F8', border: '#EC4899', label: '#9D174D' },  // fallback
];

/* ------------------------------------------------------------------ */
/*  FundClassTree — expanded fund holdings by 良田模型                   */
/* ------------------------------------------------------------------ */

function FundClassTree({ classification, fundMeta, fundRanges, activeIndex, onIndexClick, onCollapse }: {
  classification?: FundClassification;
  fundMeta: FundMeta[];
  fundRanges?: Record<string, IndexRange>;
  activeIndex: string | null;
  onIndexClick: (name: string) => void;
  onCollapse: () => void;
}) {
  // Compute total fund count per L1 for proportional widths
  const groups = classification?.groups ?? [];
  const uncategorized = classification?.uncategorized ?? [];
  const l1FundCounts = groups.map((g) => g.children.reduce((s, c) => s + c.funds.length, 0));
  const totalClassified = l1FundCounts.reduce((s, n) => s + n, 0) + uncategorized.length;

  const renderPill = (f: FundMeta) => {
    const isActive = activeIndex === f.name;
    const idx = fundMeta.findIndex((fm) => fm.name === f.name);
    const color = getFundColor(idx >= 0 ? idx : 0);
    return (
      <span
        key={f.name}
        onClick={() => onIndexClick(f.name)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 11, whiteSpace: 'nowrap',
          cursor: 'pointer', padding: '2px 7px', borderRadius: 4,
          background: isActive ? color + '25' : '#fff',
          border: isActive ? `1.5px solid ${color}` : '1px solid #E5E7EB',
          transition: 'all 0.15s', lineHeight: 1.4,
        }}
      >
        <span style={{ width: 6, height: 6, borderRadius: 2, background: color, flexShrink: 0 }} />
        <span style={{ fontWeight: isActive ? 600 : 400, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.name}</span>
        <span style={{ color: '#B0B0B0', fontSize: 10 }}>({f.stock_count})</span>
      </span>
    );
  };

  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: '#9CA3AF', width: 32, flexShrink: 0 }}>持仓</span>
        <span style={{ flex: 1 }} />
        <span onClick={onCollapse} style={{ fontSize: 12, color: '#6366F1', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2 }}>
          收起 <UpOutlined style={{ fontSize: 10 }} />
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {groups.map((g, gi) => {
          const fundCount = l1FundCounts[gi];
          const style = L1_STYLES[gi % L1_STYLES.length];
          const activeCats = g.children.filter((c) => c.funds.length > 0);
          const emptyCats = g.children.filter((c) => c.funds.length === 0);
          return (
            <div key={g.name} style={{
              flex: `${Math.max(fundCount, 2)} 1 240px`, minWidth: 240,
              background: style.bg, border: `1px solid ${style.border}30`,
              borderRadius: 8, padding: '8px 10px',
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: style.label, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                {g.name}
                <span style={{ fontSize: 10, fontWeight: 400, color: style.label + 'AA' }}>({fundCount})</span>
                {emptyCats.length > 0 && (
                  <span style={{ fontSize: 10, fontWeight: 400, color: '#D1D5DB', marginLeft: 4 }}>
                    {emptyCats.map((c) => c.name).join('·')}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {activeCats.map((l2) => (
                  <div key={l2.name} style={{
                    flex: `${Math.max(l2.funds.length, 1)} 1 110px`, minWidth: 110,
                    background: 'rgba(255,255,255,0.7)', borderRadius: 6, padding: '5px 8px',
                    border: '1px solid rgba(0,0,0,0.04)',
                  }}>
                    <div style={{ fontSize: 11, color: '#6B7280', marginBottom: 4, fontWeight: 500 }}>{l2.name} <span style={{ fontSize: 10 }}>({l2.funds.length})</span></div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                      {l2.funds.map(renderPill)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {uncategorized.length > 0 && (
          <div style={{
            flex: `${Math.max(uncategorized.length, 1)} 1 200px`, minWidth: 200,
            background: '#F9FAFB', border: '1px solid #E5E7EB',
            borderRadius: 8, padding: '8px 10px',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9CA3AF', marginBottom: 6 }}>未分类</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {uncategorized.map(renderPill)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MarketInsight() {
  const [data, setData] = useState<MarketGridData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [noData, setNoData] = useState(false);
  const [activeIndex, setActiveIndex] = useState<string | null>(null);
  const [fundExpanded, setFundExpanded] = useState(false);
  const [hoveredCell, setHoveredCell] = useState<GridCell | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [klineRaw, setKlineRaw] = useState<KlinePoint[]>([]);
  const [klineLoading, setKlineLoading] = useState(false);
  const [range, setRange] = useState<RangeKey>('1y');
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const klineData = useMemo(() => filterByRange(klineRaw, range), [klineRaw, range]);

  // ---- Data loading ----
  const loadGrid = useCallback(async () => {
    setLoading(true); setNoData(false);
    try {
      const resp = await get<MarketGridData>('/market-insight/grid');
      if (resp.success) setData(resp.data); else setNoData(true);
    } catch { setNoData(true); }
    finally { setLoading(false); }
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await post('/market-insight/refresh');
      message.info('数据刷新已开始，约1分钟后完成');
      const poll = setInterval(async () => {
        const resp = await get<MarketGridData>('/market-insight/grid');
        if (resp.success) { setData(resp.data); setNoData(false); setRefreshing(false); clearInterval(poll); }
      }, 5000);
      setTimeout(() => { clearInterval(poll); setRefreshing(false); }, 120000);
    } catch { message.error('刷新请求失败'); setRefreshing(false); }
  }, []);

  useEffect(() => { loadGrid(); }, [loadGrid]);

  // Is activeIndex a fund (not a market index)?
  const isActiveFund = activeIndex != null && !INDEX_NAME_TO_CODE[activeIndex];

  // ---- Fetch kline when activeIndex changes (only for market indices) ----
  useEffect(() => {
    if (!activeIndex) { setKlineRaw([]); return; }
    const code = INDEX_NAME_TO_CODE[activeIndex];
    if (!code) { setKlineRaw([]); return; }
    setKlineLoading(true);
    get<KlinePoint[]>(`/market-insight/index-kline?code=${code}`)
      .then((resp) => { if (resp.success) setKlineRaw(resp.data ?? []); })
      .finally(() => setKlineLoading(false));
  }, [activeIndex]);

  // ---- Fund names from API data ----
  const fundNames = useMemo(() => {
    if (!data?.fund_meta) return [];
    return data.fund_meta.map((f) => f.name);
  }, [data]);

  const allOverlayNames = useMemo(() => [...ALL_STATIC_INDEX_NAMES, ...fundNames], [fundNames]);

  // ---- Memoized maps ----
  const { stockColorMap, indexStockCodes } = useMemo(() => {
    if (!data) return { stockColorMap: new Map<string, string>(), indexStockCodes: new Map<string, Set<string>>() };
    const scm = new Map<string, string>();
    for (const cell of data.cells)
      for (const s of cell.stocks)
        if (!scm.has(s.code)) scm.set(s.code, stockColor(s.code));
    const isc = new Map<string, Set<string>>();
    for (const name of allOverlayNames) {
      const codes = new Set<string>();
      for (const cell of data.cells)
        if (cell.indices.includes(name))
          for (const s of cell.stocks) codes.add(s.code);
      isc.set(name, codes);
    }
    return { stockColorMap: scm, indexStockCodes: isc };
  }, [data, allOverlayNames]);

  // ---- Company pie: top 20 ----
  const pieData = useMemo(() => {
    if (!data || !activeIndex) return [];
    const codes = indexStockCodes.get(activeIndex);
    if (!codes || codes.size === 0) return [];
    const seen = new Map<string, { name: string; cap: number }>();
    for (const cell of data.cells)
      for (const s of cell.stocks)
        if (codes.has(s.code) && !seen.has(s.code))
          seen.set(s.code, { name: s.name, cap: s.market_cap });
    const sorted = [...seen.values()].sort((a, b) => b.cap - a.cap);
    const top = sorted.slice(0, 20);
    const otherCap = sorted.slice(20).reduce((s, v) => s + v.cap, 0);
    const result = top.map((s) => ({ name: s.name, value: s.cap }));
    if (otherCap > 0) result.push({ name: '其他', value: otherCap });
    return result;
  }, [data, activeIndex, indexStockCodes]);

  // ---- Industry pie: top 10 ----
  const industryPieData = useMemo(() => {
    if (!data || !activeIndex) return [];
    const codes = indexStockCodes.get(activeIndex);
    if (!codes || codes.size === 0) return [];
    const industryMap = new Map<string, number>();
    const seen = new Set<string>();
    for (const cell of data.cells)
      for (const s of cell.stocks)
        if (codes.has(s.code) && !seen.has(s.code)) {
          seen.add(s.code);
          const ind = s.industry || '未分类';
          industryMap.set(ind, (industryMap.get(ind) ?? 0) + s.market_cap);
        }
    const sorted = [...industryMap.entries()].map(([name, cap]) => ({ name, value: cap })).sort((a, b) => b.value - a.value);
    const top = sorted.slice(0, 10);
    const otherCap = sorted.slice(10).reduce((s, v) => s + v.value, 0);
    if (otherCap > 0) top.push({ name: '其他', value: otherCap });
    return top;
  }, [data, activeIndex, indexStockCodes]);

  // ---- Draw grid on canvas ----
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const size = data.grid_size;
    const cellSize = canvas.width / size;
    const activeStockCodes = activeIndex ? indexStockCodes.get(activeIndex) : null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const cell of data.cells) {
      const x = cell.col * cellSize;
      const y = cell.row * cellSize;
      const mainStock = cell.stocks[0];
      const baseColor = mainStock ? (stockColorMap.get(mainStock.code) ?? '#E5E7EB') : '#E5E7EB';
      if (activeStockCodes) {
        const isActive = cell.stocks.some((s) => activeStockCodes.has(s.code));
        if (isActive) {
          ctx.fillStyle = baseColor;
          ctx.fillRect(x, y, cellSize, cellSize);
          ctx.fillStyle = 'rgba(255,255,255,0.35)';
          ctx.fillRect(x, y, cellSize, 1); ctx.fillRect(x, y, 1, cellSize);
          ctx.fillStyle = 'rgba(0,0,0,0.2)';
          ctx.fillRect(x, y + cellSize - 1, cellSize, 1); ctx.fillRect(x + cellSize - 1, y, 1, cellSize);
        } else {
          ctx.fillStyle = 'rgba(200,200,200,0.3)';
          ctx.fillRect(x, y, cellSize, cellSize);
        }
      } else {
        ctx.fillStyle = baseColor;
        ctx.fillRect(x, y, cellSize, cellSize);
        ctx.strokeStyle = 'rgba(255,255,255,0.25)';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x, y, cellSize, cellSize);
      }
    }
  }, [data, activeIndex, stockColorMap, indexStockCodes]);

  // ---- Canvas hover ----
  const handleCanvasMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!data || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const cellSize = rect.width / data.grid_size;
    const col = Math.floor((e.clientX - rect.left) / cellSize);
    const row = Math.floor((e.clientY - rect.top) / cellSize);
    const idx = row * data.grid_size + col;
    if (idx >= 0 && idx < data.cells.length) {
      setHoveredCell(data.cells[idx]);
      setTooltipPos({ x: e.clientX, y: e.clientY });
    } else setHoveredCell(null);
  }, [data]);

  // Fund color map (dynamic)
  const fundColorMap = useMemo(() => {
    const m: Record<string, string> = {};
    (data?.fund_meta ?? []).forEach((f, i) => { m[f.name] = getFundColor(i); });
    return m;
  }, [data]);

  const getColor = useCallback((name: string) => INDEX_COLORS[name] || fundColorMap[name] || '#888', [fundColorMap]);

  const handleIndexClick = (name: string) => setActiveIndex((prev) => (prev === name ? null : name));

  // ---- ECharts options ----
  const hasPE = klineData.some((k) => k.pe !== null);
  const klineOption = useMemo(() => {
    if (klineData.length === 0 || !activeIndex) return null;
    const color = getColor(activeIndex);
    const peColor = '#9333EA';
    return {
      tooltip: {
        trigger: 'axis' as const,
        formatter: (params: any) => {
          let html = params[0]?.axisValue ?? '';
          for (const p of params)
            html += `<br/>${p.marker} ${p.seriesName}: ${p.value != null ? Number(p.value).toFixed(2) : '-'}`;
          return html;
        },
      },
      legend: { data: ['收盘价', ...(hasPE ? ['PE'] : [])], top: 0, right: 0, textStyle: { fontSize: 11 } },
      grid: { top: 30, right: hasPE ? 50 : 16, bottom: 60, left: 56 },
      dataZoom: [
        { type: 'slider' as const, xAxisIndex: 0, bottom: 6, height: 20, borderColor: 'transparent' },
        { type: 'inside' as const, xAxisIndex: 0 },
      ],
      xAxis: { type: 'category' as const, data: klineData.map((k) => k.date), axisLabel: { fontSize: 10 }, boundaryGap: false },
      yAxis: [
        { type: 'value' as const, scale: true, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { type: 'dashed' as const, opacity: 0.3 } } },
        ...(hasPE ? [{ type: 'value' as const, scale: true, axisLabel: { fontSize: 10, color: peColor }, splitLine: { show: false }, name: 'PE', nameTextStyle: { fontSize: 10, color: peColor } }] : []),
      ],
      series: [
        { name: '收盘价', type: 'line' as const, data: klineData.map((k) => k.close), smooth: true, symbol: 'none', lineStyle: { width: 2, color }, areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '40' }, { offset: 1, color: color + '05' }] } } },
        ...(hasPE ? [{ name: 'PE', type: 'line' as const, yAxisIndex: 1, data: klineData.map((k) => k.pe), smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: peColor, type: 'dashed' as const } }] : []),
      ],
    };
  }, [klineData, activeIndex, hasPE, getColor]);

  const makePieOption = (pieItems: { name: string; value: number }[]) => ({
    tooltip: { trigger: 'item' as const, formatter: (p: any) => `${p.name}<br/>${formatCap(p.value)} (${p.percent}%)` },
    series: [{
      type: 'pie' as const, radius: ['30%', '60%'], center: ['50%', '50%'], data: pieItems,
      label: { fontSize: 10, formatter: '{b}\n{d}%' },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
    }],
  });

  // ---- Render ----
  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>大盘洞察</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<CloudDownloadOutlined />} onClick={handleRefresh} loading={refreshing}>
            {refreshing ? '刷新中...' : '重新拉取数据'}
          </Button>
          {data && <Button icon={<ReloadOutlined />} onClick={loadGrid} loading={loading}>刷新</Button>}
        </div>
      </div>

      {loading && !data && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}><Spin size="large" tip="正在加载..." /></div>
      )}
      {noData && !loading && !data && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 80, gap: 16 }}>
          <div style={{ fontSize: 16, color: '#6B7280' }}>暂无大盘数据</div>
          <Button type="primary" icon={<CloudDownloadOutlined />} onClick={handleRefresh} loading={refreshing} size="large">
            {refreshing ? '正在拉取数据...' : '拉取 A 股市值数据'}
          </Button>
          {refreshing && <div style={{ fontSize: 13, color: '#9CA3AF' }}>首次加载约需 1 分钟，请稍候...</div>}
        </div>
      )}

      {data && (
        <>
          {/* Summary stats */}
          <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
            {[
              { label: 'A股总市值', value: formatCap(data.total_market_cap) },
              { label: '上市公司数', value: data.stock_count.toLocaleString() },
              { label: '每格代表', value: formatCap(data.cell_value) },
              { label: '数据日期', value: data.snapshot_date },
            ].map((s) => (
              <div key={s.label} className="section-card" style={{ padding: '12px 20px', flex: '0 0 auto' }}>
                <div style={{ fontSize: 12, color: '#9CA3AF' }}>{s.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFeatureSettings: "'tnum'" }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Index legend: 3 rows + fund row */}
          <div className="section-card" style={{ padding: '10px 16px', marginBottom: 12 }}>
            {INDEX_GROUPS.map((group) => (
              <div key={group.label} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: '#9CA3AF', width: 32, flexShrink: 0 }}>{group.label}</span>
                {group.items.map(({ name }) => {
                  const isActive = activeIndex === name;
                  const color = INDEX_COLORS[name];
                  const range = data.index_ranges[name];
                  return (
                    <span
                      key={name}
                      onClick={() => handleIndexClick(name)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12,
                        cursor: 'pointer', padding: '2px 8px', borderRadius: 5,
                        background: isActive ? color + '20' : 'transparent',
                        border: isActive ? `1.5px solid ${color}` : '1.5px solid transparent',
                        transition: 'all 0.15s',
                      }}
                    >
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                      <span style={{ fontWeight: isActive ? 700 : 400 }}>{name}</span>
                      {range && range.stock_count > 0 && (
                        <span style={{ color: '#B0B0B0', fontSize: 11 }}>({range.stock_count})</span>
                      )}
                    </span>
                  );
                })}
              </div>
            ))}
            {/* Fund holdings row — collapsed / expanded */}
            {data.fund_meta && data.fund_meta.length > 0 && (
              <>
                {/* Collapsed: one row of pills + expand button inline */}
                {!fundExpanded && (
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: '#9CA3AF', width: 32, flexShrink: 0 }}>持仓</span>
                    {data.fund_meta.slice(0, 4).map((f, i) => {
                      const isActive = activeIndex === f.name;
                      const color = getFundColor(i);
                      return (
                        <span key={f.name} onClick={() => handleIndexClick(f.name)} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, whiteSpace: 'nowrap',
                          cursor: 'pointer', padding: '2px 8px', borderRadius: 5,
                          background: isActive ? color + '20' : 'transparent',
                          border: isActive ? `1.5px solid ${color}` : '1.5px solid transparent',
                        }}>
                          <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                          <span style={{ fontWeight: isActive ? 700 : 400 }}>{f.name}</span>
                          <span style={{ color: '#B0B0B0', fontSize: 11 }}>({f.stock_count})</span>
                        </span>
                      );
                    })}
                    <span onClick={() => setFundExpanded(true)} style={{ fontSize: 12, color: '#6366F1', cursor: 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 2 }}>
                      +{data.fund_meta.length - 4} 展开 <DownOutlined style={{ fontSize: 10 }} />
                    </span>
                  </div>
                )}
                {/* Expanded: 良田模型 classification tree */}
                {fundExpanded && (
                  <FundClassTree
                    classification={data.fund_classification}
                    fundMeta={data.fund_meta}
                    fundRanges={data.fund_ranges}
                    activeIndex={activeIndex}
                    onIndexClick={handleIndexClick}
                    onCollapse={() => setFundExpanded(false)}
                  />
                )}
              </>
            )}
            {activeIndex && (
              <span onClick={() => setActiveIndex(null)} style={{ fontSize: 12, color: '#9CA3AF', cursor: 'pointer', textDecoration: 'underline', marginLeft: 40 }}>
                清除筛选
              </span>
            )}
          </div>

          {/* Main: Grid (left) + Charts (right) */}
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            {/* Grid */}
            <div className="section-card" style={{ padding: 8, flex: '0 0 auto' }}>
              <canvas
                ref={canvasRef} width={800} height={800}
                style={{ width: 560, height: 560, cursor: 'crosshair', display: 'block' }}
                onMouseMove={handleCanvasMove}
                onMouseLeave={() => setHoveredCell(null)}
              />
            </div>

            {/* Right panel */}
            {activeIndex && (
              <div style={{ flex: 1, minWidth: 320, display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Kline + PE (only for market indices) */}
                {!isActiveFund && (
                  <div className="section-card" style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{activeIndex} 收盘价 & PE</span>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {RANGE_LABELS.map(({ key, label }) => (
                          <span
                            key={key}
                            onClick={() => setRange(key)}
                            style={{
                              fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
                              background: range === key ? getColor(activeIndex) : '#F3F4F6',
                              color: range === key ? '#fff' : '#6B7280',
                              fontWeight: range === key ? 600 : 400,
                              transition: 'all 0.15s',
                            }}
                          >
                            {label}
                          </span>
                        ))}
                      </div>
                    </div>
                    {klineLoading ? (
                      <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin /></div>
                    ) : klineOption ? (
                      <ReactECharts option={klineOption} style={{ height: 260 }} />
                    ) : (
                      <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无行情数据</div>
                    )}
                  </div>
                )}

                {/* Pie charts side by side */}
                <div style={{ display: 'flex', gap: 16 }}>
                  {/* Industry pie */}
                  <div className="section-card" style={{ padding: '12px 16px', flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{activeIndex} 行业占比（前10）</div>
                    {industryPieData.length > 0 ? (
                      <ReactECharts option={makePieOption(industryPieData)} style={{ height: 300 }} />
                    ) : (
                      <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无行业数据，请重新拉取</div>
                    )}
                  </div>

                  {/* Company pie */}
                  <div className="section-card" style={{ padding: '12px 16px', flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
                      {activeIndex} {isActiveFund ? '持仓股' : '成分股'}市值占比（前20）
                    </div>
                    {pieData.length > 0 ? (
                      <ReactECharts option={makePieOption(pieData)} style={{ height: 300 }} />
                    ) : (
                      <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>暂无数据</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Tooltip */}
          {hoveredCell && (
            <div style={{
              position: 'fixed', left: tooltipPos.x + 12, top: tooltipPos.y - 10,
              background: 'rgba(0,0,0,0.85)', color: '#fff',
              padding: '8px 12px', borderRadius: 6, fontSize: 12,
              lineHeight: 1.6, zIndex: 9999, pointerEvents: 'none', maxWidth: 260,
            }}>
              <div style={{ color: '#9CA3AF', marginBottom: 2 }}>格 ({hoveredCell.row + 1}, {hoveredCell.col + 1})</div>
              {hoveredCell.stocks.map((s) => (
                <div key={s.code}>
                  <span style={{ fontWeight: 600 }}>{s.code}</span>{' '}
                  <span>{s.name}</span>{' '}
                  <span style={{ color: '#FCD34D' }}>{formatCap(s.market_cap)}</span>
                  {s.industry && <span style={{ color: '#9CA3AF', marginLeft: 4 }}>{s.industry}</span>}
                </div>
              ))}
              {hoveredCell.indices.length > 0 && (
                <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {hoveredCell.indices.map((idx) => (
                    <span key={idx} style={{ padding: '1px 6px', borderRadius: 3, background: getColor(idx), fontSize: 10, fontWeight: 500 }}>{idx}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
