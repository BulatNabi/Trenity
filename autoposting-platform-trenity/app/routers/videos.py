from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from app.database import get_db
from app import models, schemas
from app.services.video_processing_service import video_processing_service
from app.config import settings
from app.logger import api_logger as logger

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post("/upload", response_model=schemas.VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...)
):
    """Загрузить видео для обработки"""
    # Проверяем формат файла
    if not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(
            status_code=400, detail="Неподдерживаемый формат видео")

    # Создаем папку data если её нет
    os.makedirs(settings.data_folder, exist_ok=True)

    # Сохраняем файл
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.data_folder, file_name)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    return {
        "message": "Видео загружено",
        "video_path": file_path
    }


@router.post("/process/{video_filename}")
async def process_video(
    video_filename: str
):
    """Обработать видео до получения 100 уникализированных версий"""
    logger.info(f"Обработка видео: {video_filename}")
    video_path = os.path.join(settings.data_folder, video_filename)

    if not os.path.exists(video_path):
        logger.warning(f"Видео не найдено: {video_path}")
        raise HTTPException(status_code=404, detail="Видео не найдено")

    try:
        video_urls = await video_processing_service.process_video_to_100_unique(video_path)
        logger.info(f"Видео обработано: получено {len(video_urls)} уникальных версий")
        return {
            "message": "Видео обработано",
            "total_videos": len(video_urls),
            "video_urls": video_urls
        }
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
