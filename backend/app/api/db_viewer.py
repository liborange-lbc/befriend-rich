"""Database introspection API – tables, columns, foreign keys, data preview."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok

router = APIRouter()

# ── 中文表说明（与 SQLAlchemy model __doc__ / __tablename__ 对应） ──
TABLE_COMMENTS: dict[str, str] = {
    "funds": "基金/资产标的",
    "wechat_portfolio_records": "持仓记录（每日每基金）",
    "wechat_portfolio_snapshots": "持仓快照（每日汇总）",
    "class_models": "分类模型",
    "class_categories": "分类类目",
    "fund_class_map": "基金-分类映射",
    "strategies": "策略定义",
    "backtest_results": "回测结果",
    "alert_logs": "策略告警日志",
    "fund_daily_prices": "基金每日净值",
    "exchange_rates": "汇率数据",
    "fund_holdings": "基金持仓明细（季报）",
    "market_index_components": "市场指数成分",
    "market_stocks": "市场股票信息",
    "allocation_targets": "资产配置目标",
    "allocation_snapshots": "资产配置快照",
    "rebalance_targets": "再平衡目标",
    "gurus": "价值大师",
    "guru_holdings": "大师持仓",
    "guru_trades": "大师交易",
    "guru_stocks": "大师关注股票",
    "ic_option_prices": "IC 期权价格",
    "wechat_nanny_salary_config": "月嫂薪资配置",
    "wechat_nanny_salary_holidays": "月嫂假期",
    "wechat_nanny_salary_leaves": "月嫂请假记录",
    "system_configs": "系统配置",
    "job_runs": "定时任务运行记录",
    "import_logs": "数据导入日志",
    "wechat_users": "微信用户",
    "wechat_steps": "微信步数",
    "wechat_family_profiles": "家庭成员档案",
    "wechat_injury_records": "伤病记录",
    "wechat_watch_connections": "手表连接",
    "wechat_watch_activities": "运动记录",
}

COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "funds": {
        "id": "主键",
        "code": "基金代码",
        "name": "基金名称",
        "currency": "币种",
        "data_source": "数据源",
        "fee_rate": "费率",
        "management_fee": "管理费率",
        "custody_fee": "托管费率",
        "service_fee": "服务费率",
        "is_active": "是否启用",
    },
    "wechat_portfolio_records": {
        "id": "主键",
        "openid": "用户标识",
        "fund_id": "基金 ID",
        "record_date": "记录日期",
        "amount": "金额（原币）",
        "amount_cny": "金额（人民币）",
        "profit": "收益",
        "channel": "渠道",
    },
    "wechat_portfolio_snapshots": {
        "id": "主键",
        "openid": "用户标识",
        "snapshot_date": "快照日期",
        "total_amount": "总金额",
        "total_profit": "总收益",
    },
}


@router.get("/tables")
def list_tables(db: Session = Depends(get_db)):
    """列出所有表及其说明、行数。"""
    insp = inspect(db.bind)
    tables = insp.get_table_names()
    result = []
    for t in sorted(tables):
        row_count = db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        result.append({
            "name": t,
            "comment": TABLE_COMMENTS.get(t, ""),
            "row_count": row_count,
        })
    return ok(result)


@router.get("/tables/{table_name}/schema")
def table_schema(table_name: str, db: Session = Depends(get_db)):
    """获取表结构：列定义、主键、外键。"""
    insp = inspect(db.bind)
    if table_name not in insp.get_table_names():
        return {"success": False, "error": f"表 {table_name} 不存在", "data": None}

    columns = []
    col_comments = COLUMN_COMMENTS.get(table_name, {})
    for col in insp.get_columns(table_name):
        columns.append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "default": str(col["default"]) if col.get("default") is not None else None,
            "primary_key": False,  # filled below
            "comment": col_comments.get(col["name"], ""),
        })

    # 主键
    pk = insp.get_pk_constraint(table_name)
    pk_cols = set(pk.get("constrained_columns", []))
    for c in columns:
        c["primary_key"] = c["name"] in pk_cols

    # 外键
    fks = []
    for fk in insp.get_foreign_keys(table_name):
        fks.append({
            "constrained_columns": fk["constrained_columns"],
            "referred_table": fk["referred_table"],
            "referred_columns": fk["referred_columns"],
        })

    # 索引
    indexes = []
    for idx in insp.get_indexes(table_name):
        indexes.append({
            "name": idx["name"],
            "columns": idx["column_names"],
            "unique": idx.get("unique", False),
        })

    return ok({
        "table_name": table_name,
        "comment": TABLE_COMMENTS.get(table_name, ""),
        "columns": columns,
        "primary_key": list(pk_cols),
        "foreign_keys": fks,
        "indexes": indexes,
    })


@router.get("/tables/{table_name}/data")
def table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """分页预览表数据。"""
    insp = inspect(db.bind)
    if table_name not in insp.get_table_names():
        return {"success": False, "error": f"表 {table_name} 不存在", "data": None}

    total = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
    offset = (page - 1) * page_size
    rows = db.execute(
        text(f'SELECT * FROM "{table_name}" LIMIT :limit OFFSET :offset'),
        {"limit": page_size, "offset": offset},
    )
    columns = list(rows.keys())
    data = [dict(zip(columns, row)) for row in rows.fetchall()]

    return ok(data, meta={
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "columns": columns,
    })
