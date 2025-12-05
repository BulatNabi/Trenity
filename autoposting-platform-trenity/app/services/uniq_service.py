import httpx
import zipfile
import os
import tempfile
import uuid
from typing import List
from app.config import settings
from app.logger import service_logger as logger


class UniquizationService:
    def __init__(self):
        self.api_url = settings.uniq_api_url

    async def uniquize_video(self, video_path: str, copies: int = 3) -> List[str]:
        """
        Отправляет видео на уникализацию и возвращает список путей к уникализированным видео

        Процесс в два этапа:
        1. POST запрос - отправка видео, получение jobId и token
        2. GET запрос - скачивание готового ZIP файла по jobId и token
        3. Разархивирование ZIP и извлечение видео файлов
        """
        if copies > 3:
            copies = 3

        video_files = []

        try:
            async with httpx.AsyncClient(timeout=1800.0) as client:
                # Читаем файл
                with open(video_path, 'rb') as f:
                    file_content = f.read()
                    file_name = os.path.basename(video_path)

                # Определяем content type по расширению
                content_type = 'video/mp4'
                if file_name.endswith('.avi'):
                    content_type = 'video/x-msvideo'
                elif file_name.endswith('.mov'):
                    content_type = 'video/quicktime'
                elif file_name.endswith('.mkv'):
                    content_type = 'video/x-matroska'

                # Формируем multipart/form-data
                files = {
                    'files[]': (file_name, file_content, content_type)
                }
                data = {
                    'intent': 'upload',
                    'copies': copies
                }

                logger.info(
                    f"Отправка запроса на уникализацию: {self.api_url}, copies={copies}")
                response = await client.post(
                    self.api_url,
                    files=files,
                    data=data
                )
                content_type = response.headers.get('content-type', '').lower()
                logger.debug(
                    f"Ответ API уникализации: статус {response.status_code}, Content-Type: {content_type}, размер: {len(response.content)} байт")
                response.raise_for_status()

                # Проверяем, что ответ действительно ZIP файл
                # ZIP файлы начинаются с сигнатуры PK (0x504B)
                is_zip = response.content.startswith(
                    b'PK') or 'zip' in content_type

                # API возвращает JSON с jobId и token, а не ZIP напрямую
                json_response = response.json()
                logger.info(f"Получен ответ от API: {json_response}")

                # Извлекаем необходимые данные для скачивания
                job_id = json_response.get('jobId')
                token = json_response.get('token')
                status = json_response.get('status', 'unknown')
                file_count = json_response.get('fileCount', 0)

                if not job_id or not token:
                    error_msg = f"Не получены jobId или token из ответа API: {json_response}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                if status != 'completed':
                    logger.warning(
                        f"Статус обработки: {status}, ожидалось 'completed'")
                    # Возможно нужно подождать, но продолжаем попытку скачивания

                logger.info(
                    f"jobId: {job_id}, token: {token}, fileCount: {file_count}")

                # Проверяем warnings
                warnings = json_response.get('warnings', [])
                if warnings:
                    logger.warning(f"Предупреждения от API: {warnings}")

                # Этап 2: Скачивание готового файла (ZIP или MP4)
                download_url = f"{self.api_url}?download={job_id}&token={token}"
                logger.info(f"Этап 2: Скачивание файла: {download_url}")

                download_response = await client.get(download_url)
                download_response.raise_for_status()

                download_content_type = download_response.headers.get(
                    'content-type', '').lower()
                content_size = len(download_response.content)
                logger.info(
                    f"Ответ скачивания: статус {download_response.status_code}, Content-Type: {download_content_type}, размер: {content_size} байт")

                # Проверяем сигнатуру файла для определения типа
                is_zip_file = False
                is_mp4_file = False

                if content_size >= 4:
                    first_bytes = download_response.content[:2]
                    # ZIP файлы начинаются с PK (0x504B)
                    is_zip_signature = first_bytes == b'PK'

                    # MP4 файлы имеют структуру: [размер][тип]
                    # Обычно на позиции 4-8 находится "ftyp" (file type box)
                    # Также могут быть другие атомы: moov, mdat, free и т.д.
                    is_mp4_signature = False
                    if content_size >= 8:
                        # Проверяем атомы MP4 (обычно начинаются с размера, затем тип)
                        atoms = [download_response.content[4:8],
                                 download_response.content[8:12]]
                        mp4_atoms = [b'ftyp', b'moov',
                                     b'mdat', b'free', b'skip', b'wide']
                        is_mp4_signature = any(
                            atom in mp4_atoms for atom in atoms)

                    logger.debug(
                        f"Сигнатура файла: первые 2 байта={first_bytes.hex()}, "
                        f"байты 4-8={download_response.content[4:8] if content_size >= 8 else 'N/A'} "
                        f"({'PK - ZIP' if is_zip_signature else 'MP4' if is_mp4_signature else 'неизвестно'})")
                else:
                    is_zip_signature = False
                    is_mp4_signature = False
                    logger.error("Файл слишком маленький")

                # Определяем тип файла по сигнатуре и Content-Type
                is_zip_file = is_zip_signature or 'zip' in download_content_type
                is_mp4_file = (is_mp4_signature or 'video' in download_content_type or
                               download_content_type in ['video/mp4', 'application/octet-stream']) and not is_zip_file

                # Если не удалось определить по сигнатуре, проверяем Content-Type и количество копий
                if not is_zip_file and not is_mp4_file:
                    if copies == 1:
                        # Если запрошена одна копия, скорее всего это MP4
                        is_mp4_file = True
                        logger.info(
                            "Не удалось определить тип по сигнатуре, но copies=1, предполагаем MP4")
                    else:
                        # Если несколько копий, скорее всего это ZIP
                        is_zip_file = True
                        logger.info(
                            "Не удалось определить тип по сигнатуре, но copies>1, предполагаем ZIP")

                if not is_zip_file and not is_mp4_file:
                    # Пытаемся понять, что это за файл
                    try:
                        error_json = download_response.json()
                        logger.error(
                            f"API вернул JSON вместо файла: {error_json}")
                        raise Exception(
                            f"API вернул ошибку при скачивании: {error_json}")
                    except ValueError:
                        preview = download_response.content[:500].decode(
                            'utf-8', errors='ignore') if len(download_response.content) > 0 else "пустой ответ"
                        logger.error(
                            f"Не удалось определить тип файла. Первые 500 символов: {preview}")
                        raise Exception(
                            f"Не удалось определить тип скачанного файла. Content-Type: {download_content_type}, размер: {content_size} байт")

                # Обрабатываем файл в зависимости от типа
                if is_mp4_file:
                    # Это MP4 файл (одно видео) - сохраняем напрямую
                    logger.info(
                        "Обнаружен MP4 файл (одно видео), сохраняем напрямую")
                    extract_dir = tempfile.mkdtemp()
                    video_file_path = os.path.join(
                        extract_dir, f"unique_video_{uuid.uuid4()}.mp4")

                    with open(video_file_path, 'wb') as f:
                        f.write(download_response.content)

                    video_files.append(video_file_path)
                    logger.info(f"Сохранено одно видео: {video_file_path}")

                elif is_zip_file:
                    # Это ZIP файл (несколько видео) - распаковываем
                    logger.info(
                        "Обнаружен ZIP файл (несколько видео), распаковываем")

                    # Сохраняем zip файл во временную директорию
                    logger.debug("Сохранение zip файла")
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                        tmp_zip.write(download_response.content)
                        tmp_zip_path = tmp_zip.name

                    # Извлекаем видео из zip
                    extract_dir = tempfile.mkdtemp()
                    logger.debug(f"Извлечение архива в {extract_dir}")
                    try:
                        # Проверяем, что файл действительно ZIP перед открытием
                        with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                            # Получаем список файлов в архиве
                            file_list = zip_ref.namelist()
                            logger.info(f"Файлов в архиве: {len(file_list)}")
                            if file_list:
                                logger.debug(
                                    f"Первые файлы в архиве: {file_list[:5]}")
                            zip_ref.extractall(extract_dir)
                    except zipfile.BadZipFile as e:
                        logger.error(
                            f"Файл не является ZIP архивом. Размер: {len(download_response.content)} байт")
                        debug_file = os.path.join(
                            tempfile.gettempdir(), f"debug_response_{uuid.uuid4()}.bin")
                        with open(debug_file, 'wb') as f:
                            f.write(download_response.content)
                        logger.error(
                            f"Ответ API сохранен для отладки: {debug_file}")
                        raise Exception(
                            f"Файл не является ZIP архивом. Ответ сохранен в {debug_file} для анализа")

                    # Собираем список видео файлов
                    for root, dirs, files_list in os.walk(extract_dir):
                        for file in files_list:
                            if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                                video_files.append(os.path.join(root, file))

                    logger.info(
                        f"Извлечено {len(video_files)} видео файлов из архива (ожидалось {file_count})")

                    # Удаляем временный zip файл
                    os.unlink(tmp_zip_path)
                    logger.debug(f"Временный файл {tmp_zip_path} удален")

        except Exception as e:
            logger.error(f"Ошибка уникализации видео: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка уникализации видео: {str(e)}")

        logger.info(
            f"Уникализация завершена. Получено {len(video_files)} видео")
        return video_files

    async def get_download_url(self, download_id: str, token: str) -> bytes:
        """
        Скачивает уникализированное видео по download ID и token
        """
        try:
            logger.info(f"Скачивание видео: download_id={download_id}")
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.get(
                    f"{self.api_url}?download={download_id}&token={token}"
                )
                response.raise_for_status()
                logger.info(
                    f"Видео успешно скачано, размер: {len(response.content)} байт")
                return response.content
        except Exception as e:
            logger.error(f"Ошибка скачивания видео: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка скачивания видео: {str(e)}")


uniq_service = UniquizationService()
