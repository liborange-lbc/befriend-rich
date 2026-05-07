import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Row, Statistic, Table, Tag, Spin, Tabs, Input, message, InputNumber, Select, Descriptions } from 'antd';
import {
  UserOutlined,
  FolderOutlined,
  StockOutlined,
  AppstoreOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type {
  GuruInfo,
  GuruDetailInfo,
  GuruHoldingItem,
  GuruTradeItem,
  GuruStockItem,
  GuruOverviewStats,
  GuruSectorStat,
} from '../../types';
import {
  getGurus,
  getGuruDetail,
  getGuruHoldings,
  getGuruTrades,
  getGuruSectors,
  getGuruStocks,
  getGuruStockDetail,
  getGuruStockGurus,
  getGuruOverview,
  getGuruTopStocks,
  getGuruSectorStats,
  refreshGuruHoldings,
} from '../../services/api';

type View =
  | { type: 'home' }
  | { type: 'guru-list'; category?: string }
  | { type: 'guru-detail'; slug: string }
  | { type: 'stock-list' }
  | { type: 'stock-detail'; code: string }
  | { type: 'screener' };

const categoryConfig: Record<string, { label: string; color: string }> = {
  china_fund: { label: '中国公募基金', color: 'blue' },
  asia: { label: '亚洲大师', color: 'green' },
  north_america: { label: '北美大师', color: 'orange' },
};

const categoryLabels: Record<string, string> = {
  china_fund: '中国公募',
  asia: '亚洲大师',
  north_america: '北美大师',
};

const categoryColors: Record<string, string> = {
  china_fund: 'blue',
  asia: 'green',
  north_america: 'orange',
};

const viewTabItems = [
  { key: 'home', label: '总览' },
  { key: 'guru-list', label: '大师列表' },
  { key: 'stock-list', label: '股票列表' },
  { key: 'screener', label: '选股器' },
];

function buildPieOption(data: { name: string; value: number }[]) {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data,
      },
    ],
  };
}

// ── Home View ──

