import { CloseOutlined, SendOutlined } from '@ant-design/icons';
import { Button, Input } from 'antd';
import { useEffect, useRef } from 'react';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  costUsd?: number;
  durationMs?: number;
}

interface AssistantPanelProps {
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onClose: () => void;
}

function formatMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:#f3f4f6;padding:1px 4px;border-radius:3px;font-size:11px;">$1</code>');
  // Line breaks
  html = html.replace(/\n/g, '<br/>');
  return html;
}

export default function AssistantPanel({
  messages,
  input,
  loading,
  onInputChange,
  onSend,
  onClose,
}: AssistantPanelProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        right: 24,
        bottom: 84,
        width: 400,
        height: 500,
        backgroundColor: '#FFFFFF',
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
        zIndex: 1002,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #F3F4F6',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'linear-gradient(135deg, #D946EF, #A855F7)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              color: '#FFFFFF',
              fontWeight: 600,
            }}
          >
            萌
          </span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#FFFFFF' }}>投资萌可</div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)' }}>CCRemote AI 助手</div>
          </div>
        </div>
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined style={{ color: '#FFFFFF' }} />}
          onClick={onClose}
          style={{ color: '#FFFFFF' }}
        />
      </div>

      {/* Messages */}
      <div
        ref={listRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          backgroundColor: '#FAFAFA',
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 12,
              color: '#9CA3AF',
            }}
          >
            <span style={{ fontSize: 36 }}>🐱</span>
            <div style={{ fontSize: 12, textAlign: 'center', lineHeight: 1.8 }}>
              你好！我是投资萌可<br />
              基于 CCRemote 的 AI 投资助手<br />
              <span style={{ fontSize: 11, color: '#D1D5DB' }}>试试问我任何投资相关的问题</span>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                padding: '8px 12px',
                borderRadius: 12,
                fontSize: 13,
                lineHeight: 1.6,
                color: msg.role === 'user' ? '#FFFFFF' : '#1F2937',
                backgroundColor: msg.role === 'user' ? '#D946EF' : '#F3F4F6',
                wordBreak: 'break-word',
              }}
            >
              {msg.role === 'assistant' ? (
                <div
                  dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }}
                />
              ) : (
                <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
              )}
            </div>
            {msg.role === 'assistant' && (msg.costUsd != null || msg.durationMs != null) && (
              <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 4, paddingLeft: 4 }}>
                {msg.durationMs != null && `${(msg.durationMs / 1000).toFixed(1)}s`}
                {msg.costUsd != null && msg.durationMs != null && ' · '}
                {msg.costUsd != null && `$${msg.costUsd.toFixed(4)}`}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
            }}
          >
            <div
              style={{
                padding: '8px 12px',
                borderRadius: 12,
                backgroundColor: '#F3F4F6',
                fontSize: 13,
                color: '#9CA3AF',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span style={{ animation: 'ccremote-dot 1.4s infinite', animationDelay: '0s' }}>·</span>
              <span style={{ animation: 'ccremote-dot 1.4s infinite', animationDelay: '0.2s' }}>·</span>
              <span style={{ animation: 'ccremote-dot 1.4s infinite', animationDelay: '0.4s' }}>·</span>
              <span style={{ marginLeft: 4, fontSize: 11 }}>思考中</span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div
        style={{
          padding: '10px 12px',
          borderTop: '1px solid #F3F4F6',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
          backgroundColor: '#FFFFFF',
        }}
      >
        <Input.TextArea
          ref={inputRef as any}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，Enter 发送..."
          autoSize={{ minRows: 1, maxRows: 3 }}
          style={{ fontSize: 13, resize: 'none' }}
          disabled={loading}
        />
        <Button
          type="primary"
          size="small"
          icon={<SendOutlined />}
          onClick={onSend}
          disabled={!input.trim() || loading}
          style={{
            flexShrink: 0,
            backgroundColor: '#D946EF',
            borderColor: '#D946EF',
          }}
        />
      </div>
    </div>
  );
}
