from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import time
from app.database import get_db
from app import models, schemas
from app.services.smmbox_service import smmbox_service
from app.services.video_processing_service import video_processing_service
from app.models import SocialNetwork
from app.logger import api_logger as logger

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.post("/publish-all")
async def publish_all_videos(
    video_urls: List[str],
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Публикует все видео на все аккаунты во всех соцсетях
    Ожидает: список из 100 URL видео
    """
    logger.info(f"Начало публикации {len(video_urls)} видео")
    if len(video_urls) != 100:
        logger.warning(f"Неверное количество видео: ожидается 100, получено {len(video_urls)}")
        raise HTTPException(
            status_code=400,
            detail=f"Ожидается 100 видео, получено {len(video_urls)}"
        )

    # Получаем все аккаунты, сгруппированные по соцсетям
    accounts_by_social = {}
    for social in [SocialNetwork.VK, SocialNetwork.INSTAGRAM, SocialNetwork.YOUTUBE, SocialNetwork.PINTEREST]:
        accounts = db.query(models.Account).filter(
            models.Account.social == social).all()
        if len(accounts) < 100:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно аккаунтов для {social.value}. Требуется 100, найдено {len(accounts)}"
            )
        accounts_by_social[social] = accounts[:100]  # Берем первые 100

    # Публикуем видео
    published_posts = []
    errors = []

    # Публикуем каждое видео на все 4 соцсети (100 видео * 4 соцсети = 400 постов)
    for i, video_url in enumerate(video_urls):
        for social, accounts in accounts_by_social.items():
            if i < len(accounts):
                account = accounts[i]
                try:
                    # Создаем пост через SmmBox API
                    result = await smmbox_service.create_post(
                        group_id=account.account_id,
                        social=account.social,
                        group_type=account.account_type,
                        video_url=video_url
                    )

                    # Извлекаем ID поста из ответа
                    post_id = None
                    if result.get("posts") and len(result.get("posts", [])) > 0:
                        post_id = result.get("posts")[0].get("id")

                    # Сохраняем в БД
                    post = models.Post(
                        account_id=account.id,
                        video_url=video_url,
                        smmbox_post_id=post_id,
                        status="published",
                        published_at=datetime.now()
                    )
                    db.add(post)
                    published_posts.append(post)

                except Exception as e:
                    errors.append({
                        "video_url": video_url,
                        "account_id": account.id,
                        "social": social.value,
                        "error": str(e)
                    })
                    # Сохраняем ошибку в БД
                    post = models.Post(
                        account_id=account.id,
                        video_url=video_url,
                        status="failed"
                    )
                    db.add(post)

    db.commit()

    # Очищаем папку data после публикации
    video_processing_service.cleanup_data_folder()

    return {
        "message": "Публикация завершена",
        "published": len(published_posts),
        "errors": len(errors),
        "error_details": errors
    }


@router.get("/", response_model=List[schemas.PostResponse])
def get_posts(db: Session = Depends(get_db)):
    """Получить список всех постов"""
    return db.query(models.Post).all()


@router.get("/{post_id}", response_model=schemas.PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """Получить пост по ID"""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return post
