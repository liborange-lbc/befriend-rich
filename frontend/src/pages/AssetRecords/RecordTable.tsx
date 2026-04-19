import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { Button, Form, Input, InputNumber, Modal, Popconfirm, Space, Table, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { batchDeleteImportRecords, deleteImportRecord, updateImportRecord } from '../../services/api';
import type { GroupedRecordResult, ImportRecord, RecordSummary } from '../../types';

interface RecordTableProps {
  records: ImportRecord[];
  groupedResults: GroupedRecordResult[] | null;
  summary: RecordSummary | null;
  loading: boolean;
  selectedDimensions: string[];
  onDataChange: () => void;
}

function formatAmount(value: number): string {
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function profitColor(value: number): string {
  if (value > 0) return '#EF4444';
  if (value < 0) return '#22C55E';
  return '#9CA3AF';
}

export default function RecordTable({
  records,
  groupedResults,
  summary,
  loading,
  selectedDimensions,
  onDataChange,
}: RecordTableProps) {
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([]);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ImportRecord | null>(null);
  const [editForm] = Form.useForm();
  const [deleting, setDeleting] = useState(false);

  const handleEdit = (record: ImportRecord) => {
    setEditingRecord(record);
    editForm.setFieldsValue({ amount: record.amount, profit: record.profit, fund_code: record.fund_code, fund_name: record.fund_name });
    setEditModalOpen(true);
  };

  const handleEditSave = async () => {
    if (!editingRecord) return;
    const values = await editForm.validateFields();
    const resp = await updateImportRecord(editingRecord.id, {
      amount: values.amount,
      profit: values.profit,
      fund_code: values.fund_code,
      fund_name: values.fund_name,
    });
    if (resp.success) {
      message.success('更新成功');
      setEditModalOpen(false);
      onDataChange();
    } else {
      message.error(resp.error || '更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    const resp = await deleteImportRecord(id);
    if (resp.success) {
      message.success('删除成功');
      setSelectedRowKeys((prev) => prev.filter((k) => k !== id));
      onDataChange();
    } else {
      message.error(resp.error || '删除失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    setDeleting(true);
    try {
      const resp = await batchDeleteImportRecords(selectedRowKeys);
      if (resp.success) {
        message.success(`已删除 ${resp.data.deleted} 条记录`);
        setSelectedRowKeys([]);
        onDataChange();
      } else {
        message.error(resp.error || '批量删除失败');
      }
    } finally {
      setDeleting(false);
    }
  };

  const isGrouped = selectedDimensions.length > 0 && groupedResults !== null;

  const recordColumns: ColumnsType<ImportRecord> = [
    { title: '日期', dataIndex: 'record_date', key: 'record_date', width: 120 },
    { title: '基金代码', dataIndex: 'fund_code', key: 'fund_code', width: 100 },
    { title: '基金名称', dataIndex: 'fund_name', key: 'fund_name', width: 250 },
    {
      title: '持仓金额', dataIndex: 'amount', key: 'amount', width: 150, align: 'right',
      render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>{formatAmount(v)}</span>,
    },
    {
      title: '持仓金额(CNY)', dataIndex: 'amount_cny', key: 'amount_cny', width: 150, align: 'right',
      render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{formatAmount(v)}</span>,
    },
    {
      title: '收益', dataIndex: 'profit', key: 'profit', width: 120, align: 'right',
      render: (v: number) => (
        <span style={{ color: profitColor(v), fontWeight: 500, fontFeatureSettings: "'tnum'" }}>
          {v > 0 ? '+' : ''}{formatAmount(v)}
        </span>
      ),
    },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 80 },
    {
      title: '操作', key: 'actions', width: 100, fixed: 'right',
      render: (_: unknown, record: ImportRecord) => (
        <Space size={4}>
          <Button type="link" icon={<EditOutlined />} size="small" onClick={() => handleEdit(record)} style={{ color: '#8B5CF6' }} />
          <Popconfirm title="确认删除此记录？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button type="link" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (isGrouped && groupedResults) {
    const groupColumns: ColumnsType<GroupedRecordResult> = [
      {
        title: '分组', key: 'group_key', width: 300,
        render: (_: unknown, record: GroupedRecordResult) => (
          <span style={{ fontWeight: 600 }}>
            {Object.entries(record.key).map(([k, v]) => `${k}: ${v}`).join(' / ')}
          </span>
        ),
      },
      {
        title: '持仓总额(CNY)', dataIndex: 'total_amount_cny', key: 'total_amount_cny', width: 160, align: 'right',
        render: (v: number) => <span style={{ fontFeatureSettings: "'tnum'" }}>¥{formatAmount(v)}</span>,
      },
      {
        title: '总收益', dataIndex: 'total_profit', key: 'total_profit', width: 140, align: 'right',
        render: (v: number) => (
          <span style={{ color: profitColor(v), fontWeight: 500, fontFeatureSettings: "'tnum'" }}>
            {v > 0 ? '+' : ''}{formatAmount(v)}
          </span>
        ),
      },
      { title: '记录数', dataIndex: 'count', key: 'count', width: 80, align: 'center' },
    ];

    return (
      <div className="section-card">
        <div style={{ padding: 0 }}>
          <Table
            dataSource={groupedResults}
            columns={groupColumns}
            rowKey={(r) => JSON.stringify(r.key)}
            loading={loading}
            size="small"
            pagination={false}
            expandable={{
              expandedRowRender: (group) => (
                <Table
                  dataSource={group.records}
                  columns={recordColumns}
                  rowKey="id"
                  size="small"
                  pagination={false}
                />
              ),
            }}
            summary={() =>
              summary ? (
                <Table.Summary fixed>
                  <Table.Summary.Row>
                    <Table.Summary.Cell index={0}><span style={{ fontWeight: 600 }}>合计</span></Table.Summary.Cell>
                    <Table.Summary.Cell index={1} align="right">
                      <span style={{ fontWeight: 600, fontFeatureSettings: "'tnum'" }}>¥{formatAmount(summary.total_amount_cny)}</span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={2} align="right">
                      <span style={{ fontWeight: 600, color: profitColor(summary.total_profit), fontFeatureSettings: "'tnum'" }}>
                        {summary.total_profit > 0 ? '+' : ''}{formatAmount(summary.total_profit)}
                      </span>
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={3} align="center"><span style={{ fontWeight: 600 }}>{summary.record_count}</span></Table.Summary.Cell>
                  </Table.Summary.Row>
                </Table.Summary>
              ) : null
            }
          />
        </div>
      </div>
    );
  }

  // Flat mode
  return (
    <div className="section-card">
      {selectedRowKeys.length > 0 && (
        <div style={{ padding: '8px 16px', background: '#FAFAFA', borderBottom: '1px solid #F0F0F0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: '#666' }}>已选 {selectedRowKeys.length} 条</span>
          <Popconfirm title={`确认删除选中的 ${selectedRowKeys.length} 条记录？`} onConfirm={handleBatchDelete} okText="删除" cancelText="取消">
            <Button danger size="small" icon={<DeleteOutlined />} loading={deleting}>批量删除</Button>
          </Popconfirm>
        </div>
      )}
      <div style={{ padding: 0 }}>
        <Table
          dataSource={records}
          columns={recordColumns}
          rowKey="id"
          loading={loading}
          size="small"
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as number[]),
          }}
          pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          scroll={{ x: 1400 }}
          summary={() =>
            summary ? (
              <Table.Summary fixed>
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} />
                  <Table.Summary.Cell index={1} colSpan={4}><span style={{ fontWeight: 600 }}>合计</span></Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    <span style={{ fontWeight: 600, fontFeatureSettings: "'tnum'" }}>¥{formatAmount(summary.total_amount_cny)}</span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={6} align="right">
                    <span style={{ fontWeight: 600, color: profitColor(summary.total_profit), fontFeatureSettings: "'tnum'" }}>
                      {summary.total_profit > 0 ? '+' : ''}{formatAmount(summary.total_profit)}
                    </span>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={7} colSpan={3} />
                </Table.Summary.Row>
              </Table.Summary>
            ) : null
          }
        />
      </div>

      <Modal title="编辑记录" open={editModalOpen} onCancel={() => setEditModalOpen(false)} onOk={handleEditSave} okText="保存">
        {editingRecord && (
          <div style={{ marginBottom: 16, color: '#999', fontSize: 12 }}>{editingRecord.record_date}</div>
        )}
        <Form form={editForm} layout="vertical">
          <Form.Item name="fund_code" label="基金代码" rules={[{ required: true, message: '请输入代码' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="fund_name" label="基金名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="amount" label="持仓金额" rules={[{ required: true, message: '请输入金额' }]}>
            <InputNumber style={{ width: '100%' }} min={0} step={0.01} precision={2} />
          </Form.Item>
          <Form.Item name="profit" label="收益" initialValue={0}>
            <InputNumber style={{ width: '100%' }} step={0.01} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
