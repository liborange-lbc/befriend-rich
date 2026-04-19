import { DatePicker, Input, Select, Space } from 'antd';
import type { Dayjs } from 'dayjs';
import type { ClassModel } from '../../types';

interface Filters {
  dateRange: [string, string] | null;
  keyword: string;
  modelId: number | null;
  categoryId: number | null;
}

interface FilterBarProps {
  filters: Filters;
  onFilterChange: (filters: Partial<Filters>) => void;
  classModels: ClassModel[];
}

export default function FilterBar({ filters, onFilterChange, classModels }: FilterBarProps) {
  const handleDateChange = (_: [Dayjs | null, Dayjs | null] | null, dateStrings: [string, string]) => {
    if (dateStrings[0] && dateStrings[1]) {
      onFilterChange({ dateRange: dateStrings });
    } else {
      onFilterChange({ dateRange: null });
    }
  };

  const handleSearch = (value: string) => {
    onFilterChange({ keyword: value });
  };

  const handleModelChange = (value: number | undefined) => {
    onFilterChange({ modelId: value ?? null, categoryId: null });
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      marginBottom: 12,
      padding: '8px 12px',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      background: 'var(--bg-group)',
    }}>
      <Space size={12} wrap>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>日期范围:</span>
          <DatePicker.RangePicker
            size="small"
            onChange={handleDateChange}
            style={{ width: 240 }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>搜索:</span>
          <Input.Search
            size="small"
            placeholder="基金名称/代码"
            allowClear
            onSearch={handleSearch}
            defaultValue={filters.keyword}
            style={{ width: 180 }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>分类模型:</span>
          <Select
            size="small"
            placeholder="全部模型"
            allowClear
            value={filters.modelId ?? undefined}
            onChange={handleModelChange}
            options={classModels.map((m) => ({ label: m.name, value: m.id }))}
            style={{ width: 140 }}
          />
        </div>
      </Space>
    </div>
  );
}
