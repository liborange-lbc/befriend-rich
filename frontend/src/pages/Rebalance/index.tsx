import { SaveOutlined } from '@ant-design/icons';
import { Button, InputNumber, Table, Tag, message } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { get, post } from '../../services/api';

interface Target {
  category_id: number;
  category_name: string;
  target_pct: number;
}

interface AnalysisItem {
  category_id: number;
  category_name: string;
  actual_amount: number;
  actual_pct: number;
  target_pct: number;
  drift: number;
  target_amount: number;
  action_amount: number;
  action: string;
}

interface AnalysisData {
  total_value: number;
  record_date: string;
  categories: AnalysisItem[];
}

const fmt = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
const actionColor = (a: string) => a === '买入' ? 'green' : a === '卖出' ? 'red' : 'default';

export default function Rebalance() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [editTargets, setEditTargets] = useState<Record<number, number>>({});
  const [saving, setSaving] = useState(false);

  const loadData = () => {
    get<Target[]>('/rebalance/targets').then((r) => {
      if (r.success) {
        setTargets(r.data);
        const map: Record<number, number> = {};
        r.data.forEach((t) => { map[t.category_id] = t.target_pct; });
        setEditTargets(map);
      }
    });
    get<AnalysisData>('/rebalance/analysis').then((r) => r.success && setAnalysis(r.data));
  };

  useEffect(() => { loadData(); }, []);

  const handleSave = async () => {
    setSaving(true);
    const items = Object.entries(editTargets).map(([id, pct]) => ({ category_id: Number(id), target_pct: pct }));
    const resp = await post<{ updated: number }>('/rebalance/targets', { targets: items });
    if (resp.success) {
      message.success(`已保存 ${resp.data.updated} 项目标`);
      loadData();
    }
    setSaving(false);
  };

  const totalTarget = Object.values(editTargets).reduce((s, v) => s + v, 0);

  const radarOption = useMemo(() => {
    if (!analysis?.categories.length) return null;
    const cats = analysis.categories.filter((c) => c.target_pct > 0 || c.actual_pct > 0);
    if (cats.length === 0) return null;
    return {
      tooltip: {},
      legend: { data: ['实际', '目标'], bottom: 0, textStyle: { fontSize: 11 } },
      radar: {
        indicator: cats.map((c) => ({ name: c.category_name.slice(0, 6), max: Math.max(c.actual_pct, c.target_pct, 10) * 1.3 })),
        radius: '60%',
      },
      series: [{
        type: 'radar',
        data: [
          { value: cats.map((c) => c.actual_pct), name: '实际', lineStyle: { color: '#5470c6' }, areaStyle: { opacity: 0.2, color: '#5470c6' } },
          { value: cats.map((c) => c.target_pct), name: '目标', lineStyle: { color: '#91cc75', type: 'dashed' as const }, areaStyle: { opacity: 0.1, color: '#91cc75' } },
        ],
      }],
    };
  }, [analysis]);

  return (
    <div style={{ maxWidth: 960 }}>
      <h2 style={{ fontSize: 15, margin: '0 0 12px' }}>再平衡建议</h2>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        {/* ── 目标配置编辑 ── */}
        <div className="section-card" style={{ flex: 1, minWidth: 300 }}>
          <div className="section-card-header">
            <span className="section-card-title">目标配置</span>
            <span style={{ fontSize: 11, color: totalTarget === 100 ? 'var(--success)' : 'var(--error)', marginLeft: 8 }}>
              合计: {totalTarget.toFixed(1)}%
            </span>
            <Button size="small" type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving} style={{ marginLeft: 'auto' }}>
              保存
            </Button>
          </div>
          <div className="section-card-body">
            {targets.map((t) => (
              <div key={t.category_id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ flex: 1, fontSize: 12 }}>{t.category_name}</span>
                <InputNumber
                  size="small"
                  value={editTargets[t.category_id] ?? 0}
                  min={0}
                  max={100}
                  step={5}
                  formatter={(v) => `${v}%`}
                  parser={(v) => Number((v || '').replace('%', ''))}
                  onChange={(v) => setEditTargets({ ...editTargets, [t.category_id]: v ?? 0 })}
                  style={{ width: 90 }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* ── 雷达图 ── */}
        <div className="section-card" style={{ flex: 1, minWidth: 300 }}>
          <div className="section-card-header"><span className="section-card-title">配置偏离度</span></div>
          <div className="section-card-body">
            {radarOption ? (
              <ReactECharts option={radarOption} style={{ height: 300 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>设置目标配置后可查看偏离度</div>
            )}
          </div>
        </div>
      </div>

      {/* ── 再平衡建议 ── */}
      {analysis && analysis.categories.length > 0 && (
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">再平衡操作建议</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
              总值 ¥{fmt(analysis.total_value)} · {analysis.record_date}
            </span>
          </div>
          <div className="section-card-body">
            <Table
              dataSource={analysis.categories}
              rowKey="category_id"
              size="small"
              pagination={false}
              columns={[
                { title: '分类', dataIndex: 'category_name' },
                { title: '实际金额', dataIndex: 'actual_amount', render: (v: number) => `¥${fmt(v)}` },
                { title: '实际%', dataIndex: 'actual_pct', render: (v: number) => `${v.toFixed(1)}%` },
                { title: '目标%', dataIndex: 'target_pct', render: (v: number) => `${v.toFixed(1)}%` },
                { title: '偏离', dataIndex: 'drift', render: (v: number) => <span style={{ color: Math.abs(v) > 5 ? 'var(--error)' : undefined }}>{v > 0 ? '+' : ''}{v.toFixed(1)}%</span> },
                { title: '操作', dataIndex: 'action', render: (v: string) => <Tag color={actionColor(v)}>{v}</Tag> },
                { title: '调整金额', dataIndex: 'action_amount', render: (v: number) => <span style={{ fontWeight: 600, color: v > 0 ? 'var(--success)' : v < 0 ? 'var(--error)' : undefined }}>{v > 0 ? '+' : ''}{fmt(v)}</span> },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  );
}
