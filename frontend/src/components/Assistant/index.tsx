import { useCallback, useRef, useState } from 'react';
import AssistantButton from './AssistantButton';
import AssistantPanel from './AssistantPanel';

const CCREMOTE_BASE = 'http://localhost:3000';
const AGENT_ID = 'e2092fb0-a872-4acd-9c3c-e62ed9a98b8f';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  costUsd?: number;
  durationMs?: number;
}

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const sessionIdRef = useRef<string>(`fund-session-${Date.now()}`);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const url = `${CCREMOTE_BASE}/api/assistant/${AGENT_ID}/chat`;
    const body = { message: text, sessionId: sessionIdRef.current };

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        let detail = '';
        try {
          const errData = await resp.json();
          detail = errData.error || errData.detail || JSON.stringify(errData);
        } catch {
          detail = await resp.text();
        }
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `**请求失败 (${resp.status} ${resp.statusText})**\n\n${detail}\n\n**调试信息：**\n- URL: \`${url}\`\n- AgentId: \`${AGENT_ID}\`\n- Method: POST`,
          },
        ]);
        setLoading(false);
        return;
      }

      const data = await resp.json();

      if (data.success && data.data) {
        const { text: replyText, sessionId, costUsd, durationMs } = data.data;
        if (sessionId) {
          sessionIdRef.current = sessionId;
        }
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: replyText, costUsd, durationMs },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `**服务返回错误**\n\n${data.error || '未知错误'}\n\n**调试信息：**\n- URL: \`${url}\`\n- AgentId: \`${AGENT_ID}\``,
          },
        ]);
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `**无法连接 CCRemote**\n\n${errMsg}\n\n**调试信息：**\n- URL: \`${url}\`\n- AgentId: \`${AGENT_ID}\`\n\n请确认 CCRemote 服务已启动：\n\`cd CCRemote && npm run dev:server\``,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading]);

  return (
    <>
      {open && (
        <AssistantPanel
          messages={messages}
          input={input}
          loading={loading}
          onInputChange={setInput}
          onSend={sendMessage}
          onClose={() => setOpen(false)}
        />
      )}
      <AssistantButton onClick={() => setOpen(!open)} />
    </>
  );
}
