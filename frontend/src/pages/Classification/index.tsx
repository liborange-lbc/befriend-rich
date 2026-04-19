import { CloseOutlined, DeleteOutlined, EditOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons';
import { Button, Drawer, Form, Input, Popconfirm, Popover, Select, Space, Table, Tag, Tree, message } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useState } from 'react';
import { del, get, post, put } from '../../services/api';
import type { ClassCategory, ClassModel, Fund, FundClassMap } from '../../types';

const TAG_COLORS = ['purple', 'blue', 'green', 'orange', 'cyan', 'magenta', 'gold', 'lime', 'geekblue', 'volcano'];
const LEVEL_BG_COLORS = ['#FFFFFF', '#F0F5FF', '#F6FFED', '#FFFBE6', '#FFF0F6', '#F0FCFF'];
function getCategoryColor(id: number): string { return TAG_COLORS[id % TAG_COLORS.length]; }
function getLevelBg(level: number): string { return LEVEL_BG_COLORS[Math.min(level, LEVEL_BG_COLORS.length - 1)]; }
interface CategoryMap { [modelId: number]: { tree: ClassCategory[]; flat: ClassCategory[]; }; }

export default function ClassificationPage() {
  const [models, setModels] = useState<ClassModel[]>([]);
  const [funds, setFunds] = useState<Fund[]>([]);
  const [mappings, setMappings] = useState<FundClassMap[]>([]);
  const [categoryMap, setCategoryMap] = useState<CategoryMap>({});
  const [loading, setLoading] = useState(false);
  const [addModelOpen, setAddModelOpen] = useState(false);
  const [addModelName, setAddModelName] = useState('');
  const [editingModelId, setEditingModelId] = useState<number | null>(null);
  const [editModelName, setEditModelName] = useState('');
  const [drawerModelId, setDrawerModelId] = useState<number | null>(null);
  const [catForm] = Form.useForm();
  const [catModalOpen, setCatModalOpen] = useState(false);
  const [catParentId, setCatParentId] = useState<number | null>(null);
  const [editingCell, setEditingCell] = useState<{ fundId: number; modelId: number } | null>(null);
  const [classifying, setClassifying] = useState(false);

  const loadFunds = useCallback(async () => { const r = await get<Fund[]>('/funds', { page_size: 100 }); if (r.success) setFunds(r.data); }, []);
  const loadMappings = useCallback(async () => { const r = await get<FundClassMap[]>('/classification/mappings'); if (r.success) setMappings(r.data); }, []);
  const loadModels = useCallback(async () => { const r = await get<ClassModel[]>('/classification/models'); if (r.success) setModels(r.data); }, []);
  const loadCategoryTree = useCallback(async (modelId: number) => {
    const r = await get<ClassCategory[]>('/classification/categories/tree', { model_id: modelId });
    if (r.success) { const flat: ClassCategory[] = []; const flatten = (nodes: ClassCategory[]) => { nodes.forEach((n) => { flat.push(n); if (n.children) flatten(n.children); }); }; flatten(r.data); setCategoryMap((prev) => ({ ...prev, [modelId]: { tree: r.data, flat } })); }
  }, []);
  const loadAllCategoryTrees = useCallback(async (ml: ClassModel[]) => { await Promise.all(ml.map((m) => loadCategoryTree(m.id))); }, [loadCategoryTree]);
  const loadAll = useCallback(async () => {
    setLoading(true);
    const [modelsRes] = await Promise.all([get<ClassModel[]>('/classification/models'), loadFunds(), loadMappings()]);
    if (modelsRes.success) { setModels(modelsRes.data); await loadAllCategoryTrees(modelsRes.data); }
    setLoading(false);
  }, [loadFunds, loadMappings, loadAllCategoryTrees]);
  useEffect(() => { loadAll(); }, [loadAll]);

  const handleAddModel = async () => { if (!addModelName.trim()) return; await post('/classification/models', { name: addModelName.trim(), description: '' }); setAddModelName(''); setAddModelOpen(false); message.success('模型创建成功'); loadAll(); };
  const handleRenameModel = async (id: number) => { if (!editModelName.trim()) return; await put(`/classification/models/${id}`, { name: editModelName.trim() }); setEditingModelId(null); message.success('模型重命名成功'); loadModels(); };
  const handleDeleteModel = async (id: number) => { await del(`/classification/models/${id}`); message.success('模型删除成功'); loadAll(); };
  const handleMappingChange = async (fundId: number, modelId: number, categoryId: number) => { await post('/classification/mappings', { fund_id: fundId, category_id: categoryId, model_id: modelId }); setEditingCell(null); loadMappings(); };
  const handleAddCategory = async (values: { name: string }) => { if (!drawerModelId) return; await post('/classification/categories', { model_id: drawerModelId, parent_id: catParentId, name: values.name }); setCatModalOpen(false); catForm.resetFields(); message.success('类别创建成功'); loadCategoryTree(drawerModelId); };
  const handleDeleteCategory = async (catId: number) => { await del(`/classification/categories/${catId}`); message.success('类别删除成功'); if (drawerModelId) loadCategoryTree(drawerModelId); };
  const handleAutoClassify = async () => { setClassifying(true); try { const r = await post<{ classified: number; message: string }>('/classification/auto-classify', {}); if (r.success) { message.success(r.data.message); loadAll(); } else { message.error(r.error || 'AI 分类失败'); } } finally { setClassifying(false); } };

  const getMappingCategory = (fundId: number, modelId: number): ClassCategory | undefined => {
    const mapping = mappings.find((m) => m.fund_id === fundId && m.model_id === modelId);
    return mapping ? categoryMap[modelId]?.flat.find((c) => c.id === mapping.category_id) : undefined;
  };
  const convertTree = (cats: ClassCategory[]): DataNode[] => cats.map((c) => ({ key: c.id, title: c.name, children: c.children ? convertTree(c.children) : [] }));

  const columns: ColumnsType<Fund> = [
    { title: '基金', key: 'fund', width: 200, fixed: 'left',
      render: (_, record) => (<div><div style={{ fontWeight: 500 }}>{record.name}</div><div style={{ fontSize: 11, color: '#9CA3AF' }}>{record.code}</div></div>) },
    ...models.map((model) => ({
      title: model.name, key: `model_${model.id}`, width: 150,
      render: (_: unknown, record: Fund) => {
        const category = getMappingCategory(record.id, model.id);
        const isEditing = editingCell?.fundId === record.id && editingCell?.modelId === model.id;
        const flatCats = categoryMap[model.id]?.flat || [];
        if (isEditing) return <Select size="small" style={{ width: '100%' }} placeholder="选择分类" value={category?.id} allowClear autoFocus open
          options={flatCats.map((c) => ({ label: c.name, value: c.id, level: c.level }))}
          optionRender={(option) => {
            const cat = flatCats.find((c) => c.id === option.value);
            const lvl = cat?.level || 1;
            return <div style={{ paddingLeft: (lvl - 1) * 16, background: getLevelBg(lvl), margin: '-5px -12px', padding: `5px ${12 + (lvl - 1) * 16}px`, fontSize: 13 }}>{cat?.name}</div>;
          }}
          onChange={(val) => { if (val) handleMappingChange(record.id, model.id, val); else setEditingCell(null); }} onBlur={() => setEditingCell(null)} />;
        return <div style={{ cursor: 'pointer', minHeight: 22 }} onClick={() => setEditingCell({ fundId: record.id, modelId: model.id })}>
          {category ? <Tag color={getCategoryColor(category.id)}>{category.name}</Tag> : <span style={{ color: '#D1D5DB', fontSize: 12 }}>点击分类</span>}
        </div>;
      },
    })),
  ];

  const drawerModel = models.find((m) => m.id === drawerModelId);
  const drawerTree = drawerModelId ? categoryMap[drawerModelId]?.tree || [] : [];
  const drawerFlat = drawerModelId ? categoryMap[drawerModelId]?.flat || [] : [];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>标的分类</h1>
        <Button icon={<RobotOutlined />} loading={classifying} onClick={handleAutoClassify}>AI 自动分类</Button>
      </div>
      <div style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        {models.map((model) => (
          <div key={model.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 4,
            background: '#F9FAFB', border: '1px solid #E5E7EB', cursor: 'pointer', fontSize: 13, transition: 'all 0.15s' }}
            onClick={() => setDrawerModelId(model.id)}>
            <span>{model.name}</span>
            <Space size={4}>
              <Popover trigger="click" open={editingModelId === model.id}
                onOpenChange={(open) => { if (open) { setEditingModelId(model.id); setEditModelName(model.name); } else setEditingModelId(null); }}
                content={<Space><Input size="small" value={editModelName} onChange={(e) => setEditModelName(e.target.value)} onPressEnter={() => handleRenameModel(model.id)} style={{ width: 120 }} /><Button size="small" type="primary" onClick={() => handleRenameModel(model.id)}>确定</Button></Space>}>
                <EditOutlined style={{ fontSize: 11, color: '#D946EF' }} onClick={(e) => e.stopPropagation()} />
              </Popover>
              <Popconfirm title="确认删除此模型？" onConfirm={(e) => { e?.stopPropagation(); handleDeleteModel(model.id); }} onCancel={(e) => e?.stopPropagation()}>
                <CloseOutlined style={{ fontSize: 11, color: '#EF4444' }} onClick={(e) => e.stopPropagation()} />
              </Popconfirm>
            </Space>
          </div>
        ))}
        <Popover trigger="click" open={addModelOpen} onOpenChange={setAddModelOpen}
          content={<Space><Input size="small" placeholder="模型名称" value={addModelName} onChange={(e) => setAddModelName(e.target.value)} onPressEnter={handleAddModel} style={{ width: 120 }} /><Button size="small" type="primary" onClick={handleAddModel}>添加</Button></Space>}>
          <Button size="small" icon={<PlusOutlined />}>添加模型</Button>
        </Popover>
      </div>
      <div className="section-card"><div style={{ padding: 0 }}><Table dataSource={funds} columns={columns} rowKey="id" loading={loading} size="small" scroll={{ x: 200 + models.length * 150 }} pagination={false} /></div></div>
      <Drawer title={`${drawerModel?.name || ''} — 类别管理`} open={!!drawerModelId} onClose={() => setDrawerModelId(null)} width={400}>
        <div style={{ marginBottom: 16 }}><Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => { setCatParentId(null); catForm.resetFields(); setCatModalOpen(true); }}>添加顶级类别</Button></div>
        <Tree treeData={convertTree(drawerTree)} defaultExpandAll
          titleRender={(node) => (<Space><span>{node.title as string}</span>
            <PlusOutlined style={{ fontSize: 11, color: '#D946EF' }} onClick={(e) => { e.stopPropagation(); setCatParentId(node.key as number); catForm.resetFields(); setCatModalOpen(true); }} />
            <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDeleteCategory(node.key as number); }}>
              <DeleteOutlined style={{ fontSize: 11, color: '#EF4444' }} onClick={(e) => e.stopPropagation()} />
            </Popconfirm></Space>)} />
        {catModalOpen && (<div style={{ marginTop: 16, padding: 12, background: '#F9FAFB', borderRadius: 6, border: '1px solid #E5E7EB' }}>
          <Form form={catForm} layout="inline" onFinish={handleAddCategory}>
            <Form.Item name="name" rules={[{ required: true, message: '请输入类别名称' }]}><Input placeholder="类别名称" size="small" /></Form.Item>
            <Form.Item><Space><Button size="small" type="primary" htmlType="submit">添加</Button><Button size="small" onClick={() => setCatModalOpen(false)}>取消</Button></Space></Form.Item>
          </Form>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>父类别: {catParentId ? drawerFlat.find((c) => c.id === catParentId)?.name : '顶级'}</div>
        </div>)}
      </Drawer>
    </div>
  );
}
