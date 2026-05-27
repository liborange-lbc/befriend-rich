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
    """每天运行：
    1. 本周缺失的 (fund_id, channel) → 从上周递延（携带 data_date）
    2. 本周已递延但上周 data_date 更新 → 重新递延一次（覆盖金额和 data_date）
    """
    from datetime import date, timedelta

    from app.models.portfolio import PortfolioRecord

    logger.info("Running weekly data completion job")
    db = SessionLocal()
    try:
        today = date.today()
        this_monday = today - timedelta(days=today.weekday())
        prev_monday = this_monday - timedelta(days=7)

        # 上周记录，按 (fund_id, channel) 索引；同一对取 data_date 最新的
        prev_map: dict[tuple, PortfolioRecord] = {}
        for r in (
            db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == prev_monday)
            .all()
        ):
            key = (r.fund_id, r.channel)
            existing = prev_map.get(key)
            if existing is None or (r.data_date or "") > (existing.data_date or ""):
                prev_map[key] = r

        # 本周记录，按 (fund_id, channel) 索引
        this_map: dict[tuple, PortfolioRecord] = {
            (r.fund_id, r.channel): r
            for r in (
                db.query(PortfolioRecord)
                .filter(PortfolioRecord.record_date == this_monday)
                .all()
            )
        }

        filled = 0
        refreshed = 0
        for key, pr in prev_map.items():
            this_rec = this_map.get(key)
            if this_rec is None:
                # 本周缺失 → 新建递延记录
                db.add(PortfolioRecord(
                    openid=pr.openid,
                    fund_id=pr.fund_id,
                    record_date=this_monday,
                    channel=pr.channel,
                    amount=pr.amount,
                    amount_cny=pr.amount_cny,
                    profit=pr.profit,
                    weekly_investment=None,
                    data_date=pr.data_date,
                ))
                filled += 1
            elif (pr.data_date or "") > (this_rec.data_date or ""):
                # 上周 data_date 更新 → 重新递延，覆盖本周已有记录
                this_rec.amount = pr.amount
                this_rec.amount_cny = pr.amount_cny
                this_rec.profit = pr.profit
                this_rec.data_date = pr.data_date
                refreshed += 1

        if filled or refreshed:
            db.commit()
            from app.services.portfolio.snapshot import generate_snapshot
            generate_snapshot(db, this_monday)

        logger.info(
            f"Weekly data completion: filled={filled}, refreshed={refreshed} "
            f"for {this_monday}"
        )
        return f"filled={filled} refreshed={refreshed}"
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
                PortfolioRecord.channel == "支付宝-闪闪",
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


@_record_run("alipay1_auto_import")
def job_alipay1_auto_import():
    """每天 9:15 自动从第二个邮箱拉取支付宝-1基金对账单"""
    logger.info("Running Alipay-1 auto import job")
    db = SessionLocal()
    try:
        from app.models.portfolio import PortfolioRecord
        from app.services.alipay.email_puller import pull_alipay1_statements

        results = pull_alipay1_statements(db)
        if not results:
            logger.info("Alipay-1 auto import: nothing new to import")
            return "无新数据"

        total_records = sum(r.records_imported for r in results)

        latest_log_id = results[-1].import_log_id
        from app.models.import_log import ImportLog
        latest_log = db.query(ImportLog).get(latest_log_id)
        latest_date = latest_log.import_date if latest_log else None

        total_amount = 0.0
        if latest_date:
            rows = db.query(PortfolioRecord).filter(
                PortfolioRecord.record_date == latest_date,
                PortfolioRecord.channel == "支付宝-左川",
            ).all()
            total_amount = sum(r.amount_cny for r in rows)

        summary = (
            f"导入{len(results)}周, 共{total_records}条"
            f" | 最新: {latest_date}"
            f" | 总资产: {total_amount:,.0f}元"
        )
        logger.info(f"Alipay-1 auto import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Alipay-1 auto import failed: {e}")
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


