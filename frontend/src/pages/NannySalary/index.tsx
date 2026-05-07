import {
  CalendarOutlined,
  DeleteOutlined,
  DollarOutlined,
  EditOutlined,
  EyeOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Timeline,
  Tooltip,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { del, get, post, put } from '../../services/api';

interface Holiday {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  extra_days: number;
}

interface Leave {
  id: number;
  start_date: string;
  end_date: string;
  reason: string;
}

interface DayDetail {
  date: string;
  type: 'normal' | 'holiday' | 'leave';
  value: number;
  accumulated: number;
  holiday_name?: string;
  extra?: number;
}

interface PayDate {
  cycle_start: string;
  pay_date: string;
  calendar_days: number;
  days_detail: DayDetail[];
}

interface CalcResult {
  config: { start_date: string; salary_amount: number; cycle_days: number };
  pay_dates: PayDate[];
  total_paid: number;
  total_amount: number;
}

/* ── Inline calendar: single row, only cycle dates, no blank filler ── */
function CycleCalendar({ detail, cycleDays }: { detail: DayDetail[]; cycleDays: number }) {
  if (!detail || detail.length === 0) return null;

  const todayStr = dayjs().format('YYYY-MM-DD');
  const payDateStr = detail[detail.length - 1].date;

  // Group consecutive days by month for labeling
  let lastMonth = '';

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 8, fontSize: 12 }}>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: 2 }} /> 基础</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#fff7e6', border: '1px solid #ffd591', borderRadius: 2 }} /> 节假日</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#fff1f0', border: '1px solid #ffa39e', borderRadius: 2 }} /> 请假</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f6ffed', border: '2px solid #52c41a', borderRadius: 2 }} /> 发薪日</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {detail.map((cell) => {
          const month = cell.date.slice(5, 7);
          const showMonth = month !== lastMonth;
          lastMonth = month;

          const isPayDay = cell.date === payDateStr;
          const isToday = cell.date === todayStr;
          let bg = '#e6f7ff';
          let border = '1px solid #91d5ff';
          if (cell.type === 'holiday') { bg = '#fff7e6'; border = '1px solid #ffd591'; }
          if (cell.type === 'leave') { bg = '#fff1f0'; border = '1px solid #ffa39e'; }
          if (isPayDay) { bg = '#f6ffed'; border = '2px solid #52c41a'; }

          const day = parseInt(cell.date.slice(8));
          const tooltip = cell.type === 'leave'
            ? `${cell.date} 请假 (不计)`
            : cell.type === 'holiday'
              ? `${cell.date} ${cell.holiday_name} | 计${cell.value}天${cell.extra ? ` (含+${cell.extra})` : ''} | 累计${cell.accumulated}/${cycleDays}`
              : `${cell.date} | 计${cell.value}天 | 累计${cell.accumulated}/${cycleDays}`;

          return (
            <Tooltip key={cell.date} title={tooltip}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {showMonth && (
                  <div style={{ fontSize: 9, color: '#999', marginBottom: 1 }}>{month}月</div>
                )}
                {!showMonth && <div style={{ fontSize: 9, marginBottom: 1, visibility: 'hidden' }}>0</div>}
                <div style={{
                  width: 32, height: 32, display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  background: bg, border, borderRadius: 4,
                  fontWeight: isPayDay || isToday ? 700 : 400,
                  outline: isToday ? '2px solid #1677ff' : 'none',
                  outlineOffset: -1,
                  fontSize: 11,
                  cursor: 'default',
                }}>
                  <div style={{ lineHeight: 1 }}>{day}</div>
                  {cell.type === 'holiday' && cell.extra !== undefined && cell.extra > 0 && (
                    <div style={{ fontSize: 7, color: '#d46b08', lineHeight: 1 }}>(+{cell.extra})</div>
                  )}
                  {cell.type === 'leave' && (
                    <div style={{ fontSize: 7, color: '#cf1322', lineHeight: 1 }}>假</div>
                  )}
                </div>
                {/* Accumulated count below */}
                <div style={{
                  fontSize: 9,
                  color: cell.type === 'leave' ? '#cf1322' : '#666',
                  marginTop: 1,
                  lineHeight: 1,
                }}>
                  {cell.type === 'leave' ? '-' : cell.accumulated}
                </div>
              </div>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

export default function NannySalary() {
  const [config, setConfig] = useState<{ start_date: string; salary_amount: number; cycle_days: number } | null>(null);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [calcResult, setCalcResult] = useState<CalcResult | null>(null);
  const [holidayModal, setHolidayModal] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState<Holiday | null>(null);
  const [leaveModal, setLeaveModal] = useState(false);
  const [configModal, setConfigModal] = useState(false);
  const [calendarModal, setCalendarModal] = useState<PayDate | null>(null);
  const [holidayForm] = Form.useForm();
  const [leaveForm] = Form.useForm();
  const [configForm] = Form.useForm();

  const loadAll = useCallback(async () => {
    const [cfgRes, holRes, leaveRes] = await Promise.all([
      get<any>('/nanny-salary/config'),
      get<any>('/nanny-salary/holidays'),
      get<any>('/nanny-salary/leaves'),
    ]);
    if (cfgRes.success && cfgRes.data) setConfig(cfgRes.data);
    if (holRes.success) setHolidays(holRes.data || []);
    if (leaveRes.success) setLeaves(leaveRes.data || []);
  }, []);

  const loadCalc = useCallback(async () => {
    const res = await get<CalcResult>('/nanny-salary/calculate', { count: 5 });
    if (res.success && res.data && !('error' in res.data)) {
      setCalcResult(res.data);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { if (config) loadCalc(); }, [config, holidays, leaves, loadCalc]);

  // Current cycle: first one with pay_date in the future
  const currentCycle = useMemo(() => {
    if (!calcResult) return null;
    const today = dayjs();
    return calcResult.pay_dates.find(p => dayjs(p.pay_date).isAfter(today, 'day')) || null;
  }, [calcResult]);

  const currentProgress = useMemo(() => {
    if (!currentCycle || !config) return null;
    const todayStr = dayjs().format('YYYY-MM-DD');
    const lastBefore = currentCycle.days_detail
      .filter(d => d.date <= todayStr && d.type !== 'leave')
      .pop();
    return { accumulated: lastBefore?.accumulated || 0, total: config.cycle_days };
  }, [currentCycle, config]);

  // Holidays sorted: upcoming first
  const sortedHolidays = useMemo(() => {
    const todayStr = dayjs().format('YYYY-MM-DD');
    const upcoming = holidays.filter(h => h.end_date >= todayStr);
    const past = holidays.filter(h => h.end_date < todayStr);
    return [...upcoming, ...past];
  }, [holidays]);

  const handleSaveConfig = async (values: any) => {
    const res = await post('/nanny-salary/config', {
      start_date: values.start_date.format('YYYY-MM-DD'),
      salary_amount: values.salary_amount,
      cycle_days: values.cycle_days,
    });
    if (res.success) {
      message.success('配置已保存');
      setConfig({
        start_date: values.start_date.format('YYYY-MM-DD'),
        salary_amount: values.salary_amount,
        cycle_days: values.cycle_days,
      });
      setConfigModal(false);
      loadCalc();
    }
  };

  const handleSaveHoliday = async (values: any) => {
    const payload = {
      name: values.name,
      start_date: values.dates[0].format('YYYY-MM-DD'),
      end_date: values.dates[1].format('YYYY-MM-DD'),
      extra_days: values.extra_days,
    };
    if (editingHoliday) {
      await put(`/nanny-salary/holidays/${editingHoliday.id}`, payload);
      message.success('已更新');
    } else {
      await post('/nanny-salary/holidays', payload);
      message.success('已添加');
    }
    setHolidayModal(false);
    setEditingHoliday(null);
    holidayForm.resetFields();
    loadAll();
    loadCalc();
  };

  const handleAddLeave = async (values: any) => {
    const res = await post('/nanny-salary/leaves', {
      start_date: values.dates[0].format('YYYY-MM-DD'),
      end_date: values.dates[1].format('YYYY-MM-DD'),
      reason: values.reason || '',
    });
    if (res.success) {
      message.success('已添加');
      setLeaveModal(false);
      leaveForm.resetFields();
      loadAll();
      loadCalc();
    }
  };

  const handleDeleteHoliday = async (id: number) => {
    await del(`/nanny-salary/holidays/${id}`);
    loadAll();
    loadCalc();
  };

  const handleDeleteLeave = async (id: number) => {
    await del(`/nanny-salary/leaves/${id}`);
    loadAll();
    loadCalc();
  };

  const openEditHoliday = (h: Holiday) => {
    setEditingHoliday(h);
    holidayForm.setFieldsValue({
      name: h.name,
      dates: [dayjs(h.start_date), dayjs(h.end_date)],
      extra_days: h.extra_days,
    });
    setHolidayModal(true);
  };

  const today = dayjs();

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={[16, 16]}>
        {/* ── 第一行：基本配置 + 当前周期进度 + 发薪试算 ── */}
        <Col xs={24} md={5}>
          <Card
            title="基本配置"
            size="small"
            extra={
              <Button size="small" type="link" onClick={() => {
                if (config) {
                  configForm.setFieldsValue({
                    start_date: dayjs(config.start_date),
                    salary_amount: config.salary_amount,
                    cycle_days: config.cycle_days,
                  });
                }
                setConfigModal(true);
              }}>
                {config ? '修改' : '初始化'}
              </Button>
            }
          >
            {config ? (
              <>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="起始日期">{config.start_date}</Descriptions.Item>
                  <Descriptions.Item label="每期工资">{config.salary_amount} 元</Descriptions.Item>
                  <Descriptions.Item label="周期天数">{config.cycle_days} 天</Descriptions.Item>
                </Descriptions>
                {calcResult && (
                  <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                    <div style={{ flex: 1, padding: 10, background: 'var(--ant-color-bg-layout)', borderRadius: 8 }}>
                      <div style={{ fontSize: 12, color: 'var(--ant-color-text-secondary)' }}>累计已发</div>
                      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--ant-color-success)' }}>
                        <DollarOutlined /> {calcResult.total_amount.toLocaleString()}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--ant-color-text-tertiary)' }}>
                        共 {calcResult.total_paid} 期
                      </div>
                    </div>
                    {currentProgress && config && (
                      <div style={{ flex: 1, padding: 10, background: 'var(--ant-color-bg-layout)', borderRadius: 8 }}>
                        <div style={{ fontSize: 12, color: 'var(--ant-color-text-secondary)' }}>当期应计</div>
                        <div style={{ fontSize: 18, fontWeight: 600, color: '#faad14' }}>
                          <DollarOutlined /> {Math.round(config.salary_amount * currentProgress.accumulated / currentProgress.total).toLocaleString()}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--ant-color-text-tertiary)' }}>
                          {currentProgress.accumulated}/{currentProgress.total}天
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <Alert message="请先配置" type="info" />
            )}
          </Card>
        </Col>

        <Col xs={24} md={11}>
          <Card title="当前周期进度" size="small">
            {currentCycle && currentProgress ? (
              <div>
                <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Progress
                    percent={Math.round((currentProgress.accumulated / currentProgress.total) * 100)}
                    format={() => `${currentProgress.accumulated}/${currentProgress.total}`}
                    size="small"
                    style={{ flex: 1 }}
                  />
                  <Tag color="blue">发薪日: {currentCycle.pay_date}</Tag>
                </div>
                <CycleCalendar detail={currentCycle.days_detail} cycleDays={config!.cycle_days} />
              </div>
            ) : (
              <Alert message="暂无进行中的周期" type="info" />
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="发薪日试算" size="small" style={{ height: '100%' }}>
            {calcResult ? (
              <Timeline
                style={{ marginTop: 8 }}
                items={calcResult.pay_dates.map((p, i) => {
                  const payDay = dayjs(p.pay_date);
                  const isPast = payDay.isBefore(today, 'day') || payDay.isSame(today, 'day');
                  const isUpcoming = !isPast && payDay.diff(today, 'day') <= 7;
                  return {
                    color: isPast ? 'green' : isUpcoming ? 'red' : 'blue',
                    children: (
                      <div style={{ fontSize: 13 }}>
                        <Space size={4}>
                          <Tag color={isPast ? 'success' : isUpcoming ? 'error' : 'processing'} style={{ fontSize: 11 }}>
                            {calcResult.total_paid + i + 1}期
                          </Tag>
                          <strong>{p.pay_date}</strong>
                          <span style={{ color: 'var(--ant-color-text-tertiary)', fontSize: 11 }}>
                            {p.calendar_days}天
                          </span>
                          {isPast && <Tag color="green" style={{ fontSize: 10 }}>已发</Tag>}
                          {isUpcoming && <Tag color="red" style={{ fontSize: 10 }}>即将</Tag>}
                          <Button
                            type="link"
                            size="small"
                            icon={<EyeOutlined />}
                            onClick={() => setCalendarModal(p)}
                            style={{ fontSize: 11, padding: 0 }}
                          >
                            明细
                          </Button>
                        </Space>
                      </div>
                    ),
                  };
                })}
              />
            ) : (
              <Alert message="请先配置" type="info" />
            )}
          </Card>
        </Col>

        {/* ── 第二行：请假 + 节假日 ── */}
        <Col xs={24} md={10}>
          <Card
            title="请假记录"
            size="small"
            extra={<Button icon={<PlusOutlined />} size="small" onClick={() => setLeaveModal(true)}>添加</Button>}
          >
            <Table
              dataSource={leaves}
              rowKey="id"
              size="small"
              pagination={false}
              scroll={{ y: 320 }}
              columns={[
                {
                  title: '日期范围', key: 'dates', width: 200,
                  render: (_, r) => (
                    <><CalendarOutlined /> {r.start_date === r.end_date ? r.start_date : `${r.start_date} ~ ${r.end_date}`}</>
                  ),
                },
                { title: '原因', dataIndex: 'reason' },
                {
                  title: '', key: 'action', width: 40,
                  render: (_, r) => (
                    <Button type="text" danger size="small" icon={<DeleteOutlined />}
                      onClick={() => handleDeleteLeave(r.id)} />
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} md={14}>
          <Card
            title="节假日额外加计"
            size="small"
            extra={<Button icon={<PlusOutlined />} size="small" onClick={() => {
              setEditingHoliday(null);
              holidayForm.resetFields();
              setHolidayModal(true);
            }}>添加</Button>}
          >
            <Table
              dataSource={sortedHolidays}
              rowKey="id"
              size="small"
              pagination={false}
              scroll={{ y: 320 }}
              columns={[
                { title: '节假日', dataIndex: 'name', width: 70 },
                {
                  title: '日期范围', key: 'dates', width: 200,
                  render: (_, r) => `${r.start_date} ~ ${r.end_date}`,
                },
                {
                  title: '额外', dataIndex: 'extra_days', width: 60,
                  render: (v: number) => <Tag color="orange">+{v}</Tag>,
                },
                {
                  title: '', key: 'action', width: 60,
                  render: (_, r) => (
                    <Space size={0}>
                      <Button type="text" size="small" icon={<EditOutlined />}
                        onClick={() => openEditHoliday(r)} />
                      <Button type="text" danger size="small" icon={<DeleteOutlined />}
                        onClick={() => handleDeleteHoliday(r.id)} />
                    </Space>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      {/* Calendar Detail Modal */}
      <Modal
        title={calendarModal ? `周期明细: ${calendarModal.cycle_start} → ${calendarModal.pay_date}` : ''}
        open={!!calendarModal}
        onCancel={() => setCalendarModal(null)}
        footer={null}
        width={700}
      >
        {calendarModal && config && (
          <CycleCalendar detail={calendarModal.days_detail} cycleDays={config.cycle_days} />
        )}
      </Modal>

      {/* Config Modal */}
      <Modal
        title="基本配置"
        open={configModal}
        onCancel={() => setConfigModal(false)}
        onOk={() => configForm.submit()}
      >
        <Form form={configForm} layout="vertical" onFinish={handleSaveConfig}
          initialValues={{ start_date: dayjs('2026-04-23'), salary_amount: 9000, cycle_days: 26 }}>
          <Form.Item name="start_date" label="起始日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="salary_amount" label="每期工资(元)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={1} />
          </Form.Item>
          <Form.Item name="cycle_days" label="计薪天数(天/周期)" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={1} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Holiday Modal */}
      <Modal
        title={editingHoliday ? '修改节假日' : '添加节假日'}
        open={holidayModal}
        onCancel={() => { setHolidayModal(false); setEditingHoliday(null); }}
        onOk={() => holidayForm.submit()}
      >
        <Form form={holidayForm} layout="vertical" onFinish={handleSaveHoliday}>
          <Form.Item name="name" label="节假日名称" rules={[{ required: true }]}>
            <Input placeholder="如：五一" />
          </Form.Item>
          <Form.Item name="dates" label="日期范围" rules={[{ required: true }]}>
            <DatePicker.RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="extra_days" label="额外加计天数" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Leave Modal */}
      <Modal
        title="添加请假"
        open={leaveModal}
        onCancel={() => setLeaveModal(false)}
        onOk={() => leaveForm.submit()}
      >
        <Form form={leaveForm} layout="vertical" onFinish={handleAddLeave}>
          <Form.Item name="dates" label="请假日期范围" rules={[{ required: true }]}>
            <DatePicker.RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="reason" label="原因">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