function HomeView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [overview, setOverview] = useState<GuruOverviewStats | null>(null);
  const [sectors, setSectors] = useState<GuruSectorStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getGuruOverview(), getGuruSectorStats()])
      .then(([ov, sec]) => {
        setOverview(ov.data);
        setSectors(sec.data ?? []);
      })
      .catch(() => message.error('加载数据失败'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const topStockColumns = [
    { title: '排名', render: (_: unknown, __: unknown, i: number) => i + 1, width: 60 },
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '公司名称', dataIndex: 'name', key: 'name' },
    { title: '市场', dataIndex: 'market', key: 'market', render: (v: string) => <Tag>{v}</Tag> },
    { title: '持有大师数', dataIndex: 'guru_count', key: 'guru_count', sorter: (a: GuruStockItem, b: GuruStockItem) => a.guru_count - b.guru_count },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}><Card><Statistic title="大师总数" value={overview?.total_gurus ?? 0} prefix={<UserOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="持仓记录" value={overview?.total_holdings ?? 0} prefix={<FolderOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="覆盖股票" value={overview?.total_stocks ?? 0} prefix={<StockOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="覆盖行业" value={sectors.length} prefix={<AppstoreOutlined />} /></Card></Col>
      </Row>

      <Card title="被最多大师持有的股票 Top 10" style={{ marginBottom: 24 }}>
        <Table
          dataSource={overview?.top_stocks ?? []}
          columns={topStockColumns}
          rowKey="id"
          pagination={false}
          size="middle"
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => onNavigate({ type: 'stock-detail', code: record.code! }),
          })}
        />
      </Card>

      <Row gutter={16}>
        {Object.entries(categoryConfig).map(([key, cat]) => (
          <Col span={8} key={key}>
            <Card hoverable onClick={() => onNavigate({ type: 'guru-list', category: key })} style={{ textAlign: 'center' }}>
              <Tag color={cat.color} style={{ fontSize: 16, padding: '4px 12px', marginBottom: 12 }}>{cat.label}</Tag>
              <p style={{ color: '#666' }}>点击查看该分类大师</p>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

// ── Guru List View ──

function GuruListView({ initialCategory, onNavigate }: { initialCategory?: string; onNavigate: (v: View) => void }) {
  const [category, setCategory] = useState(initialCategory ?? '');
  const [gurus, setGurus] = useState<GuruInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getGurus(category || undefined)
      .then((res) => setGurus(res.data?.gurus ?? []))
      .catch(() => message.error('加载大师列表失败'))
      .finally(() => setLoading(false));
  }, [category]);

  const tabItems = [
    { key: '', label: '全部' },
    { key: 'china_fund', label: '中国公募' },
    { key: 'asia', label: '亚洲大师' },
    { key: 'north_america', label: '北美大师' },
  ];

  return (
    <div>
      <Tabs activeKey={category} items={tabItems} onChange={setCategory} style={{ marginBottom: 16 }} />
      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : (
        <Table
          dataSource={gurus}
          rowKey="id"
          size="small"
          pagination={false}
          onRow={(record) => ({ style: { cursor: 'pointer' }, onClick: () => onNavigate({ type: 'guru-detail', slug: record.slug }) })}
          columns={[
            { title: '大师名称', dataIndex: 'name', key: 'name', width: 200 },
            { title: '英文名', dataIndex: 'name_en', key: 'name_en', width: 260, render: (v: string | null) => v ?? '-' },
            { title: '分类', dataIndex: 'category', key: 'category', width: 120, render: (v: string) => v ? <Tag color={categoryColors[v]}>{categoryLabels[v] ?? v}</Tag> : '-' },
            { title: '持仓数', dataIndex: 'num_holdings', key: 'num_holdings', width: 90, sorter: (a: GuruInfo, b: GuruInfo) => a.num_holdings - b.num_holdings },
            { title: '交易数', dataIndex: 'num_trades', key: 'num_trades', width: 90, sorter: (a: GuruInfo, b: GuruInfo) => a.num_trades - b.num_trades },
          ]}
        />
      )}
    </div>
  );
}

// ── Guru Detail View ──

function GuruDetailView({ slug, onNavigate }: { slug: string; onNavigate: (v: View) => void }) {
  const [guru, setGuru] = useState<GuruDetailInfo | null>(null);
  const [holdings, setHoldings] = useState<GuruHoldingItem[]>([]);
  const [trades, setTrades] = useState<GuruTradeItem[]>([]);
  const [sectors, setSectors] = useState<GuruSectorStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [holdingSearch, setHoldingSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([getGuruDetail(slug), getGuruHoldings(slug), getGuruTrades(slug), getGuruSectors(slug)])
      .then(([g, h, t, s]) => {
        setGuru(g.data);
        setHoldings(h.data ?? []);
        setTrades(t.data ?? []);
        setSectors(s.data ?? []);
      })
      .catch(() => message.error('加载大师详情失败'))
      .finally(() => setLoading(false));
  }, [slug]);

  const filteredHoldings = useMemo(() => {
    if (!holdingSearch.trim()) return holdings;
    const q = holdingSearch.toLowerCase();
    return holdings.filter(
      (h) => (h.stock_code ?? '').toLowerCase().includes(q) || (h.stock_name ?? '').toLowerCase().includes(q)
    );
  }, [holdings, holdingSearch]);

  const sectorPieOption = useMemo(() => {
    if (sectors.length > 0) {
      return buildPieOption(sectors.map((s) => ({ name: s.sector, value: s.count })));
    }
    const sectorMap: Record<string, number> = {};
    for (const h of holdings) {
      const s = h.sector || '未知';
      sectorMap[s] = (sectorMap[s] || 0) + 1;
    }
    return buildPieOption(
      Object.entries(sectorMap).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
    );
  }, [sectors, holdings]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!guru) return <div>未找到该大师</div>;

  const holdingColumns = [
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', sorter: (a: GuruHoldingItem, b: GuruHoldingItem) => (a.stock_code ?? '').localeCompare(b.stock_code ?? '') },
    { title: '公司名称', dataIndex: 'stock_name', key: 'stock_name' },
    { title: '仓位变动', dataIndex: 'position_change', key: 'position_change' },
    { title: '交易影响率', dataIndex: 'trade_impact_pct', key: 'trade_impact_pct' },
    { title: '持股数', dataIndex: 'shares', key: 'shares' },
    { title: '价值', dataIndex: 'value', key: 'value' },
    { title: '权重%', dataIndex: 'weight_pct', key: 'weight_pct', sorter: (a: GuruHoldingItem, b: GuruHoldingItem) => parseFloat(a.weight_pct ?? '0') - parseFloat(b.weight_pct ?? '0') },
    { title: '行业', dataIndex: 'sector', key: 'sector' },
    { title: '总市值', dataIndex: 'market_cap', key: 'market_cap' },
    { title: '3月回报', dataIndex: 'return_3m_pct', key: 'return_3m_pct' },
  ];

  const tradeColumns = [
    { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code' },
    { title: '公司名称', dataIndex: 'stock_name', key: 'stock_name' },
    { title: '操作', dataIndex: 'action', key: 'action', render: (v: string) => <Tag color={v === '新建仓位' || v === '增持' ? 'green' : 'red'}>{v}</Tag> },
    { title: '变动股数', dataIndex: 'shares_changed', key: 'shares_changed' },
    { title: '价格', dataIndex: 'price', key: 'price' },
    { title: '交易日期', dataIndex: 'trade_date', key: 'trade_date' },
    { title: '报告日期', dataIndex: 'report_date', key: 'report_date' },
  ];

  const top10 = [...holdings].sort((a, b) => parseFloat(b.weight_pct ?? '0') - parseFloat(a.weight_pct ?? '0')).slice(0, 10);

  const detailTabs = [
    {
      key: 'overview', label: '概览',
      children: (
        <Row gutter={24}>
          <Col span={12}>
            <Card title="行业分布"><ReactECharts option={sectorPieOption} style={{ height: 360 }} /></Card>
          </Col>
          <Col span={12}>
            <Card title="重仓前10">
              <Table
                dataSource={top10}
                columns={[
                  { title: '股票代码', dataIndex: 'stock_code' },
                  { title: '公司名称', dataIndex: 'stock_name' },
                  { title: '权重%', dataIndex: 'weight_pct' },
                  { title: '行业', dataIndex: 'sector' },
                ]}
                rowKey="id" pagination={false} size="small"
              />
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'holdings', label: '当前持仓',
      children: (
        <div>
          <Input.Search placeholder="搜索股票代码或名称" value={holdingSearch} onChange={(e) => setHoldingSearch(e.target.value)} style={{ width: 300, marginBottom: 16 }} allowClear />
          <Table dataSource={filteredHoldings} columns={holdingColumns} rowKey="id" size="middle" pagination={{ pageSize: 20 }} scroll={{ x: 1200 }} />
        </div>
      ),
    },
    {
      key: 'trades', label: '历史交易',
      children: <Table dataSource={trades} columns={tradeColumns} rowKey="id" size="middle" pagination={{ pageSize: 20 }} scroll={{ x: 1000 }} />,
    },
    {
      key: 'sectors', label: '行业分布',
      children: <Card><ReactECharts option={sectorPieOption} style={{ height: 500 }} /></Card>,
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 24 }}>
        <Row align="middle" gutter={24}>
          <Col>
            <h2 style={{ margin: 0 }}>{guru.name}</h2>
            {guru.name_en && <div style={{ color: '#999' }}>{guru.name_en}</div>}
          </Col>
          <Col>{guru.category && <Tag color={categoryColors[guru.category]} style={{ fontSize: 14 }}>{categoryLabels[guru.category] ?? guru.category}</Tag>}</Col>
          <Col><Statistic title="持仓数" value={guru.num_holdings} /></Col>
          <Col><Statistic title="交易数" value={guru.num_trades} /></Col>
        </Row>
        {guru.description && <p style={{ marginTop: 12, color: '#666' }}>{guru.description}</p>}
      </Card>
      <a style={{ marginBottom: 16, display: 'inline-block' }} onClick={() => onNavigate({ type: 'guru-list' })}>← 返回大师列表</a>
      <Tabs items={detailTabs} />
    </div>
  );
}

// ── Stock List View ──

function StockListView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [stocks, setStocks] = useState<GuruStockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    setLoading(true);
    getGuruStocks(query ? { q: query } : undefined)
      .then((res) => setStocks(res.data ?? []))
      .catch(() => message.error('加载股票列表失败'))
      .finally(() => setLoading(false));
  }, [query]);

  const columns = [
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '市场', dataIndex: 'market', key: 'market', filters: [{ text: 'A股', value: 'A' }, { text: '港股', value: 'HK' }, { text: '美股', value: 'US' }, { text: '台股', value: 'TW' }], onFilter: (value: unknown, record: GuruStockItem) => record.market === value, render: (v: string) => <Tag>{v}</Tag> },
    { title: '行业', dataIndex: 'sector', key: 'sector' },
    { title: '持有大师数', dataIndex: 'guru_count', key: 'guru_count', sorter: (a: GuruStockItem, b: GuruStockItem) => a.guru_count - b.guru_count, defaultSortOrder: 'descend' as const },
  ];

  return (
    <div>
      <Input.Search placeholder="搜索股票代码或名称" onSearch={setQuery} style={{ width: 400, marginBottom: 24 }} allowClear enterButton />
      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : (
        <Table dataSource={stocks} columns={columns} rowKey="id" size="middle" pagination={{ pageSize: 20 }}
          onRow={(record) => ({ style: { cursor: 'pointer' }, onClick: () => onNavigate({ type: 'stock-detail', code: record.code! }) })}
        />
      )}
    </div>
  );
}

