import json
import logging
import re

from sqlalchemy.orm import Session

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.fund import Fund
from app.services.config_service import get_config_with_db

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """
你是一个基金分类专家。请根据基金名称，为每个基金在每个分类模型下选择最合适的分类。

## 分类体系

{classification_tree}

## 待分类基金

{fund_list}

## 输出格式

请以 JSON 格式返回，格式如下：
```json
[
  {{
    "fund_id": 1,
    "fund_name": "...",
    "classifications": [
      {{"model_id": 1, "model_name": "...", "category_id": 5, "category_name": "...", "reason": "..."}}
    ]
  }}
]
```

注意：
- 每个基金在每个模型下只能选择一个分类
- category_id 必须是上面分类体系中存在的 ID
- reason 简要说明分类依据（10字以内）
"""


def _build_classification_tree(db: Session) -> tuple[str, dict[int, set[int]]]:
    """Build classification tree text and valid category IDs per model."""
    models = db.query(ClassModel).all()
    if not models:
        return "", {}

    tree_parts: list[str] = []
    valid_categories: dict[int, set[int]] = {}

    for model in models:
        categories = (
            db.query(ClassCategory)
            .filter(ClassCategory.model_id == model.id)
            .order_by(ClassCategory.level, ClassCategory.sort_order)
            .all()
        )
        valid_categories[model.id] = {c.id for c in categories}

        tree_parts.append(f"\n### 模型: {model.name} (model_id={model.id})")
        for cat in categories:
            indent = "  " * (cat.level - 1)
            tree_parts.append(f"{indent}- {cat.name} (category_id={cat.id}, level={cat.level})")

    return "\n".join(tree_parts), valid_categories


def _build_fund_list(db: Session, fund_ids: list[int]) -> str:
    """Build fund list text for the prompt."""
    funds = db.query(Fund).filter(Fund.id.in_(fund_ids)).all()
    lines: list[str] = []
    for f in funds:
        lines.append(f"- fund_id={f.id}, 名称: {f.name}")
    return "\n".join(lines)


def _parse_ai_response(response_text: str) -> list[dict]:
    """Extract JSON array from AI response text."""
    # Try to find JSON block in markdown code block
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()
    else:
        # Try to find raw JSON array
        bracket_match = re.search(r"\[.*\]", response_text, re.DOTALL)
        if bracket_match:
            text = bracket_match.group(0)
        else:
            text = response_text.strip()

    return json.loads(text)


def classify_funds_with_ai(
    db: Session,
    fund_ids: list[int],
) -> dict[int, dict[int, int]]:
    """
    Use Claude API to classify funds automatically.

    Args:
        db: Database session
        fund_ids: List of fund IDs to classify

    Returns:
        {fund_id: {model_id: category_id}} classification mapping
    """
    if not fund_ids:
        return {}

    # Check API key
    api_key = get_config_with_db(db, "anthropic_api_key", "")
    if not api_key:
        logger.warning("AI classification skipped: Anthropic API key not configured")
        return {}

    # Check if there are any classification models
    models = db.query(ClassModel).all()
    if not models:
        logger.warning("AI classification skipped: no ClassModel defined")
        return {}

    # Build prompt
    tree_text, valid_categories = _build_classification_tree(db)
    fund_list_text = _build_fund_list(db, fund_ids)

    prompt = CLASSIFICATION_PROMPT.format(
        classification_tree=tree_text,
        fund_list=fund_list_text,
    )

    # Call Claude API
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return {}

    # Parse response
    try:
        results = _parse_ai_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {}

    # Validate and create mappings
    classification_map: dict[int, dict[int, int]] = {}

    for item in results:
        fund_id = item.get("fund_id")
        if fund_id not in fund_ids:
            logger.warning(f"AI returned unknown fund_id: {fund_id}")
            continue

        classifications = item.get("classifications", [])
        fund_classifications: dict[int, int] = {}

        for cls in classifications:
            model_id = cls.get("model_id")
            category_id = cls.get("category_id")

            if model_id not in valid_categories:
                logger.warning(f"Invalid model_id {model_id} for fund {fund_id}")
                continue

            if category_id not in valid_categories[model_id]:
                logger.warning(f"Invalid category_id {category_id} for model {model_id}, fund {fund_id}")
                continue

            fund_classifications[model_id] = category_id

            # Upsert FundClassMap
            existing = (
                db.query(FundClassMap)
                .filter(FundClassMap.fund_id == fund_id, FundClassMap.model_id == model_id)
                .first()
            )
            if existing:
                existing.category_id = category_id
            else:
                db.add(FundClassMap(
                    fund_id=fund_id,
                    category_id=category_id,
                    model_id=model_id,
                ))

        if fund_classifications:
            classification_map[fund_id] = fund_classifications

    db.commit()
    logger.info(f"AI classified {len(classification_map)} funds")
    return classification_map
