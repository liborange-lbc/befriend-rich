import {
  AudioOutlined,
  MinusOutlined,
  RobotOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { Badge, Button, Input, Spin, Tag } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { post } from '../../services/api';
import './style.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface AssistantResponse {
  reply: string;
  tool_calls: string[];
}

interface AssistantFloatProps {
  currentPath: string;
}

const PAGE_NAMES: Record<string, string> = {
  '/dashboard': '大盘看板',
  '/market-insight': '大盘洞察',
  '/portfolio': '资金大盘',
  '/attribution': '收益归因',
  '/rebalance': '再平衡',
  '/diary': '投资日记',
  '/discipline': '投资纪律',
  '/allocation': '良田配比',
  '/asset-records': '资产记录',
  '/funds': '资产标的',
  '/classification': '标的分类',
  '/fund-xray': '基金透视',
  '/fund-compare': '基金比较',
  '/correlation': '相关性',
  '/analysis': '基金分析',
  '/valuation': '估值指标',
  '/backtest': '回测',
  '/strategy': '策略管理',
  '/guru-focus': '价值大师',
  '/ma-timing': '均线择时',
  '/settings': '系统设置',
};

export default function AssistantFloat({ currentPath }: AssistantFloatProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const pageName = PAGE_NAMES[currentPath] || currentPath;

  // Auto-scroll to bottom
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [open]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      // Prefix page context to the message
      const contextPrefix = `[页面:${pageName}] `;
      const actualContent = contextPrefix + text.trim();

      const userMsg: Message = { role: 'user', content: text.trim() };
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);
      setInput('');
      setLoading(true);

      try {
        // Build payload: all history, but latest user message has page context
        const sendPayload = [
          ...newMessages.slice(0, -1),
          { role: 'user' as const, content: actualContent },
        ];

        const resp = await post<AssistantResponse>('/assistant/chat', {
          messages: sendPayload,
        });

        if (resp.success) {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: resp.data.reply },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `${resp.error || '服务暂不可用'}` },
          ]);
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: '网络异常，请稍后再试' },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [messages, loading, pageName],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <>
      {/* Floating button */}
      {!open && (
        <div className="af-button" onClick={() => setOpen(true)}>
          <RobotOutlined style={{ fontSize: 22, color: '#fff' }} />
        </div>
      )}

      {/* Chat panel */}
      {open && (
        <div className="af-panel">
          {/* Header */}
          <div className="af-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="af-avatar">萌</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  萌可 &middot; 投资主理人
                </div>
                <div
                  style={{ fontSize: 10, color: 'var(--text-muted, #999)' }}
                >
                  AI 资产管理助手
                </div>
              </div>
            </div>
            <Button
              type="text"
              size="small"
              icon={<MinusOutlined />}
              onClick={() => setOpen(false)}
            />
          </div>

          {/* Page context badge */}
          <div className="af-context-badge">
            <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
              当前页面: {pageName}
            </Tag>
          </div>

          {/* Messages */}
          <div className="af-messages" ref={listRef}>
            {messages.length === 0 && (
              <div className="af-welcome">
                <div className="af-welcome-avatar">萌</div>
                <div
                  style={{
                    fontSize: 12,
                    color: 'var(--text-secondary, #666)',
                    textAlign: 'center',
                    lineHeight: 1.8,
                  }}
                >
                  你好！我是萌可，你的投资主理人
                  <br />
                  我了解你的良田配比和持仓偏离，可以给出调仓建议
                  <br />
                  <span
                    style={{
                      fontSize: 11,
                      color: 'var(--text-muted, #999)',
                    }}
                  >
                    试试问：「当前配比偏离如何？」
                  </span>
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`af-msg af-msg-${msg.role}`}>
                {msg.role === 'assistant' && (
                  <span className="af-msg-avatar">萌</span>
                )}
                <div className={`af-msg-bubble af-msg-bubble-${msg.role}`}>
                  <div
                    style={{
                      whiteSpace: 'pre-wrap',
                      fontSize: 12,
                      lineHeight: 1.6,
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="af-msg af-msg-assistant">
                <span className="af-msg-avatar">萌</span>
                <div className="af-msg-bubble af-msg-bubble-assistant">
                  <Spin size="small" />{' '}
                  <span
                    style={{
                      fontSize: 11,
                      color: 'var(--text-muted, #999)',
                      marginLeft: 6,
                    }}
                  >
                    思考中...
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="af-input-area">
            <Button
              type="text"
              size="small"
              icon={<AudioOutlined />}
              title="语音输入（即将上线）"
              disabled
              style={{ flexShrink: 0, alignSelf: 'flex-end' }}
            />
            <Input.TextArea
              ref={inputRef as any}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，Enter 发送..."
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{ fontSize: 12, resize: 'none' }}
              disabled={loading}
            />
            <Button
              type="primary"
              size="small"
              icon={<SendOutlined />}
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || loading}
              style={{ flexShrink: 0, alignSelf: 'flex-end' }}
            />
          </div>
        </div>
      )}
    </>
  );
}
