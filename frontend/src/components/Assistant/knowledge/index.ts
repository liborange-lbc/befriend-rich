/**
 * 知识库索引
 *
 * 按需导出各知识模块，供 Assistant 组件在构建 prompt 时选择性加载。
 * 核心思路：首次对话仅发送角色简介，当用户关联具体模块或提问涉及
 * 特定领域时，才追加对应的详细文档，从而减少 token 消耗。
 */

import { API_REFERENCE } from './api-reference';
import { DOMAIN_MODEL } from './domain-model';

export { API_REFERENCE, DOMAIN_MODEL };

type KnowledgeType = 'domain' | 'api';

/** 模块名 → 需要注入的知识类型 */
const SECTION_KNOWLEDGE_MAP: Record<string, KnowledgeType[]> = {
  // 资金大盘页
  '总资产': ['domain', 'api'],
  '较上期变化': ['domain'],
  '持仓数量与总收益': ['domain'],
  '模型配比': ['domain', 'api'],
  '资产趋势': ['api'],
  '持仓 TOP 5': ['api'],

  // 大盘看板页
  '基金行情': ['domain', 'api'],
  'K线图': ['api'],
  '均值偏差热力图': ['domain', 'api'],
  '策略提醒': ['domain', 'api'],
  '汇率': ['api'],
  '变化幅度': ['domain'],

  // 基金分析页
  '选择基金': ['domain'],

  // 回测页
  '回测配置': ['domain', 'api'],
  '回测指标': ['domain'],
  '净值曲线': ['domain'],
  '交易明细': ['domain'],

  // 分类页
  '标的分类表': ['domain', 'api'],

  // 价值大师页
  '大师总数': ['domain', 'api'],
  '持仓记录': ['domain', 'api'],
  '覆盖股票': ['domain', 'api'],
  '大师列表': ['domain', 'api'],
  '大师详情': ['domain', 'api'],
  '股票列表': ['domain', 'api'],
  '选股器': ['domain', 'api'],
};

const KNOWLEDGE_DOCS: Record<KnowledgeType, string> = {
  domain: DOMAIN_MODEL,
  api: API_REFERENCE,
};

/**
 * 根据模块名返回需要注入的知识文档列表。
 * - 传入 sectionName 时返回该模块对应的文档
 * - 传入 null 时返回空数组（首次对话不注入详细知识）
 */
export function getKnowledgeForSection(sectionName: string | null): string[] {
  if (!sectionName) return [];

  const types = SECTION_KNOWLEDGE_MAP[sectionName] || ['domain', 'api'];
  const seen = new Set<KnowledgeType>();
  const docs: string[] = [];

  for (const t of types) {
    if (seen.has(t)) continue;
    seen.add(t);
    docs.push(KNOWLEDGE_DOCS[t]);
  }
  return docs;
}
