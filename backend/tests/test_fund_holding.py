"""Tests for the Fund X-ray (基金透视) feature."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.models.fund import Fund
from app.models.fund_holding import FundHolding
from app.models.portfolio import PortfolioRecord
from app.services.fund_holding_service import (
    get_available_quarters,
    get_fund_holdings,
    get_stock_exposure,
    parse_quarter,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _seed_fund(db, code: str = "005918", name: str = "天弘沪深300") -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="akshare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_holdings(db, fund: Fund, quarter: str = "2024Q4") -> list[FundHolding]:
    rows = [
        FundHolding(
            fund_id=fund.id, quarter=quarter, stock_code="600519",
            stock_name="贵州茅台", holding_ratio=8.5, holding_shares=100.0,
            holding_value=5000.0, disclosure_date=f"{quarter[:4]}年{quarter[-1]}季度报告",
        ),
        FundHolding(
            fund_id=fund.id, quarter=quarter, stock_code="000858",
            stock_name="五粮液", holding_ratio=5.2, holding_shares=200.0,
            holding_value=3000.0, disclosure_date=f"{quarter[:4]}年{quarter[-1]}季度报告",
        ),
    ]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def _seed_portfolio_record(db, fund: Fund, amount_cny: float = 100000.0) -> PortfolioRecord:
    record = PortfolioRecord(
        fund_id=fund.id, record_date=date(2024, 12, 30), amount=amount_cny,
        amount_cny=amount_cny, channel="微众银行",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── Unit Tests: parse_quarter ────────────────────────────────────────────


class TestParseQuarter:
    def test_standard_format(self):
        assert parse_quarter("2024年4季度报告") == "2024Q4"
        assert parse_quarter("2024年1季度报告") == "2024Q1"
        assert parse_quarter("2023年2季度报告") == "2023Q2"
        assert parse_quarter("2023年3季度报告") == "2023Q3"

    def test_unknown_format_returns_raw(self):
        assert parse_quarter("unknown") == "unknown"


# ── Unit Tests: get_fund_holdings ────────────────────────────────────────


class TestGetFundHoldings:
    def test_returns_latest_quarter_by_default(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q3")
        _seed_holdings(db_session, fund, "2024Q4")

        holdings = get_fund_holdings(db_session, fund.id)
        assert len(holdings) == 2
        assert all(h.quarter == "2024Q4" for h in holdings)

    def test_filter_by_quarter(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q3")
        _seed_holdings(db_session, fund, "2024Q4")

        holdings = get_fund_holdings(db_session, fund.id, "2024Q3")
        assert len(holdings) == 2
        assert all(h.quarter == "2024Q3" for h in holdings)

    def test_empty_when_no_data(self, db_session):
        fund = _seed_fund(db_session)
        holdings = get_fund_holdings(db_session, fund.id)
        assert holdings == []


# ── Unit Tests: get_available_quarters ───────────────────────────────────


class TestGetAvailableQuarters:
    def test_returns_quarters_desc(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q2")
        _seed_holdings(db_session, fund, "2024Q4")

        quarters = get_available_quarters(db_session, fund.id)
        assert quarters == ["2024Q4", "2024Q2"]

    def test_all_funds_quarters(self, db_session):
        f1 = _seed_fund(db_session, "005918", "Fund A")
        f2 = _seed_fund(db_session, "110011", "Fund B")
        _seed_holdings(db_session, f1, "2024Q4")
        _seed_holdings(db_session, f2, "2024Q3")

        quarters = get_available_quarters(db_session)
        assert set(quarters) == {"2024Q4", "2024Q3"}


# ── Unit Tests: get_stock_exposure ───────────────────────────────────────


class TestGetStockExposure:
    def test_exposure_calculation(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")
        _seed_portfolio_record(db_session, fund, 100000.0)

        exposure = get_stock_exposure(db_session)
        assert len(exposure) == 2

        # 贵州茅台: 100000 * 8.5% = 8500
        maotai = next(e for e in exposure if e["stock_code"] == "600519")
        assert maotai["total_exposure_cny"] == 8500.0
        assert maotai["stock_name"] == "贵州茅台"
        assert len(maotai["funds"]) == 1
        assert maotai["funds"][0]["exposure_cny"] == 8500.0

        # 五粮液: 100000 * 5.2% = 5200
        wuliangye = next(e for e in exposure if e["stock_code"] == "000858")
        assert wuliangye["total_exposure_cny"] == 5200.0

    def test_exposure_sorted_desc(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")
        _seed_portfolio_record(db_session, fund, 100000.0)

        exposure = get_stock_exposure(db_session)
        assert exposure[0]["total_exposure_cny"] >= exposure[1]["total_exposure_cny"]

    def test_exposure_empty_when_no_positions(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")
        # No portfolio records
        exposure = get_stock_exposure(db_session)
        assert exposure == []

    def test_exposure_with_target_date(self, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")
        _seed_portfolio_record(db_session, fund, 50000.0)

        exposure = get_stock_exposure(db_session, date(2024, 12, 30))
        assert len(exposure) == 2
        maotai = next(e for e in exposure if e["stock_code"] == "600519")
        assert maotai["total_exposure_cny"] == 4250.0  # 50000 * 8.5%

    def test_exposure_aggregates_across_funds(self, db_session):
        f1 = _seed_fund(db_session, "005918", "Fund A")
        f2 = _seed_fund(db_session, "110011", "Fund B")
        # Both funds hold 贵州茅台
        db_session.add(FundHolding(
            fund_id=f1.id, quarter="2024Q4", stock_code="600519",
            stock_name="贵州茅台", holding_ratio=8.0,
        ))
        db_session.add(FundHolding(
            fund_id=f2.id, quarter="2024Q4", stock_code="600519",
            stock_name="贵州茅台", holding_ratio=5.0,
        ))
        db_session.commit()

        # Fund A: 100k, Fund B: 200k
        db_session.add(PortfolioRecord(
            fund_id=f1.id, record_date=date(2024, 12, 30),
            amount=100000, amount_cny=100000, channel="微众银行",
        ))
        db_session.add(PortfolioRecord(
            fund_id=f2.id, record_date=date(2024, 12, 30),
            amount=200000, amount_cny=200000, channel="微众银行",
        ))
        db_session.commit()

        exposure = get_stock_exposure(db_session)
        maotai = next(e for e in exposure if e["stock_code"] == "600519")
        # 100000 * 8% + 200000 * 5% = 8000 + 10000 = 18000
        assert maotai["total_exposure_cny"] == 18000.0
        assert len(maotai["funds"]) == 2


# ── Unit Tests: fetch_holdings_for_fund (mocked akshare) ─────────────────


class TestFetchHoldings:
    @patch("app.services.fund_holding_service.ak", create=True)
    def test_fetch_and_upsert(self, mock_ak_module, db_session):
        from app.services.fund_holding_service import fetch_holdings_for_fund

        fund = _seed_fund(db_session)

        mock_df = pd.DataFrame({
            "序号": [1, 2],
            "股票代码": ["600519", "000858"],
            "股票名称": ["贵州茅台", "五粮液"],
            "占净值比例": [8.5, 5.2],
            "持仓股数": [100.0, 200.0],
            "持仓市值": [5000.0, 3000.0],
            "季度": ["2024年4季度报告", "2024年4季度报告"],
        })
        mock_ak_module.fund_portfolio_hold_em.return_value = mock_df

        count = fetch_holdings_for_fund(db_session, fund, 2024)
        assert count == 2

        holdings = db_session.query(FundHolding).filter(FundHolding.fund_id == fund.id).all()
        assert len(holdings) == 2

    @patch("app.services.fund_holding_service.ak", create=True)
    def test_upsert_updates_existing(self, mock_ak_module, db_session):
        from app.services.fund_holding_service import fetch_holdings_for_fund

        fund = _seed_fund(db_session)

        mock_df = pd.DataFrame({
            "序号": [1],
            "股票代码": ["600519"],
            "股票名称": ["贵州茅台"],
            "占净值比例": [8.5],
            "持仓股数": [100.0],
            "持仓市值": [5000.0],
            "季度": ["2024年4季度报告"],
        })
        mock_ak_module.fund_portfolio_hold_em.return_value = mock_df

        fetch_holdings_for_fund(db_session, fund, 2024)

        # Update the ratio
        mock_df_updated = mock_df.copy()
        mock_df_updated["占净值比例"] = [9.0]
        mock_ak_module.fund_portfolio_hold_em.return_value = mock_df_updated

        fetch_holdings_for_fund(db_session, fund, 2024)

        holdings = db_session.query(FundHolding).filter(FundHolding.fund_id == fund.id).all()
        assert len(holdings) == 1
        assert holdings[0].holding_ratio == 9.0

    @patch("app.services.fund_holding_service.ak", create=True)
    def test_strips_fund_code_suffix(self, mock_ak_module, db_session):
        from app.services.fund_holding_service import fetch_holdings_for_fund

        fund = _seed_fund(db_session, code="005918.OF")
        mock_ak_module.fund_portfolio_hold_em.return_value = pd.DataFrame()

        fetch_holdings_for_fund(db_session, fund, 2024)

        mock_ak_module.fund_portfolio_hold_em.assert_called_once_with(
            symbol="005918", year="2024"
        )


# ── API Endpoint Tests ───────────────────────────────────────────────────


class TestFundHoldingAPI:
    def test_get_holdings_empty(self, client):
        resp = client.get("/api/v1/fund-xray/holdings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

    def test_get_holdings_with_data(self, client, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")

        resp = client.get("/api/v1/fund-xray/holdings", params={"fund_id": fund.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["fund_code"] == "005918"
        assert data["data"][0]["fund_name"] == "天弘沪深300"

    def test_get_holdings_filter_quarter(self, client, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q3")
        _seed_holdings(db_session, fund, "2024Q4")

        resp = client.get("/api/v1/fund-xray/holdings", params={"fund_id": fund.id, "quarter": "2024Q3"})
        data = resp.json()
        assert len(data["data"]) == 2
        assert all(h["quarter"] == "2024Q3" for h in data["data"])

    def test_get_quarters(self, client, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q3")
        _seed_holdings(db_session, fund, "2024Q4")

        resp = client.get("/api/v1/fund-xray/holdings/quarters", params={"fund_id": fund.id})
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == ["2024Q4", "2024Q3"]

    def test_get_exposure(self, client, db_session):
        fund = _seed_fund(db_session)
        _seed_holdings(db_session, fund, "2024Q4")
        _seed_portfolio_record(db_session, fund, 100000.0)

        resp = client.get("/api/v1/fund-xray/exposure")
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["stock_code"] == "600519"
        assert data["data"][0]["total_exposure_cny"] == 8500.0

    @patch("app.services.fund_holding_service.ak", create=True)
    def test_trigger_fetch(self, mock_ak_module, client, db_session):
        fund = _seed_fund(db_session)
        mock_ak_module.fund_portfolio_hold_em.return_value = pd.DataFrame({
            "序号": [1],
            "股票代码": ["600519"],
            "股票名称": ["贵州茅台"],
            "占净值比例": [8.5],
            "持仓股数": [100.0],
            "持仓市值": [5000.0],
            "季度": ["2024年4季度报告"],
        })

        resp = client.post("/api/v1/fund-xray/fetch", params={"fund_id": fund.id})
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["fetched_count"] == 1
