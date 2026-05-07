import { forwardRef, useCallback, useImperativeHandle, useRef, useState } from 'react';
import AssistantButton from './AssistantButton';
import AssistantPanel from './AssistantPanel';
import { getKnowledgeForSection } from './knowledge';
import { KNOWLEDGE_INDEX, SYSTEM_ROLE } from './systemPrompt';

const AGENT_ID = 'e2092fb0-a872-4acd-9c3c-e62ed9a98b8f';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  costUsd?: number;
  durationMs?: number;
  traceId?: string;
  traceUrl?: string;
  turnCount?: number;
  status?: string;
}

export interface CopilotContext {
  sectionName: string;
  contextData: unknown;
}

export interface AssistantHandle {
  openWithContext: (sectionName: string, contextData: unknown) => void;
}

const Assistant = forwardRef<AssistantHandle>(function Assistant(_, ref) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeContext, setActiveContext] = useState<CopilotContext | null>(null);
  const sessionIdRef = useRef<string>(`fund-session-${Date.now()}`);
  const systemSentRef = useRef(false);

  const openWithContext = useCallback((sectionName: string, contextData: unknown) => {
    setActiveContext({ sectionName, contextData });
    setOpen(true);
    setInput('');
  }, []);

  useImperativeHandle(ref, () => ({ openWithContext }), [openWithContext]);

  const buildPromptMessage = useCallback((userText: string): string => {
    const parts: string[] = [];
    if (!systemSentRef.current) {
      parts.push(`[系统角色]\n${SYSTEM_ROLE}\n\n[知识索引]\n${KNOWLEDGE_INDEX}\n`);
      systemSentRef.current = true;
    }
    if (activeContext) {
      let dataStr: string;
      try { dataStr = JSON.stringify(activeContext.contextData, null, 2); } catch { dataStr = String(activeContext.contextData); }
      parts.push(`[用户选择了「${activeContext.sectionName}」模块]\n该模块当前展示的数据内容:\n${dataStr}\n`);
    }
    parts.push(`[用户问题]\n${userText}`);
    return parts.join('\n');
  }, [activeContext]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    const promptMessage = buildPromptMessage(text);
    setActiveContext(null);

    const url = `/ccremote/api/assistant/${AGENT_ID}/chat`;

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: promptMessage, sessionId: sessionIdRef.current }),
      });

      if (!resp.ok) {
        let detail = '';
        let errTraceId: string | undefined;
        let errTraceUrl: string | undefined;
        try {
          const e = await resp.json();
          detail = e.error || e.detail || JSON.stringify(e);
          errTraceId = e.traceId;
          errTraceUrl = e.traceUrl;
        } catch { detail = await resp.text(); }
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: `**请求失败 (${resp.status})**\n\n${detail}\n\n- URL: \`${url}\`\n- AgentId: \`${AGENT_ID}\``,
          traceId: errTraceId,
          traceUrl: errTraceUrl,
        }]);
        setLoading(false);
        return;
      }

      const data = await resp.json();
      if (data.success && data.data) {
        if (data.data.sessionId) sessionIdRef.current = data.data.sessionId;
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: data.data.text,
          costUsd: data.data.costUsd,
          durationMs: data.data.durationMs,
          traceId: data.data.traceId,
          traceUrl: data.data.traceUrl,
          turnCount: data.data.turnCount,
          status: data.data.status,
        }]);
      } else {
        const errorMsg: ChatMessage = {
          role: 'assistant',
          content: `**错误**\n\n${data.error || '未知'}`,
          traceId: data.traceId,
          traceUrl: data.traceUrl,
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `**无法连接 CCRemote**\n\n${err instanceof Error ? err.message : err}\n\n请启动: \`cd CCRemote && npm run dev:server\`` }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, buildPromptMessage]);

  return (
    <>
      {open && (
        <AssistantPanel
          messages={messages}
          input={input}
          loading={loading}
          activeContext={activeContext}
          onInputChange={setInput}
          onSend={sendMessage}
          onClose={() => setOpen(false)}
          onClearContext={() => setActiveContext(null)}
        />
      )}
      <AssistantButton onClick={() => setOpen(!open)} />
    </>
  );
});

export default Assistant;

// Re-exports
export { default as CopilotSection } from './CopilotSection';
export { CopilotProvider, useCopilot } from './CopilotContext';
