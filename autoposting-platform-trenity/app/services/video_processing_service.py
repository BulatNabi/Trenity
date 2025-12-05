import os
import shutil
from typing import List
from app.services.uniq_service import uniq_service
from app.services.s3_service import s3_service
from app.config import settings
from app.logger import service_logger as logger
import uuid


class VideoProcessingService:
    def __init__(self):
        self.data_folder = settings.data_folder
        self.target_video_count = 100
        self.max_copies_per_request = 5
    
    def ensure_data_folder(self):
        """Создает папку data если её нет"""
        os.makedirs(self.data_folder, exist_ok=True)
    
    async def process_video_to_100_unique(self, video_path: str) -> List[str]:
        """
        Обрабатывает видео до получения 100 уникализированных версий
        Возвращает список URL видео в S3
        """
        logger.info(f"Начало обработки видео до 100 уникальных версий: {video_path}")
        self.ensure_data_folder()
        video_urls = []
        current_count = 0
        
        # Получаем исходное видео
        original_video = video_path
        
        while current_count < self.target_video_count:
            # Вычисляем сколько нужно запросить
            needed = self.target_video_count - current_count
            copies_to_request = min(needed, self.max_copies_per_request)
            
            logger.info(f"Итерация уникализации: нужно {needed}, запрашиваем {copies_to_request}, уже получено {current_count}")
            
            # Отправляем на уникализацию
            unique_videos = await uniq_service.uniquize_video(
                original_video,
                copies=copies_to_request
            )
            
            if not unique_videos:
                logger.warning("Не получено ни одного видео от API уникализации")
                # Если это не первая итерация, используем исходное видео снова
                if current_count > 0:
                    logger.warning("Повторяем с исходным видео")
                    continue
                else:
                    break
            
            # Сохраняем первое видео для следующей итерации (если нужно)
            next_iteration_video = None
            if current_count < self.target_video_count and len(unique_videos) > 0:
                # Сохраняем первое видео для следующей итерации ДО загрузки в S3
                first_video = unique_videos[0]
                if os.path.exists(first_video):
                    next_video_path = os.path.join(self.data_folder, f"temp_{uuid.uuid4()}{os.path.splitext(first_video)[1]}")
                    shutil.copy2(first_video, next_video_path)
                    next_iteration_video = next_video_path
                    logger.debug(f"Сохранено видео для следующей итерации: {next_video_path}")
            
            # Загружаем каждое видео в S3
            for video_file in unique_videos:
                try:
                    # Генерируем уникальный ключ для S3
                    file_ext = os.path.splitext(video_file)[1]
                    s3_key = f"videos/{uuid.uuid4()}{file_ext}"
                    
                    # Загружаем в S3
                    video_url = s3_service.upload_file(video_file, s3_key)
                    video_urls.append(video_url)
                    current_count += 1
                    
                    # Удаляем временный файл после успешной загрузки
                    try:
                        if os.path.exists(video_file):
                            os.remove(video_file)
                    except:
                        pass  # Игнорируем ошибки удаления
                    
                    if current_count >= self.target_video_count:
                        break
                        
                except Exception as e:
                    # Пытаемся удалить файл даже при ошибке
                    try:
                        if os.path.exists(video_file):
                            os.remove(video_file)
                    except:
                        pass
                    logger.error(f"Ошибка загрузки видео {video_file} в S3: {str(e)}", exc_info=True)
                    continue
            
            # Если не получили нужное количество, продолжаем с сохраненным видео
            if current_count < self.target_video_count:
                if next_iteration_video and os.path.exists(next_iteration_video):
                    original_video = next_iteration_video
                    logger.info(f"Продолжаем итерацию. Используем сохраненное видео: {original_video}")
                else:
                    # Если не удалось сохранить видео, используем исходное
                    if os.path.exists(video_path):
                        original_video = video_path
                        logger.warning("Используем исходное видео для следующей итерации")
                    else:
                        logger.error("Нет доступных видео для следующей итерации")
                        break
            elif current_count >= self.target_video_count:
                # Удаляем временное видео для следующей итерации, если оно было создано
                if next_iteration_video and os.path.exists(next_iteration_video):
                    try:
                        os.remove(next_iteration_video)
                    except:
                        pass
                break
        
        logger.info(f"Обработка завершена. Получено {len(video_urls)} видео из {self.target_video_count} запрошенных")
        return video_urls[:self.target_video_count]
    
    async def process_video_to_n_unique(self, video_path: str, target_count: int) -> List[str]:
        """
        Обрабатывает видео до получения N уникализированных версий
        Возвращает список URL видео в S3
        
        Args:
            video_path: Путь к исходному видео
            target_count: Целевое количество уникальных видео
        """
        logger.info(f"Начало обработки видео до {target_count} уникальных версий: {video_path}")
        self.ensure_data_folder()
        video_urls = []
        current_count = 0
        
        # Получаем исходное видео
        original_video = video_path
        max_retries = 10  # Максимальное количество попыток при ошибках
        
        while current_count < target_count:
            # Вычисляем сколько нужно запросить
            needed = target_count - current_count
            copies_to_request = min(needed, self.max_copies_per_request)
            
            logger.info(f"Итерация уникализации: нужно {needed}, запрашиваем {copies_to_request}, уже получено {current_count}")
            
            # Отправляем на уникализацию с обработкой ошибок
            unique_videos = []
            retry_count = 0
            while retry_count < max_retries:
                try:
                    unique_videos = await uniq_service.uniquize_video(
                        original_video,
                        copies=copies_to_request
                    )
                    break  # Успешно получили видео
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Ошибка уникализации (попытка {retry_count}/{max_retries}): {str(e)}")
                    if retry_count >= max_retries:
                        logger.error(f"Не удалось получить видео после {max_retries} попыток")
                        # Продолжаем с исходным видео
                        if os.path.exists(video_path):
                            original_video = video_path
                        else:
                            logger.error("Исходное видео недоступно, прерываем обработку")
                            break
                    continue
            
            if not unique_videos:
                logger.warning("Не получено ни одного видео от API уникализации")
                # Если это не первая итерация, используем исходное видео снова
                if current_count > 0 and os.path.exists(video_path):
                    original_video = video_path
                    logger.warning("Повторяем с исходным видео")
                    continue
                else:
                    logger.error("Не удалось получить видео, прерываем обработку")
                    break
            
            # Сохраняем первое видео для следующей итерации (если нужно)
            next_iteration_video = None
            if current_count < target_count and len(unique_videos) > 0:
                # Сохраняем первое видео для следующей итерации ДО загрузки в S3
                first_video = unique_videos[0]
                if os.path.exists(first_video):
                    next_video_path = os.path.join(self.data_folder, f"temp_{uuid.uuid4()}{os.path.splitext(first_video)[1]}")
                    shutil.copy2(first_video, next_video_path)
                    next_iteration_video = next_video_path
                    logger.debug(f"Сохранено видео для следующей итерации: {next_video_path}")
            
            # Загружаем каждое видео в S3
            for video_file in unique_videos:
                try:
                    # Генерируем уникальный ключ для S3
                    file_ext = os.path.splitext(video_file)[1]
                    s3_key = f"videos/{uuid.uuid4()}{file_ext}"
                    
                    # Загружаем в S3
                    video_url = s3_service.upload_file(video_file, s3_key)
                    video_urls.append(video_url)
                    current_count += 1
                    
                    # Удаляем временный файл после успешной загрузки
                    try:
                        if os.path.exists(video_file):
                            os.remove(video_file)
                    except:
                        pass  # Игнорируем ошибки удаления
                    
                    if current_count >= target_count:
                        break
                        
                except Exception as e:
                    # Пытаемся удалить файл даже при ошибке
                    try:
                        if os.path.exists(video_file):
                            os.remove(video_file)
                    except:
                        pass
                    logger.error(f"Ошибка загрузки видео {video_file} в S3: {str(e)}", exc_info=True)
                    continue
            
            # Если не получили нужное количество, продолжаем с сохраненным видео
            if current_count < target_count:
                if next_iteration_video and os.path.exists(next_iteration_video):
                    original_video = next_iteration_video
                    logger.info(f"Продолжаем итерацию. Используем сохраненное видео: {original_video}")
                else:
                    # Если не удалось сохранить видео, используем исходное
                    if os.path.exists(video_path):
                        original_video = video_path
                        logger.warning("Используем исходное видео для следующей итерации")
                    else:
                        logger.error("Нет доступных видео для следующей итерации")
                        break
            elif current_count >= target_count:
                # Удаляем временное видео для следующей итерации, если оно было создано
                if next_iteration_video and os.path.exists(next_iteration_video):
                    try:
                        os.remove(next_iteration_video)
                    except:
                        pass
                break
        
        logger.info(f"Обработка завершена. Получено {len(video_urls)} видео из {target_count} запрошенных")
        return video_urls[:target_count]
    
    def cleanup_data_folder(self):
        """Удаляет все файлы из папки data"""
        logger.info(f"Очистка папки {self.data_folder}")
        if os.path.exists(self.data_folder):
            deleted_count = 0
            for filename in os.listdir(self.data_folder):
                file_path = os.path.join(self.data_folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Ошибка удаления {file_path}: {str(e)}", exc_info=True)
            logger.info(f"Очистка завершена. Удалено {deleted_count} элементов")


video_processing_service = VideoProcessingService()

