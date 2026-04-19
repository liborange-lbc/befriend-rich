"""AI assistant chat endpoint using Anthropic Claude API with tool use."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.assistant.tools import TOOL_DEFINITIONS, execute_tool
from app.services.config_service import get_config

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiting: simple in-memory tracker
_last_requests: list[float] = []
MAX_REQUESTS_PER_MINUTE = 10
MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """你是"萌可"，一个基金资产管理平台的 AI 助手。你可以：
1. 查询基金列表、价格、偏离度等市场数据
2. 查看投资组合持仓和快照
3. 查看汇率、策略、告警、回测结果
4. 查看和修改安全范围内的系统配置

回答风格：
- 简洁专业，使用中文
- 数据展示用表格或列表
- 给出有洞察的分析，不要仅复述数据
- 如果用户问的信息需要调用工具获取，先调用再回答"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[str] = []  # tool names used


@router.post("/chat")
def chat(req: ChatRequest) -> dict:
    # Rate limit check
    now = time.time()
    _last_requests[:] = [t for t in _last_requests if now - t < 60]
    if len(_last_requests) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _last_requests.append(now)

    api_key = get_config("anthropic_api_key")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI 助手未配置 Anthropic API Key，请在设置中填写")

    try:
        import anthropic
    except ImportError:
        raise HTTPException(status_code=503, detail="anthropic 包未安装，请运行 pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    # Build message history
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    tools_used: list[str] = []

    try:
        for _round in range(MAX_TOOL_ROUNDS + 1):
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            # Check if the model wants to use tools
            if response.stop_reason == "tool_use":
                # Collect all tool_use blocks
                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        tools_used.append(block.name)
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                # Extract text response
                text_parts = [b.text for b in response.content if hasattr(b, 'text')]
                reply = "\n".join(text_parts) if text_parts else "抱歉，我无法回答这个问题。"
                return {"reply": reply, "tool_calls": tools_used}

        # If we exhaust tool rounds, return whatever we have
        return {"reply": "查询过于复杂，请尝试简化您的问题。", "tool_calls": tools_used}

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Anthropic API Key 无效，请在设置中检查")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Anthropic API 速率限制，请稍后再试")
    except Exception as e:
        logger.error(f"Assistant chat error: {e}")
        raise HTTPException(status_code=500, detail="AI 助手服务异常，请稍后再试")
