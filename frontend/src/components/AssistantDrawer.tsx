import { CloseOutlined, SendOutlined } from '@ant-design/icons';
import { Button, Input, Spin } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { post } from '../services/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface AssistantResponse {
  reply: string;
  tool_calls: string[];
}

interface AssistantDrawerProps {
  open: boolean;
  onClose: () => void;
}

const PAGE_NAMES: Record<string, string> = {
  '/dashboard': '大盘看板',
  '/portfolio': '资产总览',
  '/funds': '基金管理',
  '/classification': '分类管理',
  '/analysis': '基金分析',
  '/backtest': '回测',
  '/strategy': '策略管理',
  '/settings': '系统设置',
};

export default function AssistantDrawer({ open, onClose }: AssistantDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const location = useLocation();
  const contextSent = useRef(false);

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

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    // Prepend page context to first message silently
    let actualContent = text.trim();
    if (!contextSent.current) {
      const pageName = PAGE_NAMES[location.pathname] || location.pathname;
      actualContent = `[当前页面: ${pageName}] ${actualContent}`;
      contextSent.current = true;
    }

    const userMsg: Message = { role: 'user', content: text.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      // Send full history but with context-enhanced first message
      const apiMessages = newMessages.map((m, i) => {
        if (i === 0 && m.role === 'user' && !m.content.startsWith('[当前页面')) {
          return { ...m, content: `[当前页面: ${PAGE_NAMES[location.pathname] || location.pathname}] ${m.content}` };
        }
        return m;
      });

      // Only send the content the user sees, but inject context in the first user message
      const sendPayload = apiMessages.length === newMessages.length
        ? [...newMessages.slice(0, -1), { role: 'user' as const, content: actualContent }]
        : newMessages;

      const resp = await post<AssistantResponse>('/assistant/chat', {
        messages: sendPayload,
      });

      if (resp.success) {
        setMessages((prev) => [...prev, { role: 'assistant', content: resp.data.reply }]);
      } else {
        setMessages((prev) => [...prev, { role: 'assistant', content: `抱歉，${resp.error || '服务暂不可用'}` }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '网络异常，请稍后再试' }]);
    } finally {
      setLoading(false);
    }
  }, [messages, loading, location.pathname]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!open) return null;

  return (
    <div className="assistant-overlay">
      <div className="assistant-drawer">
        {/* Header */}
        <div className="assistant-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="assistant-avatar">萌</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>萌可助手</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>AI 基金分析助手</div>
            </div>
          </div>
          <Button type="text" size="small" icon={<CloseOutlined />} onClick={onClose} />
        </div>

        {/* Messages */}
        <div className="assistant-messages" ref={listRef}>
          {messages.length === 0 && (
            <div className="assistant-welcome">
              <div className="assistant-welcome-avatar">萌</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.8 }}>
                你好！我是萌可助手<br />
                我可以帮你查看基金数据、分析持仓、查询策略等<br />
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>试试问：「哪只基金偏离度最大？」</span>
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`assistant-msg assistant-msg-${msg.role}`}>
              {msg.role === 'assistant' && <span className="assistant-msg-avatar">萌</span>}
              <div className={`assistant-msg-bubble assistant-msg-bubble-${msg.role}`}>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6 }}>
                  {msg.content}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="assistant-msg assistant-msg-assistant">
              <span className="assistant-msg-avatar">萌</span>
              <div className="assistant-msg-bubble assistant-msg-bubble-assistant">
                <Spin size="small" /> <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>思考中...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="assistant-input-area">
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
    </div>
  );
}
