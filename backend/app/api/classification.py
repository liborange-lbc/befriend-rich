from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.response import ok
from app.schemas.classification import (
    ClassCategoryCreate,
    ClassCategoryResponse,
    ClassCategoryTree,
    ClassCategoryUpdate,
    ClassModelCreate,
    ClassModelResponse,
    ClassModelUpdate,
    FundClassMapCreate,
    FundClassMapResponse,
)

router = APIRouter()


# --- ClassModel CRUD ---

@router.post("/models")
def create_model(body: ClassModelCreate, db: Session = Depends(get_db)):
    existing = db.query(ClassModel).filter(ClassModel.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="模型名称已存在")
    model = ClassModel(**body.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return ok(ClassModelResponse.model_validate(model).model_dump())


@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    models = db.query(ClassModel).all()
    return ok([ClassModelResponse.model_validate(m).model_dump() for m in models])


@router.get("/models/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(ClassModel).filter(ClassModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return ok(ClassModelResponse.model_validate(model).model_dump())


@router.put("/models/{model_id}")
def update_model(model_id: int, body: ClassModelUpdate, db: Session = Depends(get_db)):
    model = db.query(ClassModel).filter(ClassModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        dup = db.query(ClassModel).filter(ClassModel.name == update_data["name"], ClassModel.id != model_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="模型名称已存在")
    for key, value in update_data.items():
        setattr(model, key, value)
    db.commit()
    db.refresh(model)
    return ok(ClassModelResponse.model_validate(model).model_dump())


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(ClassModel).filter(ClassModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    db.query(FundClassMap).filter(FundClassMap.model_id == model_id).delete()
    db.query(ClassCategory).filter(ClassCategory.model_id == model_id).delete()
    db.delete(model)
    db.commit()
    return ok({"deleted": True})


# --- ClassCategory CRUD ---

@router.post("/categories")
def create_category(body: ClassCategoryCreate, db: Session = Depends(get_db)):
    model = db.query(ClassModel).filter(ClassModel.id == body.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    level = 1
    if body.parent_id is not None:
        parent = db.query(ClassCategory).filter(ClassCategory.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父类别不存在")
        level = parent.level + 1
    category = ClassCategory(
        model_id=body.model_id,
        parent_id=body.parent_id,
        name=body.name,
        level=level,
        sort_order=body.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return ok(ClassCategoryResponse.model_validate(category).model_dump())


@router.get("/categories")
def list_categories(model_id: int, db: Session = Depends(get_db)):
    categories = (
        db.query(ClassCategory)
        .filter(ClassCategory.model_id == model_id)
        .order_by(ClassCategory.level, ClassCategory.sort_order)
        .all()
    )
    return ok([ClassCategoryResponse.model_validate(c).model_dump() for c in categories])


@router.get("/categories/tree")
def get_category_tree(model_id: int, db: Session = Depends(get_db)):
    categories = (
        db.query(ClassCategory)
        .filter(ClassCategory.model_id == model_id)
        .order_by(ClassCategory.sort_order)
        .all()
    )
    cat_map = {c.id: {**ClassCategoryResponse.model_validate(c).model_dump(), "children": []} for c in categories}
    roots = []
    for c in categories:
        node = cat_map[c.id]
        if c.parent_id is None or c.parent_id not in cat_map:
            roots.append(node)
        else:
            cat_map[c.parent_id]["children"].append(node)
    return ok(roots)


@router.put("/categories/{category_id}")
def update_category(category_id: int, body: ClassCategoryUpdate, db: Session = Depends(get_db)):
    category = db.query(ClassCategory).filter(ClassCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="类别不存在")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return ok(ClassCategoryResponse.model_validate(category).model_dump())


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(ClassCategory).filter(ClassCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="类别不存在")
    db.query(FundClassMap).filter(FundClassMap.category_id == category_id).delete()
    _delete_category_tree(db, category_id)
    db.commit()
    return ok({"deleted": True})


def _delete_category_tree(db: Session, category_id: int):
    children = db.query(ClassCategory).filter(ClassCategory.parent_id == category_id).all()
    for child in children:
        db.query(FundClassMap).filter(FundClassMap.category_id == child.id).delete()
        _delete_category_tree(db, child.id)
    db.query(ClassCategory).filter(ClassCategory.id == category_id).delete()


# --- FundClassMap CRUD ---

@router.post("/mappings")
def create_mapping(body: FundClassMapCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(FundClassMap)
        .filter(FundClassMap.fund_id == body.fund_id, FundClassMap.model_id == body.model_id)
        .first()
    )
    if existing:
        existing.category_id = body.category_id
        db.commit()
        db.refresh(existing)
        return ok(FundClassMapResponse.model_validate(existing).model_dump())
    mapping = FundClassMap(**body.model_dump())
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return ok(FundClassMapResponse.model_validate(mapping).model_dump())


@router.get("/mappings")
def list_mappings(fund_id: int | None = None, model_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(FundClassMap)
    if fund_id is not None:
        query = query.filter(FundClassMap.fund_id == fund_id)
    if model_id is not None:
        query = query.filter(FundClassMap.model_id == model_id)
    mappings = query.all()
    return ok([FundClassMapResponse.model_validate(m).model_dump() for m in mappings])


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(FundClassMap).filter(FundClassMap.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    db.delete(mapping)
    db.commit()
    return ok({"deleted": True})


@router.post("/auto-classify")
def auto_classify_funds(db: Session = Depends(get_db)):
    """Use AI to auto-classify all funds that have incomplete classifications."""
    from app.models.fund import Fund
    from app.services.webank.classifier import classify_funds_with_ai

    models = db.query(ClassModel).all()
    if not models:
        raise HTTPException(status_code=400, detail="请先创建分类模型")

    # Find funds missing classification in any model
    all_funds = db.query(Fund).all()
    fund_ids_to_classify: list[int] = []
    for fund in all_funds:
        existing_models = {
            m.model_id
            for m in db.query(FundClassMap).filter(FundClassMap.fund_id == fund.id).all()
        }
        if len(existing_models) < len(models):
            fund_ids_to_classify.append(fund.id)

    if not fund_ids_to_classify:
        return ok({"classified": 0, "message": "所有基金已完成分类"})

    try:
        result = classify_funds_with_ai(db, fund_ids_to_classify)
        return ok({
            "classified": len(result),
            "total_funds": len(fund_ids_to_classify),
            "message": f"已为 {len(result)} 个基金完成 AI 自动分类",
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分类失败: {str(e)}")
