from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import models, schemas
from app.logger import api_logger as logger

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("/", response_model=schemas.AccountResponse)
def create_account(account: schemas.AccountCreate, db: Session = Depends(get_db)):
    """Создать новый аккаунт"""
    logger.info(f"Создание аккаунта: social={account.social.value}, account_id={account.account_id}")
    db_account = models.Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info(f"Аккаунт создан: id={db_account.id}")
    return db_account


@router.get("/", response_model=List[schemas.AccountResponse])
def get_accounts(
    social: Optional[schemas.SocialNetwork] = Query(
        None, description="Фильтр по соцсети"),
    db: Session = Depends(get_db)
):
    """Получить список аккаунтов"""
    query = db.query(models.Account)
    if social:
        query = query.filter(models.Account.social == social)
    return query.all()


@router.get("/{account_id}", response_model=schemas.AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    """Получить аккаунт по ID"""
    account = db.query(models.Account).filter(
        models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return account


@router.put("/{account_id}", response_model=schemas.AccountResponse)
def update_account(
    account_id: int,
    account_update: schemas.AccountUpdate,
    db: Session = Depends(get_db)
):
    """Обновить аккаунт"""
    account = db.query(models.Account).filter(
        models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    update_data = account_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """Удалить аккаунт"""
    account = db.query(models.Account).filter(
        models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    db.delete(account)
    db.commit()
    return {"message": "Аккаунт удален"}
