"""
AI 自动诊断修复服务。

收集系统异常信息，调用 Claude API 分析原因，执行可用的修复动作。
"""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.services.config_service import get_config_with_db
from app.services.data_health_service import (
    get_data_source_overview,
    get_fund_coverage,
    get_job_history,
    repair_fund_coverage,
)

logger = logging.getLogger(__name__)

# AI 可以调用的修复动作
AVAILABLE_ACTIONS = {
    "repair_fund_coverage": "回填异常基金的最近30天价格数据",
    "retry_market_data": "重新抓取所有活跃基金的今日行情",
    "retry_exchange_rate": "重新抓取汇率数据",
    "retry_ic_option": "重新抓取IC期权数据",
}


def _collect_anomalies(db: Session) -> dict:
    """收集系统所有异常信息。"""
    overview = get_data_source_overview(db)
    coverage = get_fund_coverage(db)
    history = get_job_history(db, limit=20)

    error_jobs = [j for j in overview if j["status"] in ("error", "warning")]
    error_funds = [f for f in coverage if f["status"] in ("error", "warning")]
    failed_runs = [h for h in history if h["status"] == "failed"]

    return {
        "error_jobs": error_jobs,
        "error_funds": error_funds,
        "failed_runs": failed_runs[:10],
        "total_active_funds": len(coverage),
        "today": date.today().isoformat(),
    }


def _build_prompt(anomalies: dict) -> str:
    """构造诊断 prompt。"""
    lines = ["你是一个基金资产管理系统的运维 AI。请分析以下异常并给出修复建议。"]
    lines.append("")

    if anomalies["error_jobs"]:
        lines.append("## 异常定时任务")
        for j in anomalies["error_jobs"]:
            lines.append(f"- {j['job_id']}: 状态={j['status']}, 详情={j['detail']}, 上次运行={j['last_run_at']}")
    else:
        lines.append("## 定时任务: 全部正常")

    lines.append("")
    if anomalies["error_funds"]:
        lines.append(f"## 异常基金数据 ({len(anomalies['error_funds'])}/{anomalies['total_active_funds']})")
        for f in anomalies["error_funds"][:15]:
            lines.append(
                f"- {f['fund_code']} {f['fund_name']}: "
                f"数据源={f['data_source']}, 最新={f['latest_date']}, "
                f"延迟={f['gap_days']}天, 状态={f['status']}"
            )
        if len(anomalies["error_funds"]) > 15:
            lines.append(f"  ...还有 {len(anomalies['error_funds']) - 15} 只")
    else:
        lines.append("## 基金数据覆盖: 全部正常")

    lines.append("")
    if anomalies["failed_runs"]:
        lines.append("## 最近失败记录")
        for r in anomalies["failed_runs"]:
            lines.append(f"- {r['job_id']} @ {r['started_at']}: {r['summary'][:150] if r['summary'] else '无摘要'}")

    lines.append("")
    lines.append("## 可用修复动作")
    for action, desc in AVAILABLE_ACTIONS.items():
        lines.append(f"- `{action}`: {desc}")

    lines.append("")
    lines.append("请用 JSON 格式回复:")
    lines.append('```json')
    lines.append('{')
    lines.append('  "diagnosis": "简要分析异常原因",')
    lines.append('  "actions": ["要执行的动作名称列表"],')
    lines.append('  "explanation": "为什么选择这些动作"')
    lines.append('}')
    lines.append('```')

    return "\n".join(lines)


def _execute_actions(db: Session, actions: list[str]) -> list[dict]:
    """执行 AI 建议的修复动作。"""
    results = []

    for action in actions:
        if action == "repair_fund_coverage":
            try:
                repairs = repair_fund_coverage(db)
                repaired = sum(1 for r in repairs if r["status"] == "repaired")
                results.append({
                    "action": action,
                    "status": "done",
                    "detail": f"修复 {repaired}/{len(repairs)} 只基金",
                })
            except Exception as e:
                results.append({"action": action, "status": "failed", "detail": str(e)[:200]})

        elif action == "retry_market_data":
            try:
                from app.services.market_data.fetcher import fetch_all_active_funds
                fetch_all_active_funds(db)
                results.append({"action": action, "status": "done", "detail": "行情数据抓取完成"})
            except Exception as e:
                results.append({"action": action, "status": "failed", "detail": str(e)[:200]})

        elif action == "retry_exchange_rate":
            try:
                from app.services.market_data.exchange_rate import fetch_and_store_all_rates
                fetch_and_store_all_rates(db)
                results.append({"action": action, "status": "done", "detail": "汇率数据抓取完成"})
            except Exception as e:
                results.append({"action": action, "status": "failed", "detail": str(e)[:200]})

        elif action == "retry_ic_option":
            try:
                from app.services.ic_option_service import fetch_and_store
                counts = fetch_and_store(db, days=7)
                results.append({"action": action, "status": "done", "detail": f"IC期权数据: {counts}"})
            except Exception as e:
                results.append({"action": action, "status": "failed", "detail": str(e)[:200]})

        else:
            results.append({"action": action, "status": "skipped", "detail": "未知动作"})

    return results


def ai_diagnose_and_repair(db: Session) -> dict:
    """
    AI 自动诊断修复流程:
    1. 收集所有异常
    2. 如果无异常，直接返回
    3. 调用 Claude API 分析
    4. 执行 AI 建议的修复动作
    5. 返回诊断结果和执行结果
    """
    anomalies = _collect_anomalies(db)

    # 无异常则跳过
    if not anomalies["error_jobs"] and not anomalies["error_funds"] and not anomalies["failed_runs"]:
        return {"status": "healthy", "diagnosis": "系统正常，无异常", "actions_taken": []}

    # 检查 API key
    api_key = get_config_with_db(db, "anthropic_api_key", "")
    if not api_key:
        # 无 API key，直接执行默认修复
        logger.warning("AI diagnose: no API key, running default repair")
        repairs = repair_fund_coverage(db)
        repaired = sum(1 for r in repairs if r["status"] == "repaired")
        return {
            "status": "repaired_without_ai",
            "diagnosis": f"无 Anthropic API Key，执行默认修复: 回填了 {repaired}/{len(repairs)} 只基金",
            "actions_taken": [{"action": "repair_fund_coverage", "status": "done", "detail": f"{repaired}/{len(repairs)}"}],
        }

    # 调用 Claude API
    prompt = _build_prompt(anomalies)
    try:
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text

        # 提取 JSON
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            ai_result = json.loads(response_text[json_start:json_end])
        else:
            ai_result = {"diagnosis": response_text, "actions": [], "explanation": ""}

    except Exception as e:
        logger.error(f"AI diagnose API call failed: {e}")
        # API 失败时执行默认修复
        repairs = repair_fund_coverage(db)
        repaired = sum(1 for r in repairs if r["status"] == "repaired")
        return {
            "status": "repaired_fallback",
            "diagnosis": f"Claude API 调用失败({str(e)[:100]})，已执行默认修复",
            "actions_taken": [{"action": "repair_fund_coverage", "status": "done", "detail": f"{repaired}/{len(repairs)}"}],
        }

    # 执行 AI 建议的动作
    actions = ai_result.get("actions", [])
    action_results = _execute_actions(db, actions) if actions else []

    return {
        "status": "diagnosed",
        "diagnosis": ai_result.get("diagnosis", ""),
        "explanation": ai_result.get("explanation", ""),
        "actions_taken": action_results,
        "anomaly_summary": {
            "error_jobs": len(anomalies["error_jobs"]),
            "error_funds": len(anomalies["error_funds"]),
            "failed_runs": len(anomalies["failed_runs"]),
        },
    }
