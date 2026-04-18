import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Select, Space, Switch, Table, message } from 'antd';
import { useEffect, useState } from 'react';
import { del, get, post, put } from '../../services/api';
import type { Fund, Strategy } from '../../types';

export default function StrategyManager() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [funds, setFunds] = useState<Fund[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState<Strategy | null>(null);
  const [form] = Form.useForm();

  const loadData = () => { get<Strategy[]>('/strategy').then((r) => r.success && setStrategies(r.data)); get<Fund[]>('/funds', { page_size: 100 }).then((r) => r.success && setFunds(r.data)); };
  useEffect(loadData, []);
  const openCreate = () => { setEditing(null); form.resetFields(); setModalVisible(true); };
  const openEdit = (s: Strategy) => { setEditing(s); form.setFieldsValue(s); setModalVisible(true); };
  const handleSave = async (values: Partial<Strategy>) => { if (editing) await put(`/strategy/${editing.id}`, values); else await post('/strategy', values); setModalVisible(false); loadData(); message.success('保存成功'); };
  const handleDelete = async (id: number) => { await del(`/strategy/${id}`); loadData(); };
  const handleToggle = async (s: Strategy) => { await put(`/strategy/${s.id}`, { alert_enabled: !s.alert_enabled }); loadData(); };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type', width: 100,
      render: (v: string) => { const m: Record<string, { l: string; c: string }> = { dca: { l: '定投', c: '#F59E0B' }, condition: { l: '条件', c: '#3B82F6' }, ma: { l: '均线', c: '#8B5CF6' } };
        const info = m[v] || { l: v, c: '#6B7280' }; return <span style={{ color: info.c, fontWeight: 500, fontSize: 12 }}>{info.l}</span>; } },
    { title: '关联基金', key: 'fund', render: (_: unknown, r: Strategy) => funds.find((f) => f.id === r.fund_id)?.name || <span style={{ color: '#D1D5DB' }}>-</span> },
    { title: '提醒', key: 'alert_enabled', width: 80, render: (_: unknown, r: Strategy) => <Switch checked={r.alert_enabled} onChange={() => handleToggle(r)} size="small" /> },
    { title: '操作', key: 'actions', width: 120,
      render: (_: unknown, r: Strategy) => (<Space>
        <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(r)} size="small" style={{ color: '#D946EF' }} />
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} size="small" />
      </Space>) },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1>策略管理</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>添加策略</Button>
      </div>
      <div className="section-card"><div style={{ padding: 0 }}><Table dataSource={strategies} columns={columns} rowKey="id" size="small" /></div></div>
      <Modal title={editing ? '编辑策略' : '添加策略'} open={modalVisible} onCancel={() => setModalVisible(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="type" label="类型" initialValue="dca"><Select options={[{ label: '定投', value: 'dca' }, { label: '条件买入', value: 'condition' }, { label: '均线策略', value: 'ma' }]} /></Form.Item>
          <Form.Item name="fund_id" label="关联基金"><Select allowClear options={funds.map((f) => ({ label: `${f.name} (${f.code})`, value: f.id }))} /></Form.Item>
          <Form.Item name="config" label="策略配置 (JSON)" initialValue="{}"><Input.TextArea rows={4} /></Form.Item>
          <Form.Item name="alert_conditions" label="提醒条件 (JSON)" initialValue="[]"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
