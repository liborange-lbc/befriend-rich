"""Tests for the WeBank asset import feature."""

from datetime import date
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.config import SystemConfig
from app.models.fund import Fund
from app.models.import_log import ImportLog
from app.models.portfolio import PortfolioRecord


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_excel(rows: list[tuple[str, float, str]]) -> bytes:
    """Create a minimal WeBank-style xlsx file in memory."""
    wb = Workbook()
    ws = wb.active
    ws.title = "资产概览"
    ws.append(["资产项", "金额(元)", "币种"])
    for name, amount, currency in rows:
        ws.append([name, amount, currency])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _seed_fund(db, code: str, name: str, currency: str = "CNY") -> Fund:
    fund = Fund(code=code, name=name, currency=currency, data_source="tushare", is_active=True)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund


def _seed_config(db, key: str, value: str, category: str = "email"):
    db.add(SystemConfig(key=key, value=value, category=category, description=""))
    db.commit()


def _seed_classification(db) -> tuple[ClassModel, ClassCategory]:
    model = ClassModel(name="资产类别", description="")
    db.add(model)
    db.commit()
    db.refresh(model)
    cat = ClassCategory(model_id=model.id, name="权益", level=1, sort_order=0)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return model, cat


# ── POST /api/v1/import/upload ───────────────────────────────────────────


@patch("app.services.webank.fund_matcher.start_backfill")
@patch("app.services.webank.fund_matcher.lookup_fund_code_via_akshare", return_value=None)
@patch("app.services.portfolio.snapshot.generate_snapshot", return_value=None)
@patch("app.services.webank.classifier.classify_funds_with_ai", return_value={})
def test_upload_excel_success(mock_cls, mock_snap, mock_ak, mock_bf, client, db_session):
    """Normal upload: creates funds and portfolio records."""
    excel = _create_test_excel([
        ("天弘标普500", 10000.0, "CNY"),
        ("博时基金", 20000.0, "CNY"),
    ])
    resp = client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17"},
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["total_items"] == 2
    assert data["data"]["records_imported"] == 2
    assert data["data"]["new_funds_created"] == 2

    # Verify DB records
    records = db_session.query(PortfolioRecord).all()
    assert len(records) == 2

    logs = db_session.query(ImportLog).all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].record_count == 2


def test_upload_excel_wrong_format(client):
    """Upload non-xlsx file returns 400."""
    resp = client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17"},
        files={"file": ("test.csv", b"a,b,c", "text/csv")},
    )
    assert resp.status_code == 400
    assert "不支持的文件格式" in resp.json()["detail"]


