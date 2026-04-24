import { DeleteOutlined, EditOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons';
import { Button, DatePicker, Input, Modal, Radio, Select, Tag, Timeline, message } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { del, get, post, put } from '../../services/api';

interface DiaryEntry {
  id: number;
  entry_date: string;
  title: string;
  content: string;
  mood: string | null;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

const MOOD_OPTIONS = [
  { value: 'bullish', label: '看多', color: 'green' },
  { value: 'neutral', label: '中性', color: 'default' },
  { value: 'bearish', label: '看空', color: 'red' },
];

const MOOD_COLOR: Record<string, string> = { bullish: 'green', neutral: 'blue', bearish: 'red' };
const MOOD_LABEL: Record<string, string> = { bullish: '看多', neutral: '中性', bearish: '看空' };

export default function Diary() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [keyword, setKeyword] = useState('');
  const [editing, setEditing] = useState<DiaryEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ entry_date: dayjs().format('YYYY-MM-DD'), title: '', content: '', mood: 'neutral', tags: '' });
  const [summaryText, setSummaryText] = useState('');
  const [summaryLoading, setSummaryLoading] = useState(false);

  const loadEntries = () => {
    const params: Record<string, unknown> = {};
    if (keyword) params.keyword = keyword;
    get<DiaryEntry[]>('/diary', params).then((r) => r.success && setEntries(r.data));
  };

  useEffect(() => { loadEntries(); }, [keyword]);

  const handleSave = async () => {
    const body = {
      entry_date: form.entry_date,
      title: form.title,
      content: form.content,
      mood: form.mood || null,
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
    };

    if (editing) {
      const resp = await put<DiaryEntry>(`/diary/${editing.id}`, body);
      if (resp.success) { message.success('已更新'); setEditing(null); loadEntries(); }
    } else {
      const resp = await post<DiaryEntry>('/diary', body);
      if (resp.success) { message.success('已创建'); setCreating(false); loadEntries(); }
    }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定删除这条日记？',
      okType: 'danger',
      onOk: async () => {
        await del(`/diary/${id}`);
        loadEntries();
      },
    });
  };

  const handleAISummary = async (period: string) => {
    setSummaryLoading(true);
    const resp = await post<{ summary: string }>(`/diary/ai-summary?period=${period}`);
    if (resp.success) setSummaryText(resp.data.summary);
    else message.error(resp.error || 'AI 总结失败');
    setSummaryLoading(false);
  };

  const openCreate = () => {
    setForm({ entry_date: dayjs().format('YYYY-MM-DD'), title: '', content: '', mood: 'neutral', tags: '' });
    setCreating(true);
    setEditing(null);
  };

  const openEdit = (e: DiaryEntry) => {
    setForm({ entry_date: e.entry_date, title: e.title, content: e.content, mood: e.mood || 'neutral', tags: e.tags.join(', ') });
    setEditing(e);
    setCreating(true);
  };

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>投资日记</h2>
        <Input.Search size="small" placeholder="搜索..." value={keyword} onChange={(e) => setKeyword(e.target.value)} style={{ width: 200 }} allowClear />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <Button size="small" icon={<RobotOutlined />} onClick={() => handleAISummary('week')} loading={summaryLoading}>周总结</Button>
          <Button size="small" icon={<RobotOutlined />} onClick={() => handleAISummary('month')} loading={summaryLoading}>月总结</Button>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建</Button>
        </div>
      </div>

      {/* AI Summary */}
      {summaryText && (
        <div className="section-card" style={{ marginBottom: 12 }}>
          <div className="section-card-header"><span className="section-card-title">AI 投资总结</span></div>
          <div className="section-card-body" style={{ fontSize: 12, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {summaryText}
          </div>
        </div>
      )}

      {/* Timeline */}
      <Timeline
        items={entries.map((e) => ({
          color: MOOD_COLOR[e.mood || 'neutral'] || 'blue',
          children: (
            <div style={{ background: 'var(--bg-group)', borderRadius: 'var(--radius-md)', padding: '8px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{e.entry_date}</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{e.title}</span>
                {e.mood && <Tag color={MOOD_COLOR[e.mood]} style={{ fontSize: 10 }}>{MOOD_LABEL[e.mood]}</Tag>}
                {e.tags.map((t) => <Tag key={t} style={{ fontSize: 10 }}>{t}</Tag>)}
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                  <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(e)} />
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => handleDelete(e.id)} />
                </div>
              </div>
              {e.content && <div style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{e.content}</div>}
            </div>
          ),
        }))}
      />

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 12 }}>
          暂无日记，点击「新建」开始记录投资决策
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        title={editing ? '编辑日记' : '新建日记'}
        open={creating}
        onOk={handleSave}
        onCancel={() => { setCreating(false); setEditing(null); }}
        okText="保存"
        width={500}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <DatePicker
            size="small"
            value={dayjs(form.entry_date)}
            onChange={(d) => d && setForm({ ...form, entry_date: d.format('YYYY-MM-DD') })}
            style={{ width: '100%' }}
          />
          <Input size="small" placeholder="标题" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <Input.TextArea rows={6} placeholder="内容（支持 Markdown）" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
          <Radio.Group value={form.mood} onChange={(e) => setForm({ ...form, mood: e.target.value })} size="small">
            {MOOD_OPTIONS.map((m) => <Radio.Button key={m.value} value={m.value}>{m.label}</Radio.Button>)}
          </Radio.Group>
          <Input size="small" placeholder="标签（逗号分隔）" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
        </div>
      </Modal>
    </div>
  );
}
