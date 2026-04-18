from pydantic import BaseModel, Field


class ClassModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")


class ClassModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ClassModelResponse(BaseModel):
    id: int
    name: str
    description: str

    model_config = {"from_attributes": True}


class ClassCategoryCreate(BaseModel):
    model_id: int
    parent_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    sort_order: int = 0


class ClassCategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class ClassCategoryResponse(BaseModel):
    id: int
    model_id: int
    parent_id: int | None
    name: str
    level: int
    sort_order: int

    model_config = {"from_attributes": True}


class ClassCategoryTree(BaseModel):
    id: int
    model_id: int
    parent_id: int | None
    name: str
    level: int
    sort_order: int
    children: list["ClassCategoryTree"] = []

    model_config = {"from_attributes": True}


class FundClassMapCreate(BaseModel):
    fund_id: int
    category_id: int
    model_id: int


class FundClassMapResponse(BaseModel):
    id: int
    fund_id: int
    category_id: int
    model_id: int

    model_config = {"from_attributes": True}