// ── Stock Detail View ──

function StockDetailView({ code, onNavigate }: { code: string; onNavigate: (v: View) => void }) {
  const [stock, setStock] = useState<GuruStockItem | null>(null);
  const [gurus, setGurus] = useState<GuruInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([getGuruStockDetail(code), getGuruStockGurus(code)])
      .then(([s, g]) => { setStock(s.data); setGurus(g.data ?? []); })
      .catch(() => message.error('加载股票详情失败'))
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!stock) return <div>未找到该股票</div>;

  const guruColumns = [
    { title: '大师名称', dataIndex: 'name', key: 'name' },
    { title: '英文名', dataIndex: 'name_en', key: 'name_en' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (v: string) => v ? <Tag color={categoryColors[v]}>{categoryLabels[v] ?? v}</Tag> : '-' },
    { title: '持仓数', dataIndex: 'num_holdings', key: 'num_holdings' },
  ];

  return (
    <div>
      <a style={{ marginBottom: 16, display: 'inline-block' }} onClick={() => onNavigate({ type: 'stock-list' })}>← 返回股票列表</a>
      <Card style={{ marginBottom: 24 }}>
        <Descriptions title={`${stock.code} - ${stock.name}`} bordered column={2}>
          <Descriptions.Item label="市场"><Tag>{stock.market}</Tag></Descriptions.Item>
          <Descriptions.Item label="行业">{stock.sector ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="持有大师数">{stock.guru_count}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="持有该股的大师">
        <Table dataSource={gurus} columns={guruColumns} rowKey="id" size="middle" pagination={false}
          onRow={(record) => ({ style: { cursor: 'pointer' }, onClick: () => onNavigate({ type: 'guru-detail', slug: record.slug }) })}
        />
      </Card>
    </div>
  );
}

