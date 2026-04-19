import { useCallback, useEffect, useState } from 'react';
import { get, getGroupDimensions, getImportRecords } from '../../services/api';
import type {
  ClassModel,
  GroupDimension,
  GroupedRecordResult,
  ImportRecord,
  RecordSummary,
} from '../../types';
import FilterBar from './FilterBar';
import GroupSelector from './GroupSelector';
import ImportToolbar from './ImportToolbar';
import RecordTable from './RecordTable';

interface Filters {
  dateRange: [string, string] | null;
  keyword: string;
  modelId: number | null;
  categoryId: number | null;
}

const defaultFilters: Filters = {
  dateRange: null,
  keyword: '',
  modelId: null,
  categoryId: null,
};

export default function AssetRecords() {
  const [records, setRecords] = useState<ImportRecord[]>([]);
  const [groupedResults, setGroupedResults] = useState<GroupedRecordResult[] | null>(null);
  const [summary, setSummary] = useState<RecordSummary | null>(null);
  const [dimensions, setDimensions] = useState<GroupDimension[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [classModels, setClassModels] = useState<ClassModel[]>([]);

  const loadDimensions = useCallback(async () => {
    const resp = await getGroupDimensions();
    if (resp.success) setDimensions(resp.data);
  }, []);

  const loadClassModels = useCallback(async () => {
    const resp = await get<ClassModel[]>('/classification/models');
    if (resp.success) setClassModels(resp.data);
  }, []);

  const loadRecords = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (filters.dateRange) {
        params.start_date = filters.dateRange[0];
        params.end_date = filters.dateRange[1];
      }
      if (filters.keyword) params.keyword = filters.keyword;
      if (filters.modelId) params.model_id = filters.modelId;
      if (filters.categoryId) params.category_id = filters.categoryId;
      if (selectedDimensions.length > 0) {
        params.group_by = selectedDimensions.join(',');
      }

      const resp = await getImportRecords(params as {
        start_date?: string;
        end_date?: string;
        keyword?: string;
        model_id?: number;
        category_id?: number;
        group_by?: string;
      });

      if (resp.success) {
        if (selectedDimensions.length > 0 && resp.data && 'groups' in resp.data) {
          setGroupedResults(resp.data.groups);
          setSummary(resp.data.summary);
          setRecords([]);
        } else if (Array.isArray(resp.data)) {
          setRecords(resp.data);
          setGroupedResults(null);
          const meta = resp.meta as { summary?: RecordSummary } | null;
          setSummary(meta?.summary ?? null);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [filters, selectedDimensions]);

  useEffect(() => {
    loadDimensions();
    loadClassModels();
  }, [loadDimensions, loadClassModels]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleFilterChange = useCallback((partial: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, ...partial }));
  }, []);

  const handleDimensionChange = useCallback((selected: string[]) => {
    setSelectedDimensions(selected);
  }, []);

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>资产记录</h1>
      <ImportToolbar onImportSuccess={loadRecords} />
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        classModels={classModels}
      />
      <GroupSelector
        dimensions={dimensions}
        selected={selectedDimensions}
        onChange={handleDimensionChange}
      />
      <RecordTable
        records={records}
        groupedResults={groupedResults}
        summary={summary}
        loading={loading}
        selectedDimensions={selectedDimensions}
        onDataChange={loadRecords}
      />
    </div>
  );
}
