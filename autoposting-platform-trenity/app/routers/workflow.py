from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from app.database import get_db
from app import models, schemas
from app.services.video_processing_service import video_processing_service
from app.services.smmbox_service import smmbox_service
from app.models import SocialNetwork
from app.config import settings
from app.logger import api_logger as logger
from datetime import datetime

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/process-and-publish")
async def process_and_publish_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Полный цикл обработки и публикации:
    1. Загружает видео
    2. Уникализирует до 100 версий
    3. Загружает в S3
    4. Публикует на все аккаунты
    5. Очищает папку data
    """
    logger.info(f"Начало полного цикла обработки и публикации: {file.filename}")
    # 1. Загружаем видео
    if not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
        logger.warning(f"Неподдерживаемый формат видео: {file.filename}")
        raise HTTPException(
            status_code=400, detail="Неподдерживаемый формат видео")

    os.makedirs(settings.data_folder, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.data_folder, file_name)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    try:
        # 2. Обрабатываем видео до 100 уникальных версий
        video_urls = await video_processing_service.process_video_to_100_unique(file_path)

        if len(video_urls) != 100:
            logger.error(f"Не удалось получить 100 видео. Получено: {len(video_urls)}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось получить 100 видео. Получено: {len(video_urls)}"
            )

        # 3. Проверяем наличие аккаунтов
        accounts_by_social = {}
        for social in [SocialNetwork.VK, SocialNetwork.INSTAGRAM, SocialNetwork.YOUTUBE, SocialNetwork.PINTEREST]:
            accounts = db.query(models.Account).filter(
                models.Account.social == social).all()
            if len(accounts) < 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недостаточно аккаунтов для {social.value}. Требуется 100, найдено {len(accounts)}"
                )
            accounts_by_social[social] = accounts[:100]

        # 4. Публикуем видео
        published_posts = []
        errors = []

        for i, video_url in enumerate(video_urls):
            for social, accounts in accounts_by_social.items():
                if i < len(accounts):
                    account = accounts[i]
                    try:
                        result = await smmbox_service.create_post(
                            group_id=account.account_id,
                            social=account.social,
                            group_type=account.account_type,
                            video_url=video_url
                        )

                        post_id = None
                        if result.get("posts") and len(result.get("posts", [])) > 0:
                            post_id = result.get("posts")[0].get("id")

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
                        post = models.Post(
                            account_id=account.id,
                            video_url=video_url,
                            status="failed"
                        )
                        db.add(post)

        db.commit()
        
        logger.info(f"Публикация завершена: опубликовано {len(published_posts)}, ошибок {len(errors)}")
        
        # 5. Очищаем папку data
        video_processing_service.cleanup_data_folder()
        
        return {
            "message": "Обработка и публикация завершены",
            "total_videos": len(video_urls),
            "published": len(published_posts),
            "errors": len(errors),
            # Показываем только первые 10 ошибок
            "error_details": errors[:10] if errors else []
        }
        
    except Exception as e:
        logger.error(f"Ошибка в процессе обработки и публикации: {str(e)}", exc_info=True)
        # Очищаем в случае ошибки
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))