@_record_run("sync_watch_activities")
def job_sync_watch_activities():
    """每天 06:00 同步所有运动手表活动数据"""
    logger.info("Running watch activity sync job")
    try:
        from app.services.watch.sync_service import sync_all_connections

        results = sync_all_connections(days=2)
        total = sum(r["synced"] for r in results)
        logger.info(f"Watch sync completed: {total} activities from {len(results)} connections")
        return f"{total} activities synced"
    except Exception as e:
        logger.error(f"Watch activity sync failed: {e}")


@_record_run("us_stock_trend_fetch")
def job_us_stock_trend_fetch():
    """每天 6:00 (北京时间) 获取美股交易额 Top30（美股收盘后）"""
    logger.info("Running US stock trend fetch job")
    db = SessionLocal()
    try:
        from app.services.us_stock_trend import fetch_and_store_top30

        result = fetch_and_store_top30(db)
        logger.info(f"US stock trend fetch completed: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"US stock trend fetch failed: {e}")
    finally:
        db.close()


@_record_run("futu_auto_import")
def job_futu_auto_import():
    """每天 9:20 自动从邮件拉取富途日结单持仓"""
    logger.info("Running Futu email import job")
    db = SessionLocal()
    try:
        from app.services.futu.email_puller import pull_futu_email_statement

        result = pull_futu_email_statement(db)
        summary = f"导入{result.records_imported}条 | 新基金{result.new_funds_created}"
        logger.info(f"Futu email import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Futu email import failed: {e}")
        raise
    finally:
        db.close()


@_record_run("longbridge_auto_import")
def job_longbridge_auto_import():
    """每天 9:10 自动从邮件拉取长桥日结对账单持仓"""
    logger.info("Running Longbridge email import job")
    db = SessionLocal()
    try:
        from app.services.longbridge.email_puller import pull_longbridge_email_statement

        result = pull_longbridge_email_statement(db)
        summary = f"导入{result.records_imported}条 | 新基金{result.new_funds_created}"
        logger.info(f"Longbridge email import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Longbridge email import failed: {e}")
        raise
    finally:
        db.close()


@_record_run("gtht_auto_import")
def job_gtht_auto_import():
    """每天 05:00 自动从邮箱拉取国泰海通客户资产证明，写入各持仓明细"""
    logger.info("Running GTHT auto import job")
    db = SessionLocal()
    try:
        from app.services.gtht.email_puller import pull_gtht_statement

        results = pull_gtht_statement(db)
        if not results:
            logger.info("GTHT auto import: no new data")
            return "无新数据"
        total_records = sum(r.records_imported for r in results)
        summary = f"导入{len(results)}批次, 共{total_records}条"
        logger.info(f"GTHT auto import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"GTHT auto import failed: {e}")
        raise
    finally:
        db.close()


@_record_run("eastmoney_auto_import")
def job_eastmoney_auto_import():
    """每周二 9:35 自动从邮箱拉取东方财富股份持有证明，写入各证券持仓"""
    logger.info("Running Eastmoney auto import job")
    db = SessionLocal()
    try:
        from app.services.eastmoney.email_puller import pull_eastmoney_statement

        result = pull_eastmoney_statement(db)
        if result is None:
            logger.info("Eastmoney auto import: no new data this week")
            return "无新数据"
        summary = f"导入{result.records_imported}条 | 新基金{result.new_funds_created}"
        logger.info(f"Eastmoney auto import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Eastmoney auto import failed: {e}")
        raise
    finally:
        db.close()


@_record_run("xuqiu_auto_import")
def job_xuqiu_auto_import():
    """每周二 9:30 自动从邮箱拉取雪球基金资产证明，写入有知有行持仓"""
    logger.info("Running Xuqiu auto import job")
    db = SessionLocal()
    try:
        from app.services.xuqiu.email_puller import pull_xuqiu_statement

        result = pull_xuqiu_statement(db)
        if result is None:
            logger.info("Xuqiu auto import: no new data this week")
            return "无新数据"
        summary = f"导入1条 | 总资产: {result.records_imported}条 | 新基金{result.new_funds_created}"
        logger.info(f"Xuqiu auto import completed: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Xuqiu auto import failed: {e}")
        raise
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
