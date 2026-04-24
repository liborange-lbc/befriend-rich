"""Tests for rebalancing feature."""

from datetime import date, timedelta

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord
from app.models.rebalance import RebalanceTarget


def _seed_model_and_categories(db) -> tuple:
    model = ClassModel(name="良田模型", description="")
    db.add(model)
    db.commit()
    db.refresh(model)

    c1 = ClassCategory(model_id=model.id, name="大盘价值", level=1, sort_order=1)
    c2 = ClassCategory(model_id=model.id, name="中小成长", level=1, sort_order=2)
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    return model, c1, c2


def _seed_fund(db, code: str, name: str) -> Fund:
    fund = Fund(code=code, name=name, currency="CNY", data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


class TestTargets:
    def test_set_and_get_targets(self, client, db_session):
        model, c1, c2 = _seed_model_and_categories(db_session)

        # Set targets
        resp = client.post("/api/v1/rebalance/targets", json={
            "targets": [
                {"category_id": c1.id, "target_pct": 60.0},
                {"category_id": c2.id, "target_pct": 40.0},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["updated"] == 2

        # Get targets
        resp = client.get("/api/v1/rebalance/targets")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        targets_map = {d["category_name"]: d["target_pct"] for d in data}
        assert targets_map["大盘价值"] == 60.0
        assert targets_map["中小成长"] == 40.0


class TestAnalysis:
    def test_rebalance_analysis(self, client, db_session):
        model, c1, c2 = _seed_model_and_categories(db_session)

        f1 = _seed_fund(db_session, "510300", "沪深300ETF")
        f2 = _seed_fund(db_session, "510500", "中证500ETF")

        # Map funds
        db_session.add(FundClassMap(fund_id=f1.id, category_id=c1.id, model_id=model.id))
        db_session.add(FundClassMap(fund_id=f2.id, category_id=c2.id, model_id=model.id))
        db_session.commit()

        # Set targets: 60/40
        db_session.add(RebalanceTarget(model_id=model.id, category_id=c1.id, target_pct=60.0))
        db_session.add(RebalanceTarget(model_id=model.id, category_id=c2.id, target_pct=40.0))
        db_session.commit()

        # Add portfolio: 70/30 (drifted from target)
        today = date.today() - timedelta(days=date.today().weekday())
        db_session.add(PortfolioRecord(fund_id=f1.id, record_date=today, amount=7000, amount_cny=7000, channel="微众银行"))
        db_session.add(PortfolioRecord(fund_id=f2.id, record_date=today, amount=3000, amount_cny=3000, channel="微众银行"))
        db_session.commit()

        resp = client.get("/api/v1/rebalance/analysis")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_value"] == 10000
        assert len(data["categories"]) == 2

        # Find 大盘价值: actual 70%, target 60%, drift +10%
        cat1 = next(c for c in data["categories"] if c["category_name"] == "大盘价值")
        assert abs(cat1["actual_pct"] - 70.0) < 0.1
        assert cat1["target_pct"] == 60.0
        assert abs(cat1["drift"] - 10.0) < 0.1
        assert cat1["action"] == "卖出"  # need to sell

        # Find 中小成长: actual 30%, target 40%, drift -10%
        cat2 = next(c for c in data["categories"] if c["category_name"] == "中小成长")
        assert cat2["action"] == "买入"

    def test_empty_portfolio(self, client, db_session):
        resp = client.get("/api/v1/rebalance/analysis")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_value"] == 0
