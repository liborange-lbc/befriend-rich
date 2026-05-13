import {
  DatabaseOutlined,
  KeyOutlined,
  LinkOutlined,
  ReloadOutlined,
  SearchOutlined,
  TableOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Card,
  Descriptions,
  Empty,
  Input,
  InputNumber,
  Pagination,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { get } from '../../services/api';

const { Text, Title } = Typography;

/* ── Types ── */

interface TableInfo {
  name: string;
  comment: string;
  row_count: number;
}

interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
  comment: string;
}

interface ForeignKey {
  constrained_columns: string[];
  referred_table: string;
  referred_columns: string[];
}

interface IndexInfo {
  name: string;
  columns: string[];
  unique: boolean;
}

interface TableSchema {
  table_name: string;
  comment: string;
  columns: ColumnInfo[];
  primary_key: string[];
  foreign_keys: ForeignKey[];
  indexes: IndexInfo[];
}

interface DataMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  columns: string[];
}

/* ── Component ── */

export default function DbViewer() {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [schema, setSchema] = useState<TableSchema | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);

  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [dataMeta, setDataMeta] = useState<DataMeta | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [search, setSearch] = useState('');

  /* ── Load table list ── */
  const loadTables = useCallback(async () => {
    setLoading(true);
    const res = await get<TableInfo[]>('/db-viewer/tables');
    if (res.success && res.data) setTables(res.data);
    setLoading(false);
  }, []);

  useEffect(() => { loadTables(); }, [loadTables]);

  /* ── Load schema ── */
  const loadSchema = useCallback(async (name: string) => {
    setSchemaLoading(true);
    const res = await get<TableSchema>(`/db-viewer/tables/${name}/schema`);
    if (res.success && res.data) setSchema(res.data);
    setSchemaLoading(false);
  }, []);

  /* ── Load data ── */
  const loadData = useCallback(async (name: string, p: number, ps: number) => {
    setDataLoading(true);
    const res = await get<Record<string, unknown>[]>(`/db-viewer/tables/${name}/data`, { page: p, page_size: ps });
    if (res.success) {
      setRows(res.data ?? []);
      setDataMeta((res.meta as DataMeta) ?? null);
    }
    setDataLoading(false);
  }, []);

  /* ── Select table ── */
  const handleSelect = useCallback((name: string) => {
    setSelectedTable(name);
    setPage(1);
    loadSchema(name);
    loadData(name, 1, pageSize);
  }, [loadSchema, loadData, pageSize]);

  /* ── Page change ── */
  const handlePageChange = useCallback((p: number, ps: number) => {
    setPage(p);
    setPageSize(ps);
    if (selectedTable) loadData(selectedTable, p, ps);
  }, [selectedTable, loadData]);

  /* ── Filtered tables ── */
  const filteredTables = useMemo(() => {
    if (!search) return tables;
    const q = search.toLowerCase();
    return tables.filter(t => t.name.toLowerCase().includes(q) || t.comment.toLowerCase().includes(q));
  }, [tables, search]);

  /* ── FK lookup for column badges ── */
  const fkMap = useMemo(() => {
    const m = new Map<string, ForeignKey>();
    schema?.foreign_keys.forEach(fk => {
      fk.constrained_columns.forEach(c => m.set(c, fk));
    });
    return m;
  }, [schema]);

  /* ── Data table columns ── */
  const dataColumns = useMemo(() => {
    if (!dataMeta?.columns) return [];
    return dataMeta.columns.map(col => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: 150,
      render: (v: unknown) => {
        if (v === null || v === undefined) return <Text type="secondary" italic>NULL</Text>;
        if (typeof v === 'boolean') return <Tag color={v ? 'green' : 'default'}>{String(v)}</Tag>;
        const s = String(v);
        return s.length > 80 ? <Tooltip title={s}>{s.slice(0, 80)}...</Tooltip> : s;
      },
    }));
  }, [dataMeta]);

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', gap: 16, overflow: 'hidden' }}>
      {/* ── Left: Table list ── */}
      <Card
        size="small"
        title={<span><DatabaseOutlined /> 数据表 ({tables.length})</span>}
        extra={<ReloadOutlined onClick={loadTables} style={{ cursor: 'pointer' }} />}
        style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', height: '100%' }}
        styles={{ body: { flex: 1, overflow: 'auto', padding: '8px 0' } }}
      >
        <div style={{ padding: '0 12px 8px' }}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索表名..."
            size="small"
            allowClear
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <Spin spinning={loading}>
          {filteredTables.map(t => (
            <div
              key={t.name}
              onClick={() => handleSelect(t.name)}
              style={{
                padding: '8px 16px',
                cursor: 'pointer',
                background: selectedTable === t.name ? 'var(--ant-color-primary-bg)' : 'transparent',
                borderLeft: selectedTable === t.name ? '3px solid var(--ant-color-primary)' : '3px solid transparent',
                transition: 'all .2s',
              }}
              onMouseEnter={e => { if (selectedTable !== t.name) (e.currentTarget.style.background = 'var(--ant-color-bg-text-hover)'); }}
              onMouseLeave={e => { if (selectedTable !== t.name) (e.currentTarget.style.background = 'transparent'); }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong style={{ fontSize: 13 }}><TableOutlined style={{ marginRight: 6 }} />{t.name}</Text>
                <Badge count={t.row_count} showZero overflowCount={999999} style={{ backgroundColor: t.row_count > 0 ? 'var(--ant-color-primary)' : '#d9d9d9', fontSize: 11 }} />
              </div>
              {t.comment && <Text type="secondary" style={{ fontSize: 11, marginTop: 2, display: 'block' }}>{t.comment}</Text>}
            </div>
          ))}
        </Spin>
      </Card>

      {/* ── Right: Schema + Data ── */}
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
        {!selectedTable ? (
          <Card style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Empty description="请从左侧选择一张表" />
          </Card>
        ) : (
          <>
            {/* Schema card */}
            <Card
              size="small"
              title={<span><TableOutlined /> {selectedTable} {schema?.comment && <Text type="secondary">— {schema.comment}</Text>}</span>}
            >
              <Spin spinning={schemaLoading}>
                {schema && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {/* Column definitions */}
                    <Table
                      dataSource={schema.columns}
                      rowKey="name"
                      size="small"
                      pagination={false}
                      columns={[
                        {
                          title: '字段', dataIndex: 'name', width: 180,
                          render: (name: string, col: ColumnInfo) => (
                            <span>
                              {col.primary_key && <Tooltip title="主键"><KeyOutlined style={{ color: '#faad14', marginRight: 4 }} /></Tooltip>}
                              {fkMap.has(name) && <Tooltip title={`外键 → ${fkMap.get(name)!.referred_table}.${fkMap.get(name)!.referred_columns.join(',')}`}><LinkOutlined style={{ color: '#1677ff', marginRight: 4 }} /></Tooltip>}
                              <Text strong>{name}</Text>
                            </span>
                          ),
                        },
                        { title: '类型', dataIndex: 'type', width: 140, render: (v: string) => <Tag>{v}</Tag> },
                        { title: '可空', dataIndex: 'nullable', width: 70, render: (v: boolean) => v ? <Text type="secondary">YES</Text> : <Text type="warning">NO</Text> },
                        { title: '默认值', dataIndex: 'default', width: 120, render: (v: string | null) => v ?? <Text type="secondary">-</Text> },
                        { title: '说明', dataIndex: 'comment', render: (v: string) => v || <Text type="secondary">-</Text> },
                      ]}
                    />

                    {/* PK / FK / Index summary */}
                    <Descriptions size="small" bordered column={1}>
                      <Descriptions.Item label="主键">
                        {schema.primary_key.map(k => <Tag key={k} color="gold"><KeyOutlined /> {k}</Tag>)}
                      </Descriptions.Item>
                      {schema.foreign_keys.length > 0 && (
                        <Descriptions.Item label="外键">
                          {schema.foreign_keys.map((fk, i) => (
                            <Tag
                              key={i}
                              color="blue"
                              style={{ cursor: 'pointer' }}
                              onClick={() => handleSelect(fk.referred_table)}
                            >
                              <LinkOutlined /> {fk.constrained_columns.join(',')} → {fk.referred_table}.{fk.referred_columns.join(',')}
                            </Tag>
                          ))}
                        </Descriptions.Item>
                      )}
                      {schema.indexes.length > 0 && (
                        <Descriptions.Item label="索引">
                          {schema.indexes.map(idx => (
                            <Tag key={idx.name} color={idx.unique ? 'purple' : 'default'}>
                              {idx.name} ({idx.columns.join(', ')}){idx.unique ? ' UNIQUE' : ''}
                            </Tag>
                          ))}
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                  </div>
                )}
              </Spin>
            </Card>

            {/* Data preview card */}
            <Card
              size="small"
              title={<span>数据预览 {dataMeta && <Text type="secondary">共 {dataMeta.total} 条</Text>}</span>}
              extra={
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>每页</Text>
                  <InputNumber
                    size="small"
                    min={1}
                    max={500}
                    value={pageSize}
                    onChange={v => { if (v) handlePageChange(1, v); }}
                    style={{ width: 70 }}
                  />
                  <Text type="secondary" style={{ fontSize: 12 }}>条</Text>
                </span>
              }
              style={{ flex: 1 }}
            >
              <Spin spinning={dataLoading}>
                <Table
                  dataSource={rows}
                  columns={dataColumns}
                  rowKey={(_, i) => String(i)}
                  size="small"
                  pagination={false}
                  scroll={{ x: 'max-content', y: 400 }}
                />
                {dataMeta && dataMeta.total > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
                    <Pagination
                      current={page}
                      pageSize={pageSize}
                      total={dataMeta.total}
                      showSizeChanger={false}
                      showQuickJumper
                      showTotal={t => `共 ${t} 条`}
                      onChange={p => handlePageChange(p, pageSize)}
                    />
                  </div>
                )}
              </Spin>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
