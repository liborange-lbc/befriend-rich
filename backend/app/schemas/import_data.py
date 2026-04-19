from datetime import date, datetime

from pydantic import BaseModel


class ImportResultResponse(BaseModel):
    total_items: int
    matched_funds: int
    new_funds_created: int
    records_imported: int
    classification_results: dict
    snapshot_generated: bool
    import_log_id: int


class EmailPullResultResponse(BaseModel):
    email_found: bool
    statement_date: str | None
    total_items: int
    matched_funds: int
    new_funds_created: int
    records_imported: int
    classification_results: dict
    import_log_id: int


class ImportLogResponse(BaseModel):
    id: int
    import_date: date
    source: str
    file_name: str
    record_count: int
    new_funds_count: int
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportRecordResponse(BaseModel):
    id: int
    fund_id: int
    fund_code: str
    fund_name: str
    record_date: date
    amount: float
    amount_cny: float
    profit: float
    currency: str
    classifications: dict

    model_config = {"from_attributes": True}


class GroupedResult(BaseModel):
    key: dict
    total_amount: float
    total_amount_cny: float
    total_profit: float
    count: int
    records: list[ImportRecordResponse]


class GroupDimension(BaseModel):
    key: str
    label: str
    type: str
