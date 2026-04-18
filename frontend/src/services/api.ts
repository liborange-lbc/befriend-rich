import axios from 'axios';
import type { ApiResponse } from '../types';

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

export default api;