// ── Screener View ──

function ScreenerView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [stocks, setStocks] = useState<GuruStockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [minGurus, setMinGurus] = useState(2);
  const [market, setMarket] = useState<string | undefined>(undefined);

  useEffect(() => {
    setLoading(true);
    getGuruTopStocks(200)
      .then((res) => setStocks(res.data ?? []))
      .catch(() => message.error('加载数据失败'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let list = stocks.filter((s) => s.guru_count >= minGurus);
    if (market) list = list.filter((s) => s.market === market);
    return list;
  }, [stocks, minGurus, market]);

  const columns = [
    { title: '排名', render: (_: unknown, __: unknown, i: number) => i + 1, width: 60 },
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '市场', dataIndex: 'market', key: 'market', render: (v: string) => <Tag>{v}</Tag> },
    { title: '行业', dataIndex: 'sector', key: 'sector' },
    { title: '持有大师数', dataIndex: 'guru_count', key: 'guru_count', sorter: (a: GuruStockItem, b: GuruStockItem) => a.guru_count - b.guru_count, defaultSortOrder: 'descend' as const },
  ];

  return (
    <div>
      <Card title="选股利器 - 大师共同持仓排行" style={{ marginBottom: 24 }}>
        <Row gutter={24} align="middle">
          <Col><span style={{ marginRight: 8 }}>最低大师数：</span><InputNumber min={1} max={50} value={minGurus} onChange={(v) => setMinGurus(v ?? 1)} /></Col>
          <Col>
            <span style={{ marginRight: 8 }}>市场：</span>
            <Select allowClear placeholder="全部市场" style={{ width: 120 }} value={market} onChange={setMarket}
              options={[{ label: 'A股', value: 'A' }, { label: '港股', value: 'HK' }, { label: '美股', value: 'US' }, { label: '台股', value: 'TW' }]}
            />
          </Col>
          <Col><span style={{ color: '#999' }}>共 {filtered.length} 只股票</span></Col>
        </Row>
      </Card>
      {loading ? (
        <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
      ) : (
        <Table dataSource={filtered} columns={columns} rowKey="id" size="middle" pagination={{ pageSize: 20 }}
          onRow={(record) => ({ style: { cursor: 'pointer' }, onClick: () => onNavigate({ type: 'stock-detail', code: record.code! }) })}
        />
      )}
    </div>
  );
}

