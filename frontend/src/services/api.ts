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
    // Network error, timeout, etc. — normalize to same shape instead of rejecting
    const msg = error.code === 'ECONNABORTED' ? '请求超时' : error.message || '网络错误';
    return { data: { success: false, data: null, error: msg, meta: null } };
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

export async function pullAlipay(force = false) {
  return post<EmailPullResult>(`/import/pull-alipay${force ? '?force=true' : ''}`, {});
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

// === Fund X-ray API ===

export async function getFundHoldings(params: { fund_id?: number; quarter?: string }) {
  return get<import('../types').FundHolding[]>('/fund-xray/holdings', params as Record<string, unknown>);
}

export async function getHoldingQuarters(fundId?: number) {
  return get<string[]>('/fund-xray/holdings/quarters', fundId ? { fund_id: fundId } : {});
}

export async function getStockExposure(targetDate?: string) {
  return get<import('../types').StockExposure[]>('/fund-xray/exposure', targetDate ? { target_date: targetDate } : {});
}

export async function triggerHoldingsFetch(fundId?: number) {
  return post<{ fetched_count: number }>(`/fund-xray/fetch${fundId ? `?fund_id=${fundId}` : ''}`);
}

export async function getAggregatedHoldings(fundIds: number[]) {
  return get<import('../types').AggregatedHolding[]>('/fund-xray/holdings/aggregate', { fund_ids: fundIds.join(',') });
}

// === Export API ===

export function downloadPortfolioCSV() {
  window.open('/api/v1/export/portfolio-csv', '_blank');
}

export function downloadFundStatsCSV() {
  window.open('/api/v1/export/fund-stats-csv', '_blank');
}

export async function getInvestmentReport() {
  return get<Record<string, unknown>>('/export/report');
}

// === Backup API ===

export interface BackupInfo {
  filename: string;
  size: number;
  created_at: string;
}

export async function createBackup() {
  return post<BackupInfo>('/backup/create');
}

export async function listBackups() {
  return get<BackupInfo[]>('/backup/list');
}

export async function restoreBackup(filename: string) {
  return post<{ filename: string; restored_at: string }>(`/backup/restore?filename=${encodeURIComponent(filename)}`);
}

export async function deleteBackup(filename: string) {
  return del<{ deleted: string }>(`/backup/${encodeURIComponent(filename)}`);
}

// === Guru (价值大师) API ===

export async function getGurus(category?: string) {
  return get<import('../types').GuruListResult>('/guru/gurus', category ? { category } : {});
}

export async function getGuruDetail(slug: string) {
  return get<import('../types').GuruDetailInfo>(`/guru/gurus/${slug}`);
}

export async function getGuruHoldings(slug: string) {
  return get<import('../types').GuruHoldingItem[]>(`/guru/gurus/${slug}/holdings`);
}

export async function getGuruTrades(slug: string) {
  return get<import('../types').GuruTradeItem[]>(`/guru/gurus/${slug}/trades`);
}

export async function getGuruSectors(slug: string) {
  return get<import('../types').GuruSectorStat[]>(`/guru/gurus/${slug}/sectors`);
}

export async function getGuruStocks(params?: { q?: string; sector?: string }) {
  return get<import('../types').GuruStockItem[]>('/guru/stocks', params as Record<string, unknown>);
}

export async function getGuruStockDetail(code: string) {
  return get<import('../types').GuruStockItem>(`/guru/stocks/${code}`);
}

export async function getGuruStockGurus(code: string) {
  return get<import('../types').GuruInfo[]>(`/guru/stocks/${code}/gurus`);
}

export async function getGuruOverview() {
  return get<import('../types').GuruOverviewStats>('/guru/overview');
}

export async function getGuruTopStocks(limit = 20) {
  return get<import('../types').GuruStockItem[]>('/guru/top-stocks', { limit });
}

export async function getGuruSectorStats() {
  return get<import('../types').GuruSectorStat[]>('/guru/sectors');
}

export async function guruSearch(q: string) {
  return get<import('../types').GuruSearchResult>('/guru/search', { q });
}

export async function refreshGuruHoldings() {
  return post<Record<string, unknown>>('/guru/refresh');
}

export default api;
