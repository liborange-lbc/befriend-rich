import axios from 'axios';
import type {
  ApiResponse,
  EmailPullResult,
  GroupedRecordResult,
  GroupDimension,
  ImportLog,
  ImportRecord,
  ImportResult,
  RecordSummary,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.data) {
      return { data: { success: false, data: null, error: error.response.data.detail || error.response.data.error || '请求失败', meta: null } };
    }
    return Promise.reject(error);
  }
);

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<ApiResponse<T>> {
  const resp = await api.get(url, { params });
  return resp.data;
}

export async function post<T>(url: string, data?: unknown): Promise<ApiResponse<T>> {
  const resp = await api.post(url, data);
  return resp.data;
}

export async function put<T>(url: string, data?: unknown): Promise<ApiResponse<T>> {
  const resp = await api.put(url, data);
  return resp.data;
}

export async function del<T>(url: string): Promise<ApiResponse<T>> {
  const resp = await api.delete(url);
  return resp.data;
}

// === Import API ===

export async function uploadExcel(file: File, recordDate: string) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await axios.post(
    `/api/v1/import/upload?record_date=${recordDate}`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 }
  );
  return response.data as ApiResponse<ImportResult>;
}

export async function pullEmail(force = false) {
  return post<EmailPullResult>(`/import/pull-email${force ? '?force=true' : ''}`, {});
}

export async function getImportRecords(params: {
  start_date?: string;
  end_date?: string;
  fund_id?: number;
  keyword?: string;
  model_id?: number;
  category_id?: number;
  group_by?: string;
}) {
  return get<ImportRecord[] | { groups: GroupedRecordResult[]; summary: RecordSummary }>(
    '/import/records',
    params as Record<string, unknown>,
  );
}

export async function getImportLogs(limit = 20) {
  return get<ImportLog[]>('/import/logs', { limit });
}

export async function getGroupDimensions() {
  return get<GroupDimension[]>('/import/group-dimensions');
}

export async function updateImportRecord(recordId: number, params: { amount: number; profit: number; fund_code?: string; fund_name?: string }) {
  const query = new URLSearchParams();
  query.set('amount', String(params.amount));
  query.set('profit', String(params.profit));
  if (params.fund_code !== undefined) query.set('fund_code', params.fund_code);
  if (params.fund_name !== undefined) query.set('fund_name', params.fund_name);
  return put<{ updated: boolean }>(`/import/records/${recordId}?${query.toString()}`, {});
}

export async function deleteImportRecord(recordId: number) {
  return del<{ deleted: boolean }>(`/import/records/${recordId}`);
}

export async function batchDeleteImportRecords(ids: number[]) {
  const params = ids.map((id) => `ids=${id}`).join('&');
  return post<{ deleted: number }>(`/import/records/batch-delete?${params}`, {});
}

export default api;