@patch("app.services.webank.fund_matcher.start_backfill")
@patch("app.services.webank.fund_matcher.lookup_fund_code_via_akshare", return_value=None)
@patch("app.services.portfolio.snapshot.generate_snapshot", return_value=None)
@patch("app.services.webank.classifier.classify_funds_with_ai", return_value={})
def test_upload_excel_duplicate(mock_cls, mock_snap, mock_ak, mock_bf, client, db_session):
    """Duplicate import without force returns 409."""
    excel = _create_test_excel([("基金A", 10000.0, "CNY")])

    # First upload
    resp = client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17"},
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200

    # Second upload - duplicate
    excel2 = _create_test_excel([("基金A", 12000.0, "CNY")])
    resp = client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17"},
        files={"file": ("test2.xlsx", excel2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 409
    assert "已有导入记录" in resp.json()["detail"]


@patch("app.services.webank.fund_matcher.start_backfill")
@patch("app.services.webank.fund_matcher.lookup_fund_code_via_akshare", return_value=None)
@patch("app.services.portfolio.snapshot.generate_snapshot", return_value=None)
@patch("app.services.webank.classifier.classify_funds_with_ai", return_value={})
def test_upload_excel_force_overwrite(mock_cls, mock_snap, mock_ak, mock_bf, client, db_session):
    """Force overwrite replaces existing records."""
    excel = _create_test_excel([("基金A", 10000.0, "CNY")])
    client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17"},
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    excel2 = _create_test_excel([("基金A", 15000.0, "CNY")])
    resp = client.post(
        "/api/v1/import/upload",
        params={"record_date": "2026-04-17", "force": True},
        files={"file": ("test2.xlsx", excel2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["records_imported"] == 1


# ── POST /api/v1/import/pull-email ──────────────────────────────────────


def test_pull_email_no_credentials(client, db_session):
    """Pull email without IMAP credentials returns 400."""
    # Ensure empty credentials
    _seed_config(db_session, "imap_email", "")
    _seed_config(db_session, "imap_password", "")
    _seed_config(db_session, "imap_host", "imap.163.com")
    _seed_config(db_session, "webank_zip_password", "090391")

    resp = client.post("/api/v1/import/pull-email")
    assert resp.status_code == 400
    assert "邮箱凭据" in resp.json()["detail"]


# ── GET /api/v1/import/records ───────────────────────────────────────────


def test_list_records_empty(client):
    """Records endpoint returns empty list when no data."""
    resp = client.get("/api/v1/import/records")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []


def test_list_records_with_data(client, db_session):
    """Records endpoint returns records with fund info."""
    fund = _seed_fund(db_session, "510300", "沪深300ETF")
    db_session.add(PortfolioRecord(
        fund_id=fund.id,
        record_date=date(2026, 4, 17),
        amount=100000.0,
        amount_cny=100000.0,
        profit=5000.0,
    ))
    db_session.commit()

    resp = client.get("/api/v1/import/records")
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["fund_code"] == "510300"
    assert data["data"][0]["fund_name"] == "沪深300ETF"
    assert data["data"][0]["amount"] == 100000.0
    assert data["meta"]["total"] == 1


def test_list_records_grouped(client, db_session):
    """Records endpoint supports group_by parameter."""
    fund = _seed_fund(db_session, "510300", "沪深300ETF")
    db_session.add(PortfolioRecord(
        fund_id=fund.id, record_date=date(2026, 4, 17),
        amount=100000.0, amount_cny=100000.0, profit=5000.0,
    ))
    fund2 = _seed_fund(db_session, "QQQ", "纳斯达克100", "USD")
    db_session.add(PortfolioRecord(
        fund_id=fund2.id, record_date=date(2026, 4, 17),
        amount=50000.0, amount_cny=50000.0, profit=2000.0,
    ))
    db_session.commit()

    resp = client.get("/api/v1/import/records", params={"group_by": "currency"})
    data = resp.json()
    assert data["success"] is True
    assert "groups" in data["data"]
    assert "summary" in data["data"]
    assert len(data["data"]["groups"]) == 2
    assert data["data"]["summary"]["record_count"] == 2


def test_list_records_keyword_filter(client, db_session):
    """Records endpoint filters by keyword."""
    fund1 = _seed_fund(db_session, "510300", "沪深300ETF")
    fund2 = _seed_fund(db_session, "QQQ", "纳斯达克100")
    db_session.add(PortfolioRecord(
        fund_id=fund1.id, record_date=date(2026, 4, 17),
        amount=100000.0, amount_cny=100000.0, profit=0.0,
    ))
    db_session.add(PortfolioRecord(
        fund_id=fund2.id, record_date=date(2026, 4, 17),
        amount=50000.0, amount_cny=50000.0, profit=0.0,
    ))
    db_session.commit()

    resp = client.get("/api/v1/import/records", params={"keyword": "沪深"})
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["fund_code"] == "510300"


# ── GET /api/v1/import/logs ──────────────────────────────────────────────


def test_list_import_logs(client, db_session):
    """Logs endpoint returns import history."""
    db_session.add(ImportLog(
        import_date=date(2026, 4, 17),
        source="excel_upload",
        file_name="test.xlsx",
        record_count=10,
        new_funds_count=2,
        status="success",
    ))
    db_session.commit()

    resp = client.get("/api/v1/import/logs")
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["file_name"] == "test.xlsx"
    assert data["data"][0]["record_count"] == 10


# ── GET /api/v1/import/group-dimensions ──────────────────────────────────


def test_group_dimensions_default(client):
    """Group dimensions returns at least the 4 built-in dimensions."""
    resp = client.get("/api/v1/import/group-dimensions")
    data = resp.json()
    assert data["success"] is True
    keys = [d["key"] for d in data["data"]]
    assert "date" in keys
    assert "date_week" in keys
    assert "date_month" in keys
    assert "currency" in keys


def test_group_dimensions_with_models(client, db_session):
    """Group dimensions includes classification models."""
    model, _ = _seed_classification(db_session)
    resp = client.get("/api/v1/import/group-dimensions")
    data = resp.json()
    keys = [d["key"] for d in data["data"]]
    assert f"model_{model.id}" in keys


# ── fund_matcher unit tests ──────────────────────────────────────────────


def test_fund_matcher_exact_match(db_session):
    """match_fund_by_name finds exact match."""
    from app.services.webank.fund_matcher import match_fund_by_name

    fund = _seed_fund(db_session, "510300", "沪深300ETF")
    result = match_fund_by_name(db_session, "沪深300ETF")
    assert result is not None
    assert result.id == fund.id


def test_fund_matcher_normalized_match(db_session):
    """match_fund_by_name matches after normalizing brackets."""
    from app.services.webank.fund_matcher import match_fund_by_name

    _seed_fund(db_session, "005561", "天弘标普500(QDII-FOF)A")
    result = match_fund_by_name(db_session, "天弘标普500（QDII-FOF）A")
    assert result is not None
    assert result.code == "005561"


def test_fund_matcher_suffix_strip(db_session):
    """match_fund_by_name matches by stripping share suffix."""
    from app.services.webank.fund_matcher import match_fund_by_name

    _seed_fund(db_session, "005561", "天弘标普500A")
    result = match_fund_by_name(db_session, "天弘标普500B")
    assert result is not None
    assert result.code == "005561"


def test_fund_matcher_no_match(db_session):
    """match_fund_by_name returns None when no match."""
    from app.services.webank.fund_matcher import match_fund_by_name

    result = match_fund_by_name(db_session, "不存在的基金")
    assert result is None


@patch("app.services.webank.fund_matcher.start_backfill")
@patch("app.services.webank.fund_matcher.lookup_fund_code_via_akshare", return_value=None)
def test_find_or_create_fund_new(mock_ak, mock_bf, db_session):
    """find_or_create_fund creates new fund when not found."""
    from app.services.webank.fund_matcher import find_or_create_fund

    fund, is_new = find_or_create_fund(db_session, "全新基金A")
    assert is_new is True
    assert fund.is_active is False  # No AkShare match => inactive
    assert fund.code.startswith("X")


@patch("app.services.webank.fund_matcher.start_backfill")
@patch(
    "app.services.webank.fund_matcher.lookup_fund_code_via_akshare",
    return_value={"code": "005918", "name": "天弘标普500", "type": "QDII"},
)
def test_find_or_create_fund_akshare_match(mock_ak, mock_bf, db_session):
    """find_or_create_fund creates fund with AkShare code."""
    from app.services.webank.fund_matcher import find_or_create_fund

    fund, is_new = find_or_create_fund(db_session, "天弘标普500")
    assert is_new is True
    assert fund.code == "005918"
    assert fund.is_active is True
    mock_bf.assert_called_once()


# ── importer profit calculation ──────────────────────────────────────────


@patch("app.services.webank.fund_matcher.start_backfill")
@patch("app.services.webank.fund_matcher.lookup_fund_code_via_akshare", return_value=None)
@patch("app.services.portfolio.snapshot.generate_snapshot", return_value=None)
@patch("app.services.webank.classifier.classify_funds_with_ai", return_value={})
def test_profit_calculation(mock_cls, mock_snap, mock_ak, mock_bf, db_session):
    """Profit is calculated as difference from previous period."""
    from app.services.webank.importer import import_from_parsed_data

    # First import
    items = [{"资产项": "测试基金", "金额(元)": 10000.0, "币种": "CNY"}]
    result1 = import_from_parsed_data(
        db_session, items, "test1.xlsx", date(2026, 4, 10), source="excel_upload",
    )
    assert result1.records_imported == 1

    # Check profit = 0 for first import
    record1 = db_session.query(PortfolioRecord).filter(
        PortfolioRecord.record_date == date(2026, 4, 10)
    ).first()
    assert record1.profit == 0.0

    # Second import
    items2 = [{"资产项": "测试基金", "金额(元)": 12000.0, "币种": "CNY"}]
    result2 = import_from_parsed_data(
        db_session, items2, "test2.xlsx", date(2026, 4, 17), source="excel_upload",
    )
    assert result2.records_imported == 1

    # Check profit = 12000 - 10000 = 2000
    record2 = db_session.query(PortfolioRecord).filter(
        PortfolioRecord.record_date == date(2026, 4, 17)
    ).first()
    assert record2.profit == 2000.0


# ── config API password masking ──────────────────────────────────────────


def test_config_password_masked(client, db_session):
    """Config API masks sensitive values."""
    _seed_config(db_session, "imap_password", "my_secret_password")

    resp = client.get("/api/v1/config")
    data = resp.json()
    assert data["success"] is True

    password_config = next(
        (c for c in data["data"] if c["key"] == "imap_password"), None,
    )
    assert password_config is not None
    assert password_config["value"] == "******"


def test_config_masked_value_not_updated(client, db_session):
    """PUT config skips masked values (user did not change them)."""
    _seed_config(db_session, "imap_password", "original_password")
    _seed_config(db_session, "imap_email", "test@163.com")

    resp = client.put("/api/v1/config", json={
        "configs": {
            "imap_password": "******",
            "imap_email": "new@163.com",
        }
    })
    assert resp.status_code == 200

    # Verify password was NOT changed
    row = db_session.query(SystemConfig).filter(
        SystemConfig.key == "imap_password"
    ).first()
    assert row.value == "original_password"

    # Verify email was changed
    row2 = db_session.query(SystemConfig).filter(
        SystemConfig.key == "imap_email"
    ).first()
    assert row2.value == "new@163.com"
