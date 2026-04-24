"""Tests for the data health monitoring feature."""

from datetime import date, datetime, timedelta

from app.models.fund import Fund
from app.models.price import FundDailyPrice
from app.models.scheduler import JobRun


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_job_run(db, job_id: str, status: str, hours_ago: float = 0) -> JobRun:
    started = datetime.now() - timedelta(hours=hours_ago)
    run = JobRun(
        job_id=job_id,
        started_at=started,
        finished_at=started + timedelta(seconds=5),
        status=status,
        summary="OK" if status == "success" else "Error",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _seed_price(db, fund_id: int, days_ago: int) -> FundDailyPrice:
    price = FundDailyPrice(
        fund_id=fund_id,
        date=date.today() - timedelta(days=days_ago),
        close_price=1.5,
    )
    db.add(price)
    db.commit()
    return price


class TestDataHealthOverview:
    def test_overview_healthy_job(self, client, db_session):
        _seed_job_run(db_session, "fetch_market_data", "success", hours_ago=1)
        resp = client.get("/api/v1/data-health/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        market_job = next(j for j in data if j["job_id"] == "fetch_market_data")
        assert market_job["status"] == "healthy"

    def test_overview_warning_job(self, client, db_session):
        # fetch_market_data has max_hours=2, so 3 hours ago = warning
        _seed_job_run(db_session, "fetch_market_data", "success", hours_ago=3)
        resp = client.get("/api/v1/data-health/overview")
        data = resp.json()["data"]
        market_job = next(j for j in data if j["job_id"] == "fetch_market_data")
        assert market_job["status"] == "warning"

    def test_overview_error_job(self, client, db_session):
        _seed_job_run(db_session, "fetch_market_data", "failed", hours_ago=0)
        resp = client.get("/api/v1/data-health/overview")
        data = resp.json()["data"]
        market_job = next(j for j in data if j["job_id"] == "fetch_market_data")
        assert market_job["status"] == "error"

    def test_overview_unknown_job(self, client, db_session):
        # No runs at all
        resp = client.get("/api/v1/data-health/overview")
        data = resp.json()["data"]
        market_job = next(j for j in data if j["job_id"] == "fetch_market_data")
        assert market_job["status"] == "unknown"


class TestFundCoverage:
    def test_healthy_fund(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        _seed_price(db_session, fund.id, days_ago=1)
        resp = client.get("/api/v1/data-health/fund-coverage")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["status"] == "healthy"
        assert data[0]["gap_days"] == 1

    def test_warning_fund(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        _seed_price(db_session, fund.id, days_ago=5)
        resp = client.get("/api/v1/data-health/fund-coverage")
        data = resp.json()["data"]
        assert data[0]["status"] == "warning"

    def test_error_fund_no_data(self, client, db_session):
        _seed_fund(db_session, "510300", "沪深300ETF")
        resp = client.get("/api/v1/data-health/fund-coverage")
        data = resp.json()["data"]
        assert data[0]["status"] == "error"
        assert data[0]["gap_days"] is None

    def test_error_fund_stale(self, client, db_session):
        fund = _seed_fund(db_session, "510300", "沪深300ETF")
        _seed_price(db_session, fund.id, days_ago=10)
        resp = client.get("/api/v1/data-health/fund-coverage")
        data = resp.json()["data"]
        assert data[0]["status"] == "error"


class TestJobHistory:
    def test_job_history(self, client, db_session):
        _seed_job_run(db_session, "fetch_market_data", "success", hours_ago=1)
        _seed_job_run(db_session, "fetch_market_data", "failed", hours_ago=0)
        resp = client.get("/api/v1/data-health/job-history")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # Most recent first
        assert data[0]["status"] == "failed"
        assert data[1]["status"] == "success"
        assert data[0]["duration_s"] is not None
