from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List
import os
import uuid
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.services.video_processing_service import video_processing_service
from app.services.smmbox_service import smmbox_service
from app.services.s3_service import s3_service
from app.config import settings
from app.logger import api_logger as logger
from app.models import SocialNetwork

router = APIRouter(prefix="/api/publish", tags=["publish"])


@router.post("/")
async def publish_video(
    file: UploadFile = File(...),
    selected_accounts: str = Form(...),  # JSON string
    publish_date: str = Form(...),  # ISO format datetime string
    post_text: str = Form(None)  # Текст поста (опционально)
):
    """
    Публикует видео на выбранные аккаунты

    Args:
        file: Видео файл
        selected_accounts: JSON строка с массивом выбранных аккаунтов
            [{"id": "123", "social": "vk", "type": "user"}, ...]
        publish_date: Дата публикации в формате ISO (YYYY-MM-DDTHH:mm:ss)
        post_text: Текст поста (опционально)
    """
    logger.info(f"Начало публикации видео: {file.filename}")

    # Парсим выбранные аккаунты
    try:
        accounts = json.loads(selected_accounts)
        if not isinstance(accounts, list) or len(accounts) == 0:
            raise HTTPException(
                status_code=400, detail="Не выбрано ни одного аккаунта")
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="Неверный формат selected_accounts")

    # Проверяем формат файла (.zip или видео)
    file_ext = os.path.splitext(file.filename)[1].lower()
    is_zip = file_ext == '.zip'
    is_video = file_ext in ('.mp4', '.avi', '.mov', '.mkv')

    if not (is_zip or is_video):
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла: {file_ext}. Ожидается .zip или видео файл (.mp4, .avi, .mov, .mkv)"
        )

    # Сохраняем файл
    os.makedirs(settings.data_folder, exist_ok=True)
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.data_folder, file_name)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Обрабатываем файл в зависимости от типа
    video_files = []
    extract_folder = None  # Для очистки в случае ошибки

    if is_zip:
        # Распаковываем ZIP архив
        logger.info(f"Обнаружен ZIP архив, распаковываем: {file_path}")
        extract_folder = os.path.join(
            settings.data_folder, f"extracted_{uuid.uuid4()}")
        os.makedirs(extract_folder, exist_ok=True)

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
                logger.info(f"ZIP архив распакован в: {extract_folder}")

            # Ищем все видео файлы в распакованной папке
            video_extensions = ('.mp4', '.avi', '.mov',
                                '.mkv', '.MP4', '.AVI', '.MOV', '.MKV')
            for root, dirs, files in os.walk(extract_folder):
                for filename in files:
                    if filename.endswith(video_extensions):
                        video_path = os.path.join(root, filename)
                        video_files.append(video_path)
                        logger.info(f"Найдено видео в архиве: {filename}")

            if not video_files:
                raise HTTPException(
                    status_code=400,
                    detail="В ZIP архиве не найдено видео файлов"
                )

            logger.info(
                f"Найдено {len(video_files)} видео файлов в ZIP архиве")

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail="Файл не является корректным ZIP архивом"
            )
        except Exception as e:
            logger.error(f"Ошибка распаковки ZIP: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка распаковки ZIP архива: {str(e)}"
            )
        finally:
            # Удаляем ZIP файл после распаковки
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
    else:
        # Это видео файл
        video_files = [file_path]
        logger.info(f"Обработка одного видео файла: {file_path}")

    try:
        # Парсим дату публикации
        # SmmBox API ожидает Unix timestamp в MSK (Московское время, UTC+3)
        try:
            # Убираем Z и парсим дату
            date_str = publish_date.replace('Z', '')

            # Парсим ISO формат (YYYY-MM-DDTHH:mm:ss)
            if 'T' in date_str:
                publish_datetime = datetime.fromisoformat(date_str)
            else:
                raise ValueError(
                    "Неверный формат даты, ожидается ISO формат с T")

            # Если нет timezone, считаем что это MSK (UTC+3)
            if publish_datetime.tzinfo is None:
                # Создаем timezone для MSK (UTC+3)
                msk_tz = timezone(timedelta(hours=3))
                publish_datetime = publish_datetime.replace(tzinfo=msk_tz)
                logger.info(
                    f"Время интерпретировано как MSK: {publish_datetime}")
            else:
                # Если timezone указан, конвертируем в MSK
                msk_tz = timezone(timedelta(hours=3))
                publish_datetime = publish_datetime.astimezone(msk_tz)
                logger.info(f"Время сконвертировано в MSK: {publish_datetime}")

        except ValueError as e:
            logger.error(
                f"Ошибка парсинга даты: {publish_date}, ошибка: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Неверный формат даты: {publish_date}")

        # Проверяем, что дата не в прошлом (сравниваем в MSK)
        now_msk = datetime.now(timezone(timedelta(hours=3)))
        logger.info(
            f"Текущее время MSK: {now_msk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(
            f"Запрошенное время публикации MSK: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Добавляем небольшую буферную зону (1 минута) для учета задержек обработки
        buffer_time = now_msk + timedelta(minutes=1)

        if publish_datetime <= buffer_time:
            logger.warning(
                f"Дата публикации в прошлом или слишком близко к текущему времени "
                f"({publish_datetime.strftime('%Y-%m-%d %H:%M:%S')} MSK <= {buffer_time.strftime('%Y-%m-%d %H:%M:%S')} MSK), "
                f"используем текущую + 3 минуты для безопасности")
            publish_datetime = now_msk + timedelta(minutes=3)
            logger.info(
                f"Новое время публикации MSK: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Финальная проверка - убеждаемся, что дата точно в будущем
        final_check = datetime.now(timezone(timedelta(hours=3)))
        if publish_datetime <= final_check:
            logger.warning(
                f"Финальная проверка: дата все еще в прошлом, добавляем еще 2 минуты")
            publish_datetime = final_check + timedelta(minutes=2)
            logger.info(
                f"Финальное время публикации MSK: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Конвертируем в unix timestamp
        # Unix timestamp всегда в UTC, но datetime должен быть с правильным timezone
        publish_timestamp = int(publish_datetime.timestamp())
        logger.info(f"Unix timestamp для публикации: {publish_timestamp}")
        logger.info(
            f"Время публикации MSK: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Проверяем, что timestamp действительно в будущем
        now_timestamp = int(final_check.timestamp())
        time_diff_seconds = publish_timestamp - now_timestamp
        logger.info(
            f"Разница с текущим временем: {time_diff_seconds} секунд ({time_diff_seconds / 60:.1f} минут)")

        if time_diff_seconds <= 0:
            logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: timestamp все еще в прошлом! {publish_timestamp} <= {now_timestamp}")
            # Принудительно устанавливаем время в будущем
            publish_datetime = final_check + timedelta(minutes=5)
            publish_timestamp = int(publish_datetime.timestamp())
            logger.warning(
                f"Принудительно установлено время: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')} (timestamp: {publish_timestamp})")

        # Получаем количество уникальных видео (равно количеству аккаунтов)
        target_video_count = len(accounts)
        logger.info(
            f"Требуется {target_video_count} уникальных видео для {len(accounts)} аккаунтов")
        logger.info(f"Исходных видео файлов: {len(video_files)}")

        # Обрабатываем все видео файлы
        video_urls = []

        if len(video_files) == 1:
            # Одно видео - генерируем нужное количество уникальных версий
            logger.info(
                f"Обработка одного видео файла для генерации {target_video_count} уникальных версий")
            video_urls = await video_processing_service.process_video_to_n_unique(
                video_files[0],
                target_video_count
            )
        else:
            # Несколько видео - для каждого генерируем уникальные версии
            # Распределяем аккаунты между видео
            videos_per_file = target_video_count // len(video_files)
            remainder = target_video_count % len(video_files)

            logger.info(f"Обработка {len(video_files)} видео файлов")
            logger.info(
                f"Видео на файл: {videos_per_file}, остаток: {remainder}")

            for i, video_file in enumerate(video_files):
                # Для последних файлов добавляем остаток
                count_for_this_video = videos_per_file + \
                    (1 if i < remainder else 0)

                if count_for_this_video > 0:
                    logger.info(
                        f"Обработка видео {i+1}/{len(video_files)}: {os.path.basename(video_file)} -> {count_for_this_video} уникальных версий")
                    unique_urls = await video_processing_service.process_video_to_n_unique(
                        video_file,
                        count_for_this_video
                    )
                    video_urls.extend(unique_urls)
                    logger.info(
                        f"Получено {len(unique_urls)} уникальных версий из видео {i+1}")

                # Если уже получили достаточно видео, останавливаемся
                if len(video_urls) >= target_video_count:
                    video_urls = video_urls[:target_video_count]
                    break

        if len(video_urls) < target_video_count:
            logger.warning(
                f"Получено {len(video_urls)} видео из {target_video_count} запрошенных. "
                f"Продолжаем публикацию с имеющимися видео."
            )
            # Обрезаем список аккаунтов до количества видео
            accounts = accounts[:len(video_urls)]

        # Формируем посты для публикации
        posts = []
        for i, account in enumerate(accounts):
            if i >= len(video_urls):
                break

            # Определяем SocialNetwork enum
            social_value = account.get("social", "").lower()
            try:
                social_enum = SocialNetwork(social_value)
            except ValueError:
                logger.warning(
                    f"Неизвестная соцсеть: {social_value}, пропускаем")
                continue

            # Формируем вложения
            attachments = []

            # Добавляем текст, если он указан
            if post_text and post_text.strip():
                attachments.append({
                    "type": "text",
                    "text": post_text.strip()
                })

            # Добавляем видео
            attachments.append({
                "type": "video",
                "url": video_urls[i]
            })

            post = {
                "group": {
                    "id": str(account.get("id", "")),
                    "social": social_value,
                    "type": account.get("type", "user")
                },
                "attachments": attachments,
                "date": publish_timestamp
            }
            posts.append(post)

        # Публикуем все посты одним запросом
        published_count = 0
        errors = []

        # Финальная проверка даты перед отправкой (на случай, если обработка видео заняла время)
        now_msk_final = datetime.now(timezone(timedelta(hours=3)))
        time_diff_seconds = publish_timestamp - int(now_msk_final.timestamp())

        if time_diff_seconds <= 60:  # Если меньше минуты до публикации
            logger.warning(
                f"Дата публикации слишком близко к текущему времени ({time_diff_seconds} секунд), "
                f"обновляем на текущее время + 3 минуты"
            )
            publish_datetime = now_msk_final + timedelta(minutes=3)
            publish_timestamp = int(publish_datetime.timestamp())
            # Обновляем дату во всех постах
            for post in posts:
                post["date"] = publish_timestamp
            logger.info(
                f"Обновленное время публикации MSK: {publish_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')} (timestamp: {publish_timestamp})")

        try:
            result = await smmbox_service.create_posts_batch(posts)
            published_posts = result.get("posts", [])
            published_count = len(published_posts)
            logger.info(f"Успешно опубликовано {published_count} постов")
        except Exception as e:
            logger.error(f"Ошибка публикации постов: {str(e)}", exc_info=True)
            errors.append({
                "error": str(e),
                "posts_count": len(posts)
            })

        # Очищаем временные файлы
        try:
            # Удаляем исходный файл (если еще не удален)
            if os.path.exists(file_path):
                os.remove(file_path)

            # Удаляем распакованные файлы (если были)
            if is_zip and extract_folder and os.path.exists(extract_folder):
                shutil.rmtree(extract_folder)
                logger.info(f"Удалена временная папка: {extract_folder}")
        except Exception as e:
            logger.warning(f"Ошибка при очистке временных файлов: {str(e)}")

        # Удаляем обработанные видео файлы
        for video_file in video_files:
            try:
                if os.path.exists(video_file):
                    os.remove(video_file)
            except:
                pass

        video_processing_service.cleanup_data_folder()

        return {
            "message": "Публикация завершена",
            "total_accounts": len(accounts),
            "total_videos": len(video_urls),
            "published": published_count,
            "errors": errors
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в процессе публикации: {str(e)}", exc_info=True)
        # Очищаем в случае ошибки
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if is_zip and extract_folder and os.path.exists(extract_folder):
                shutil.rmtree(extract_folder)
            for video_file in video_files:
                if os.path.exists(video_file):
                    os.remove(video_file)
        except:
            pass
        video_processing_service.cleanup_data_folder()
        raise HTTPException(
            status_code=500, detail=f"Ошибка публикации: {str(e)}")
