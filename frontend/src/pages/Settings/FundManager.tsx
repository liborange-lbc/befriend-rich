import { CalendarOutlined, DeleteOutlined, DownloadOutlined, EditOutlined, LoadingOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tooltip, message } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import HeatmapDrawer from '../../components/HeatmapDrawer';
import { del, get, post, put } from '../../services/api';
import type { Fund } from '../../types';

export default function FundManager() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingFund, setEditingFund] = useState<Fund | null>(null);
  const [heatmapFund, setHeatmapFund] = useState<Fund | null>(null);
  const [backfillingIds, setBackfillingIds] = useState<Set<number>>(new Set());
  const [fetchingFeeIds, setFetchingFeeIds] = useState<Set<number>>(new Set());
  const pollTimers = useRef<Record<number, ReturnType<typeof setInterval>>>({});
  const [form] = Form.useForm();

  const loadFunds = async () => {
    setLoading(true);
    const resp = await get<Fund[]>('/funds', { page_size: 100 });
    if (resp.success) setFunds(resp.data);
    setLoading(false);
  };

  useEffect(() => { loadFunds(); }, []);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      Object.values(pollTimers.current).forEach(clearInterval);
    };
  }, []);

  const startPolling = useCallback((fundId: number) => {
    setBackfillingIds((prev) => new Set([...prev, fundId]));

    pollTimers.current[fundId] = setInterval(async () => {
      const resp = await get<{ status: string; message: string }>(`/funds/${fundId}/backfill-status`);
      if (!resp.success || !resp.data) return;

      if (resp.data.status === 'done') {
        clearInterval(pollTimers.current[fundId]);
        delete pollTimers.current[fundId];
        setBackfillingIds((prev) => { const n = new Set(prev); n.delete(fundId); return n; });
        message.success(`历史数据回填完成`);
        loadFunds();
      } else if (resp.data.status === 'error') {
        clearInterval(pollTimers.current[fundId]);
        delete pollTimers.current[fundId];
        setBackfillingIds((prev) => { const n = new Set(prev); n.delete(fundId); return n; });
        message.error(`回填失败: ${resp.data.message}`);
      }
    }, 3000);
  }, []);

  const openCreate = () => { setEditingFund(null); form.resetFields(); setModalVisible(true); };
  const openEdit = (fund: Fund) => { setEditingFund(fund); form.setFieldsValue(fund); setModalVisible(true); };

  const handleSave = async (values: Partial<Fund>) => {
    if (editingFund) {
      await put(`/funds/${editingFund.id}`, values);
      message.success('更新成功');
    } else {
      const resp = await post<Fund>('/funds', values);
      if (!resp.success) { message.error(resp.error || '创建失败'); return; }
      message.success('创建成功，正在回填历史数据...');
      if (resp.data?.id) {
        startPolling(resp.data.id);
      }
    }
    setModalVisible(false);
    loadFunds();
  };

  const handleDelete = async (id: number) => { await del(`/funds/${id}`); message.success('删除成功'); loadFunds(); };
  const handleToggle = async (fund: Fund) => { await put(`/funds/${fund.id}`, { is_active: !fund.is_active }); loadFunds(); };

  const handleFetchFee = async (fund: Fund) => {
    setFetchingFeeIds((prev) => new Set([...prev, fund.id]));
    const resp = await post<Fund>(`/funds/${fund.id}/fetch-fees`);
    setFetchingFeeIds((prev) => { const n = new Set(prev); n.delete(fund.id); return n; });
    if (resp.success) {
      message.success(`${fund.name} 费率获取成功`);
      loadFunds();
    } else {
      message.error(resp.error || '获取费率失败');
    }
  };

  const handleBatchFetchFees = async () => {
    const resp = await post<{ success: number; failed: number }>('/funds/batch-fetch-fees');
    if (resp.success) {
      message.success(`批量获取完成: 成功 ${resp.data.success}, 失败 ${resp.data.failed}`);
      loadFunds();
    } else {
      message.error(resp.error || '批量获取失败');
    }
  };

  const columns = [
    { title: '代码', dataIndex: 'code', key: 'code', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 80 },
    { title: '数据源', dataIndex: 'data_source', key: 'data_source', width: 100 },
    {
      title: '持有费率 (%)', key: 'fees', width: 220,
      render: (_: unknown, record: Fund) => {
        if (record.management_fee == null && record.custody_fee == null) {
          return <span style={{ color: '#999' }}>未获取</span>;
        }
        const parts = [
          record.management_fee != null ? `管理 ${record.management_fee}` : null,
          record.custody_fee != null ? `托管 ${record.custody_fee}` : null,
          record.service_fee != null ? `服务 ${record.service_fee}` : null,
        ].filter(Boolean);
        return (
          <Tooltip title={parts.join(' / ')}>
            <span>{record.fee_rate}%</span>
            <span style={{ color: '#999', fontSize: 11, marginLeft: 4 }}>({parts.join(' + ')})</span>
          </Tooltip>
        );
      },
    },
    { title: '启用', key: 'is_active', width: 80, render: (_: unknown, record: Fund) => <Switch checked={record.is_active} onChange={() => handleToggle(record)} size="small" /> },
    {
      title: '操作', key: 'actions', width: 200,
      render: (_: unknown, record: Fund) => (
        <Space>
          {backfillingIds.has(record.id) ? (
            <Tooltip title="正在回填历史数据...">
              <LoadingOutlined style={{ color: '#D946EF', fontSize: 14 }} spin />
            </Tooltip>
          ) : (
            <Tooltip title="历史数据">
              <Button type="link" icon={<CalendarOutlined />} onClick={() => setHeatmapFund(record)} size="small" style={{ color: '#8B5CF6' }} />
            </Tooltip>
          )}
          <Tooltip title="获取费率">
            <Button type="link" icon={fetchingFeeIds.has(record.id) ? <LoadingOutlined spin /> : <DownloadOutlined />} onClick={() => handleFetchFee(record)} size="small" style={{ color: '#10B981' }} disabled={fetchingFeeIds.has(record.id)} />
          </Tooltip>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(record)} size="small" style={{ color: '#D946EF' }} />
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} size="small" />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1>资产标的</h1>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleBatchFetchFees}>批量获取费率</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>添加基金</Button>
        </Space>
      </div>
      <div className="section-card"><div style={{ padding: 0 }}><Table dataSource={funds} columns={columns} rowKey="id" loading={loading} size="small" pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: (total) => `共 ${total} 条` }} /></div></div>

      <Modal title={editingFund ? '编辑基金' : '添加基金'} open={modalVisible} onCancel={() => setModalVisible(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="code" label="代码" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="currency" label="币种" initialValue="CNY"><Select options={[{ label: 'CNY', value: 'CNY' }, { label: 'USD', value: 'USD' }]} /></Form.Item>
          <Form.Item name="data_source" label="数据源" initialValue="tushare"><Select options={[{ label: 'Akshare (场外基金)', value: 'akshare' }, { label: 'Yahoo Finance', value: 'yahoo' }, { label: 'Tushare', value: 'tushare' }]} /></Form.Item>
          <Form.Item name="fee_rate" label="持有总费率 (%)" initialValue={0}><InputNumber style={{ width: '100%' }} min={0} step={0.01} /></Form.Item>
        </Form>
      </Modal>

      <HeatmapDrawer open={!!heatmapFund} onClose={() => setHeatmapFund(null)} fund={heatmapFund} />
    </div>
  );
}