// ── Main Component ──

export default function GuruFocus() {
  const [view, setView] = useState<View>({ type: 'home' });
  const [refreshing, setRefreshing] = useState(false);

  const activeTab = useMemo(() => {
    if (view.type === 'guru-detail') return 'guru-list';
    if (view.type === 'stock-detail') return 'stock-list';
    return view.type;
  }, [view]);

  const handleTabChange = useCallback((key: string) => {
    switch (key) {
      case 'home': setView({ type: 'home' }); break;
      case 'guru-list': setView({ type: 'guru-list' }); break;
      case 'stock-list': setView({ type: 'stock-list' }); break;
      case 'screener': setView({ type: 'screener' }); break;
    }
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await refreshGuruHoldings();
      if (res.success) {
        message.success(`更新完成：${(res.data as Record<string, unknown>)?.gurus_updated ?? 0} 个大师持仓已刷新`);
        setView({ type: 'home' }); // force reload
      } else {
        message.error(res.error || '更���失败');
      }
    } catch {
      message.error('更新请求失败');
    } finally {
      setRefreshing(false);
    }
  }, []);

  return (
    <div style={{ padding: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Tabs activeKey={activeTab} items={viewTabItems} onChange={handleTabChange} style={{ marginBottom: 0, flex: 1 }} />
        <Button icon={<SyncOutlined spin={refreshing} />} loading={refreshing} onClick={handleRefresh} title="从天天基金 + SEC EDGAR 获取最新持仓">
          {refreshing ? '更新中...' : '刷新持仓'}
        </Button>
      </div>
      {view.type === 'home' && <HomeView onNavigate={setView} />}
      {view.type === 'guru-list' && <GuruListView initialCategory={view.category} onNavigate={setView} />}
      {view.type === 'guru-detail' && <GuruDetailView slug={view.slug} onNavigate={setView} />}
      {view.type === 'stock-list' && <StockListView onNavigate={setView} />}
      {view.type === 'stock-detail' && <StockDetailView code={view.code} onNavigate={setView} />}
      {view.type === 'screener' && <ScreenerView onNavigate={setView} />}
    </div>
  );
}
