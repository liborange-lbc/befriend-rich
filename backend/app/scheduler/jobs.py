import logging
from datetime import datetime
from functools import wraps

from app.database import SessionLocal
from app.services.market_data.exchange_rate import fetch_and_store_all_rates
from app.services.market_data.fetcher import fetch_all_active_funds
from app.services.strategy.evaluator import run_strategy_check

logger = logging.getLogger(__name__)


def _record_run(job_id: str):
    """Decorator to record job execution in job_runs table."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from app.models.scheduler import JobRun
            db = SessionLocal()
            run = JobRun(job_id=job_id, started_at=datetime.now(), status="running")
            try:
                db.add(run)
                db.commit()
                db.refresh(run)
                result = func(*args, **kwargs)
                run.status = "success"
                run.summary = str(result) if result else "OK"
                run.finished_at = datetime.now()
                db.commit()
                return result
            except Exception as e:
                run.status = "failed"
                run.summary = str(e)[:500]
                run.finished_at = datetime.now()
                db.commit()
                raise
            finally:
                db.close()
        return wrapper
    return decorator


@_record_run("fetch_market_data")
def job_fetch_market_data():
    logger.info("Running market data fetch job")
    db = SessionLocal()
    try:
        fetch_all_active_funds(db)
        fetch_and_store_all_rates(db)
        # 自动补偿异常数据，修复失败则调用 AI 诊断
        from app.services.data_health_service import repair_fund_coverage
        repairs = repair_fund_coverage(db)
        if repairs:
            repaired = sum(1 for r in repairs if r["status"] == "repaired")
            failed = sum(1 for r in repairs if r["status"] != "repaired")
            logger.info(f"Auto-repair: {repaired}/{len(repairs)} funds fixed")
            if failed > 0:
                try:
                    from app.services.ai_repair_service import ai_diagnose_and_repair
                    ai_result = ai_diagnose_and_repair(db)
                    logger.info(f"AI diagnose: {ai_result.get('diagnosis', '')[:200]}")
                except Exception as ai_err:
                    logger.warning(f"AI diagnose skipped: {ai_err}")
    except Exception as e:
        logger.error(f"Market data fetch job failed: {e}")
    finally:
        db.close()


@_record_run("strategy_check")
def job_strategy_check():
    logger.info("Running strategy check job")
    db = SessionLocal()
    try:
        run_strategy_check(db)
    except Exception as e:
        logger.error(f"Strategy check job failed: {e}")
    finally:
        db.close()


@_record_run("webank_auto_import")
def job_webank_auto_import():
    """每天 9:00 自动从邮箱拉取微众银行对账单"""
    logger.info("Running WeBank auto import job")
    db = SessionLocal()
    try:
        from app.services.webank.email_puller import pull_latest_statement

        result = pull_latest_statement(db)
        logger.info(f"WeBank auto import completed: {result}")
    except Exception as e:
        logger.error(f"WeBank auto import failed: {e}")
    finally:
        db.close()


@_record_run("weekly_data_completion")
def job_weekly_data_completion():
    """每天运行，将本周缺失的持仓数据用上周数据补全。"""
    from datetime import date, timedelta

    from app.models.portfolio import PortfolioRecord

    logger.info("Running weekly data completion job")
    db = SessionLocal()
    try:
        today = date.today()
        # 本周一
        this_monday = today - timedelta(days=today.weekday())
        # 上周一
        prev_monday = this_monday - timedelta(days=7)

        # 上周有记录的 (fund_id, channel)
        prev_records = (
            db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == prev_monday)
            .all()
        )
        # 本周已有记录的 (fund_id, channel)
        existing_this_week = set(
            (r.fund_id, r.channel)
            for r in db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == this_monday)
            .all()
        )

        filled = 0
        for pr in prev_records:
            if (pr.fund_id, pr.channel) not in existing_this_week:
                db.add(PortfolioRecord(
                    fund_id=pr.fund_id,
                    record_date=this_monday,
                    channel=pr.channel,
                    amount=pr.amount,
                    amount_cny=pr.amount_cny,
                    profit=pr.profit,
                    weekly_investment=None,
                ))
                filled += 1

        if filled:
            db.commit()
            from app.services.portfolio.snapshot import generate_snapshot
            generate_snapshot(db, this_monday)

        logger.info(f"Weekly data completion: filled {filled} records for {this_monday}")
    except Exception as e:
        logger.error(f"Weekly data completion failed: {e}")
    finally:
        db.close()


@_record_run("fetch_fund_holdings")
def job_fetch_fund_holdings():
    """每月1日 10:00 抓取基金持仓数据（检查新的季度披露）"""
    logger.info("Running fund holdings fetch job")
    db = SessionLocal()
    try:
        from app.services.fund_holding_service import fetch_holdings_for_all_funds

        result = fetch_holdings_for_all_funds(db)
        logger.info(f"Fund holdings fetch completed: {result}")
    except Exception as e:
        logger.error(f"Fund holdings fetch failed: {e}")
    finally:
        db.close()


@_record_run("refresh_market_insight")
def job_refresh_market_insight():
    """每周一 8:30 刷新大盘洞察数据"""
    logger.info("Running market insight refresh job")
    db = SessionLocal()
    try:
        from app.services.market_insight.grid import refresh_market_data

        refresh_market_data(db)
    except Exception as e:
        logger.error(f"Market insight refresh failed: {e}")
    finally:
        db.close()


@_record_run("auto_backup")
def job_auto_backup():
    """每天凌晨 2:00 自动备份数据库"""
    logger.info("Running auto backup job")
    try:
        from app.services.backup_service import cleanup_old_backups, create_backup

        result = create_backup()
        cleanup_old_backups(30)
        logger.info(f"Auto backup completed: {result['filename']}")
    except Exception as e:
        logger.error(f"Auto backup failed: {e}")


@_record_run("alipay_auto_import")
def job_alipay_auto_import():
    """每天 9:05 自动从邮箱拉取支付宝基金对账单"""
    logger.info("Running Alipay auto import job")
    db = SessionLocal()
    try:
        from app.models.portfolio import PortfolioRecord
        from app.services.alipay.email_puller import pull_alipay_statements

        results = pull_alipay_statements(db)
        if not results:
            logger.info("Alipay auto import: nothing new to import")
            return "无新数据"

        total_records = sum(r.records_imported for r in results)

        # 查最新一周的支付宝总资产
        latest_log_id = results[-1].import_log_id
        from app.models.import_log import ImportLog
        latest_log = db.query(ImportLog).get(latest_log_id)
        latest_date = latest_log.import_date if latest_log else None

        total_amount = 0.0
        if latest_date:
            rows = db.query(PortfolioRecord).filter(
                PortfolioRecord.record_date == latest_date,
                PortfolioRecord.channel == "支付宝",
            ).all()
            total_amount = sum(r.amount_cny for r in rows)

        summary = (
            f"导入{len(results)}周, 共{total_records}条"
            f" | 最新: {latest_date}"
            f" | 总资产: {total_amount:,.0f}元"
        )
        logger.info(f"Alipay auto import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Alipay auto import failed: {e}")
        raise
    finally:
        db.close()


@_record_run("allocation_recalculate")
def job_allocation_recalculate():
    """季度初（1/4/7/10月1日）09:00 重新计算良田模型配置"""
    logger.info("Running allocation recalculation job")
    db = SessionLocal()
    try:
        from app.services.allocation_engine import calculate_optimal_allocation

        result = calculate_optimal_allocation(db, model_id=1, trigger="quarterly")
        logger.info(f"Allocation recalculated: {len(result.get('targets', []))} categories")
        return f"{len(result.get('targets', []))} categories recalculated"
    except Exception as e:
        logger.error(f"Allocation recalculation failed: {e}")
    finally:
        db.close()


@_record_run("ic_option_fetch")
def job_ic_option_fetch():
    """每天 15:30 获取IC期权最近7天数据（补漏+更新当天）"""
    logger.info("Running IC option data fetch job")
    db = SessionLocal()
    try:
        from app.services.ic_option_service import fetch_and_store

        result = fetch_and_store(db, days=7)
        logger.info(f"IC option fetch completed: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"IC option fetch failed: {e}")
    finally:
        db.close()


@_record_run("guru_holdings_update")
def job_guru_holdings_update():
    """每月5日 10:30 从官方披露网站更新价值大师持仓数据"""
    logger.info("Running guru holdings update job")
    db = SessionLocal()
    try:
        from app.services.guru.updater import update_all_guru_holdings

        result = update_all_guru_holdings(db)
        logger.info(f"Guru holdings update completed: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"Guru holdings update failed: {e}")
    finally:
        db.close()
