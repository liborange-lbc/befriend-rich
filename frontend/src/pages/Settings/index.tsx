import {
  BgColorsOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  SaveOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import { Button, Checkbox, Collapse, Form, Input, InputNumber, Modal, Radio, Select, Table, Tag, message } from 'antd';
import { useEffect, useState } from 'react';
import { useThemeContext } from '../../App';
import type { ThemeName } from '../../hooks/useTheme';
import { get, put, createBackup, listBackups, restoreBackup, deleteBackup, downloadPortfolioCSV, downloadFundStatsCSV } from '../../services/api';
import type { BackupInfo } from '../../services/api';

interface ConfigItem {
  key: string;
  value: string;
  category: string;
  description: string;
}

const CATEGORIES: Record<string, string> = {
  api: 'API 密钥',
  scheduler: '调��配置',
  exchange: '汇率配置',
  email: '邮箱配置',
  backup: '备份配置',
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Settings() {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cronCustom, setCronCustom] = useState(false);
  const [form] = Form.useForm();
  const { theme, setTheme } = useThemeContext();

  // Backup state
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [backupLoading, setBackupLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadBackups = async () => {
    setBackupLoading(true);
    const resp = await listBackups();
    if (resp.success) setBackups(resp.data);
    setBackupLoading(false);
  };

  const handleCreateBackup = async () => {
    setCreating(true);
    const resp = await createBackup();
    if (resp.success) {
      message.success(`备份已创建: ${resp.data.filename}`);
      loadBackups();
    } else {
      message.error(resp.error || '备份失败');
    }
    setCreating(false);
  };

  const handleRestore = (filename: string) => {
    Modal.confirm({
      title: '确认恢复',
      content: `将从 ${filename} 恢复数据库，当前数据将被覆盖。恢复后需重启服务。`,
      okText: '确认恢复',
      okType: 'danger',
      onOk: async () => {
        const resp = await restoreBackup(filename);
        if (resp.success) {
          message.success('数据库已恢复，请重启服务');
        } else {
          message.error(resp.error || '恢复失败');
        }
      },
    });
  };

  const handleDeleteBackup = (filename: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除备份 ${filename}？`,
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        const resp = await deleteBackup(filename);
        if (resp.success) {
          message.success('备份已删除');
          loadBackups();
        }
      },
    });
  };

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

  useEffect(() => { loadConfigs(); loadBackups(); }, []);

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

      {/* ── 数据导出 ── */}
      <div style={{
        marginTop: 12,
        padding: '10px 14px',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg-group)',
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <CloudDownloadOutlined /> 数据导出
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button size="small" onClick={downloadPortfolioCSV}>导出持仓记录 CSV</Button>
          <Button size="small" onClick={downloadFundStatsCSV}>导出基金指标 CSV</Button>
        </div>
      </div>

      {/* ── 数据备份 ── */}
      <div style={{
        marginTop: 12,
        padding: '10px 14px',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg-group)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CloudDownloadOutlined /> 数据备份
          </div>
          <Button size="small" type="primary" onClick={handleCreateBackup} loading={creating}>
            立即备份
          </Button>
        </div>
        <Table
          dataSource={backups}
          rowKey="filename"
          size="small"
          loading={backupLoading}
          pagination={false}
          scroll={{ y: 200 }}
          columns={[
            {
              title: '文件名',
              dataIndex: 'filename',
              render: (v: string) => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v}</span>,
            },
            {
              title: '大小',
              dataIndex: 'size',
              width: 80,
              render: (v: number) => <Tag style={{ fontSize: 10 }}>{formatFileSize(v)}</Tag>,
            },
            {
              title: '时间',
              dataIndex: 'created_at',
              width: 160,
              render: (v: string) => <span style={{ fontSize: 11 }}>{v.replace('T', ' ').slice(0, 19)}</span>,
            },
            {
              title: '操作',
              width: 100,
              render: (_: unknown, record: BackupInfo) => (
                <div style={{ display: 'flex', gap: 4 }}>
                  <Button size="small" icon={<UndoOutlined />} onClick={() => handleRestore(record.filename)} title="恢复" />
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteBackup(record.filename)} title="删除" />
                </div>
              ),
            },
          ]}
        />
        {backups.length === 0 && !backupLoading && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 11, padding: 8 }}>
            暂无备份，点击「立即备份」创建第一个备份
          </div>
        )}
      </div>
    </div>
  );
}
