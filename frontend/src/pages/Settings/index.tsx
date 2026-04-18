import { SaveOutlined } from '@ant-design/icons';
import { Button, Card, Form, Input, InputNumber, message } from 'antd';
import { useEffect, useState } from 'react';
import { get, put } from '../../services/api';

interface ConfigItem {
  key: string;
  value: string;
  category: string;
  description: string;
}

const CATEGORIES: Record<string, string> = {
  api: 'API 密钥',
  scheduler: '调度配置',
  exchange: '汇率配置',
};

const SECRET_KEYS = new Set(['tushare_token', 'feishu_app_id', 'feishu_app_secret']);
const NUMBER_KEYS = new Set(['backfill_years']);

export default function Settings() {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const loadConfigs = async () => {
    setLoading(true);
    const resp = await get<ConfigItem[]>('/config');
    if (resp.success) {
      setConfigs(resp.data);
      const values: Record<string, string> = {};
      resp.data.forEach((c) => { values[c.key] = c.value; });
      form.setFieldsValue(values);
    }
    setLoading(false);
  };

  useEffect(() => { loadConfigs(); }, []);

  const handleSave = async () => {
    const values = form.getFieldsValue();
    const configMap: Record<string, string> = {};
    Object.entries(values).forEach(([key, val]) => {
      configMap[key] = String(val ?? '');
    });

    setSaving(true);
    const resp = await put<{ updated: number }>('/config', { configs: configMap });
    if (resp.success) {
      message.success(`已保存 ${resp.data.updated} 项配置`);
    }
    setSaving(false);
  };

  // Group by category
  const grouped: Record<string, ConfigItem[]> = {};
  configs.forEach((c) => {
    const cat = c.category || 'general';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(c);
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1>系统设置</h1>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
          保存配置
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 60 }}>加载中...</div>
      ) : (
        <Form form={form} layout="vertical">
          {Object.entries(grouped).map(([category, items]) => (
            <Card
              key={category}
              title={CATEGORIES[category] || category}
              size="small"
              style={{ marginBottom: 16 }}
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0 24px' }}>
                {items.map((item) => (
                  <Form.Item
                    key={item.key}
                    name={item.key}
                    label={<span style={{ fontSize: 12 }}>{item.description} <span style={{ color: '#D1D5DB', fontFamily: 'monospace' }}>({item.key})</span></span>}
                    style={{ marginBottom: 12 }}
                  >
                    {SECRET_KEYS.has(item.key) ? (
                      <Input.Password placeholder={item.description} />
                    ) : NUMBER_KEYS.has(item.key) ? (
                      <InputNumber style={{ width: '100%' }} min={1} />
                    ) : (
                      <Input placeholder={item.description} />
                    )}
                  </Form.Item>
                ))}
              </div>
            </Card>
          ))}
        </Form>
      )}
    </div>
  );
}
