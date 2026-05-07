"""AI assistant chat endpoint using local Claude CLI (Max subscription)."""
from __future__ import annotations

import logging
import subprocess
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.assistant.tools import execute_tool

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiting: simple in-memory tracker
_last_requests: list[float] = []
MAX_REQUESTS_PER_MINUTE = 10

# Tool names to pre-fetch for context injection
_CONTEXT_TOOLS = [
    ("get_funds", {}),
    ("get_deviation_summary", {}),
    ("get_portfolio_latest", {}),
    ("get_portfolio_snapshots", {"limit": 10}),
    ("get_strategies", {}),
    ("get_recent_alerts", {"limit": 10}),
    ("get_configs", {}),
    ("get_allocation_model", {}),
    ("get_allocation_deviation", {}),
]

SYSTEM_PROMPT = """你是萌可，一位投资主理人助手。你不只是回答问题，而是主动帮用户管理投资组合。
你了解用户的良田模型配比、当前持仓偏离、大师动态，能给出调仓建议。
你也能帮用户口述记录投资日记。

你可以：
1. 查询基金列表、价格、偏离度等市场数据
2. 查看投资组合持仓和快照
3. 查看汇率、策略、告警、回测结果
4. 查看良田模型配比目标和偏离度
5. 给出调仓建议
6. 帮用户记录投资日记
7. 查看大师动态信号
8. 查看和修改安全范围内的系统配置

回答风格：
- 简洁专业，使用中文
- 数据展示用表格或列表
- 给出有洞察的分析，不要仅复述数据
- 根据下方提供的数据上下文直接回答用户问题"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[str] = []  # tool names used


def _gather_context() -> tuple[str, list[str]]:
    """Pre-fetch all tool data and return (context_text, tool_names_used)."""
    parts: list[str] = []
    tools_used: list[str] = []

    label_map = {
        "get_funds": "基金列表",
        "get_deviation_summary": "偏离度汇总",
        "get_portfolio_latest": "最新持仓",
        "get_portfolio_snapshots": "组合快照",
        "get_strategies": "策略列表",
        "get_recent_alerts": "最近告警",
        "get_configs": "系统配置",
        "get_allocation_model": "良田模型配比",
        "get_allocation_deviation": "配比偏离摘要",
    }

    for tool_name, tool_args in _CONTEXT_TOOLS:
        try:
            result = execute_tool(tool_name, tool_args)
            label = label_map.get(tool_name, tool_name)
            parts.append(f"【{label}】\n{result}")
            tools_used.append(tool_name)
        except Exception as e:
            logger.warning(f"Pre-fetch tool {tool_name} failed: {e}")

    return "\n\n".join(parts), tools_used


def _build_prompt(messages: list[ChatMessage], context: str) -> str:
    """Build full prompt with system prompt, context data, and conversation history."""
    conv_lines: list[str] = []
    for msg in messages:
        role = "用户" if msg.role == "user" else "萌可"
        conv_lines.append(f"{role}: {msg.content}")

    return f"""{SYSTEM_PROMPT}

以下是当前系统数据（已预先获取）：

{context}

【对话历史】
{chr(10).join(conv_lines)}

请根据以上数据和对话历史，回复用户最新的消息。直接回复内容，不要加角色前缀。"""


@router.post("/chat")
def chat(req: ChatRequest) -> dict:
    # Rate limit check
    now = time.time()
    _last_requests[:] = [t for t in _last_requests if now - t < 60]
    if len(_last_requests) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _last_requests.append(now)

    # Pre-fetch all context data
    context, tools_used = _gather_context()

    # Build prompt
    prompt = _build_prompt(req.messages, context)

    # Call Claude CLI
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/claude", "-p", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"Claude CLI failed: {result.stderr[:300]}")
            raise HTTPException(
                status_code=503,
                detail="AI 助手服务异常，请稍后再试",
            )
        reply = result.stdout.strip()
        if not reply:
            reply = "抱歉，我无法回答这个问题。"
        return {"reply": reply, "tool_calls": tools_used}

    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out after 60s")
        raise HTTPException(status_code=504, detail="AI 助手响应超时，请稍后再试")
    except FileNotFoundError:
        logger.error("Claude CLI not found at /opt/homebrew/bin/claude")
        raise HTTPException(
            status_code=503,
            detail="Claude CLI 未安装，请确保已安装 Claude Code",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assistant chat error: {e}")
        raise HTTPException(status_code=500, detail="AI 助手服务异常，请稍后再试")
