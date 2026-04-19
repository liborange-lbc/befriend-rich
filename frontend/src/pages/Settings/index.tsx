import {
  BgColorsOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { Button, Checkbox, Collapse, Form, Input, InputNumber, Radio, Select, message } from 'antd';
import { useEffect, useState } from 'react';
import { useThemeContext } from '../../App';
import type { ThemeName } from '../../hooks/useTheme';
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
  email: '邮箱配置',
};

const SECRET_KEYS = new Set(['tushare_token', 'feishu_app_id', 'feishu_app_secret', 'feishu_webhook_url', 'anthropic_api_key', 'imap_password']);
const NUMBER_KEYS = new Set(['backfill_years']);
const CRON_KEY = 'scheduler_market_cron';
const STRATEGY_HOURS_KEY = 'scheduler_strategy_hours';

const CRON_PRESETS = [
  { label: '每小时', value: '0 * * * *' },
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每 2 小时', value: '0 */2 * * *' },
  { label: '工作日每小时 (9-17点)', value: '0 9-17 * * 1-5' },
  { label: '工作日 9:30', value: '30 9 * * 1-5' },
  { label: '每天 9 点', value: '0 9 * * *' },
  { label: '自定义...', value: '__custom__' },
];

const HOUR_OPTIONS = Array.from({ length: 17 }, (_, i) => i + 6); // 6-22

const THEME_OPTIONS: { value: ThemeName; label: string; desc: string }[] = [
  { value: 'default', label: '默认', desc: '紫粉色调' },
  { value: 'qingming', label: '清明', desc: '青冥 · 丹雘 · 翠微' },
  { value: 'ningye', label: '凝夜', desc: '紫蒲 · 渥赭 · 水龍吟' },
];

export default function Settings() {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cronCustom, setCronCustom] = useState(false);
  const [form] = Form.useForm();
  const { theme, setTheme } = useThemeContext();

  const loadConfigs = async () => {
    setLoading(true);
    const resp = await get<ConfigItem[]>('/config');
    if (resp.success) {
      setConfigs(resp.data);
      const values: Record<string, unknown> = {};
      resp.data.forEach((c) => {
        if (c.key === STRATEGY_HOURS_KEY) {
          values[c.key] = c.value ? c.value.split(',').map(Number) : [];
        } else {
          values[c.key] = c.value;
        }
      });
      form.setFieldsValue(values);

      // Check if cron value matches any preset
      const cronVal = resp.data.find((c) => c.key === CRON_KEY)?.value || '';
      const isPreset = CRON_PRESETS.some((p) => p.value === cronVal);
      setCronCustom(!isPreset && cronVal !== '');
    }
    setLoading(false);
  };

  useEffect(() => { loadConfigs(); }, []);

  const handleSave = async () => {
    const values = form.getFieldsValue();
    const configMap: Record<string, string> = {};
    Object.entries(values).forEach(([key, val]) => {
      if (key === STRATEGY_HOURS_KEY && Array.isArray(val)) {
        configMap[key] = (val as number[]).sort((a, b) => a - b).join(',');
      } else {
        configMap[key] = String(val ?? '');
      }
    });

    setSaving(true);
    const resp = await put<{ updated: number }>('/config', { configs: configMap });
    if (resp.success) {
      message.success(`已保存 ${resp.data.updated} 项配置`);
    }
    setSaving(false);
  };

  const renderField = (item: ConfigItem) => {
    if (item.key === CRON_KEY) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Select
            size="small"
            value={cronCustom ? '__custom__' : form.getFieldValue(CRON_KEY)}
            onChange={(v) => {
              if (v === '__custom__') {
                setCronCustom(true);
              } else {
                setCronCustom(false);
                form.setFieldValue(CRON_KEY, v);
              }
            }}
            options={CRON_PRESETS}
          />
          {cronCustom && (
            <Form.Item name={item.key} noStyle>
              <Input size="small" placeholder="分 时 日 月 周 (e.g. */30 9-17 * * 1-5)" style={{ fontFamily: 'monospace', fontSize: 11 }} />
            </Form.Item>
          )}
          {!cronCustom && <Form.Item name={item.key} noStyle><Input type="hidden" /></Form.Item>}
        </div>
      );
    }

    if (item.key === STRATEGY_HOURS_KEY) {
      return (
        <Form.Item name={item.key} noStyle>
          <Checkbox.Group style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 0' }}>
            {HOUR_OPTIONS.map((h) => (
              <Checkbox key={h} value={h} style={{ fontSize: 11, marginInlineStart: 0, width: 52 }}>
                {String(h).padStart(2, '0')}:00
              </Checkbox>
            ))}
          </Checkbox.Group>
        </Form.Item>
      );
    }

    if (SECRET_KEYS.has(item.key)) {
      return <Form.Item name={item.key} noStyle><Input.Password size="small" placeholder={item.description} /></Form.Item>;
    }

    if (NUMBER_KEYS.has(item.key)) {
      return <Form.Item name={item.key} noStyle><InputNumber size="small" style={{ width: '100%' }} min={1} /></Form.Item>;
    }

    return <Form.Item name={item.key} noStyle><Input size="small" placeholder={item.description} /></Form.Item>;
  };

  // Group by category
  const grouped: Record<string, ConfigItem[]> = {};
  configs.forEach((c) => {
    const cat = c.category || 'general';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(c);
  });

  const collapseItems = Object.entries(grouped).map(([category, items]) => ({
    key: category,
    label: <span style={{ fontSize: 12, fontWeight: 600 }}>{CATEGORIES[category] || category}</span>,
    children: (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 16px' }}>
        {items.map((item) => (
          <div key={item.key}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>
              {item.description}
              <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 10, marginLeft: 4 }}>
                {item.key}
              </span>
            </div>
            {renderField(item)}
          </div>
        ))}
      </div>
    ),
  }));

  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>系统设置</h2>
        <Button type="primary" size="small" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
          保存
        </Button>
      </div>

      {/* ── 主题切换 ── */}
      <div style={{
        marginBottom: 12,
        padding: '10px 14px',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg-group)',
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
          <BgColorsOutlined /> 主题配色
        </div>
        <Radio.Group
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          size="small"
        >
          {THEME_OPTIONS.map((t) => (
            <Radio.Button key={t.value} value={t.value}>
              <span style={{ fontSize: 11 }}>{t.label}</span>
              <span style={{ fontSize: 9, marginLeft: 4, opacity: 0.7 }}>{t.desc}</span>
            </Radio.Button>
          ))}
        </Radio.Group>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40, fontSize: 12 }}>加载中...</div>
      ) : (
        <Form form={form} layout="vertical" size="small">
          <Collapse
            defaultActiveKey={Object.keys(grouped)}
            size="small"
            items={collapseItems}
            style={{ fontSize: 12 }}
          />
        </Form>
      )}
    </div>
  );
}
