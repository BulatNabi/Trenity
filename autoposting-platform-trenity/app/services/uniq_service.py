import os
import tempfile
import uuid
import asyncio
import sys
import subprocess
from pathlib import Path
from typing import List, Optional
from app.logger import service_logger as logger

# Добавляем путь к trenity-uniqalize-system для импорта video_uniqueizer
# Пробуем несколько возможных путей (для локальной разработки и Docker)
possible_paths = [
    # Путь в Docker контейнере
    Path("/app/trenity-uniqalize-system"),
    # Путь для локальной разработки (относительно корня проекта)
    Path(__file__).parent.parent.parent.parent / "trenity-uniqalize-system",
]

# Добавляем альтернативные пути в зависимости от текущей директории
cwd = Path.cwd()
if cwd.name == "autoposting-platform-trenity":
    possible_paths.append(cwd.parent / "trenity-uniqalize-system")
else:
    possible_paths.append(cwd / "trenity-uniqalize-system")

uniqalize_system_path = None
for path in possible_paths:
    if path.exists() and (path / "video_uniqueizer.py").exists():
        uniqalize_system_path = path
        break

if uniqalize_system_path is None:
    # Используем базовый logging, так как logger может быть еще не инициализирован
    import logging
    import_logger = logging.getLogger("autoposting.uniq_service")
    import_logger.error("Не удалось найти trenity-uniqalize-system!")
    import_logger.error(f"Проверенные пути: {[str(p) for p in possible_paths]}")
    raise ImportError("Не удалось найти trenity-uniqalize-system. Убедитесь, что папка существует.")

if str(uniqalize_system_path) not in sys.path:
    sys.path.insert(0, str(uniqalize_system_path))

try:
    from video_uniqueizer import (
        process_video,
        detect_gpu_acceleration,
        check_ffmpeg,
        get_video_resolution
    )
except ImportError as e:
    # Используем базовый logging, так как logger может быть еще не инициализирован
    import logging
    import_logger = logging.getLogger("autoposting.uniq_service")
    import_logger.error(f"Не удалось импортировать video_uniqueizer: {e}")
    import_logger.error(f"Путь к trenity-uniqalize-system: {uniqalize_system_path}")
    import_logger.error(f"Абсолютный путь существует: {uniqalize_system_path.exists()}")
    raise


class UniquizationService:
    def __init__(self):
        # Проверяем FFmpeg при инициализации
        if not check_ffmpeg():
            raise RuntimeError("FFmpeg не найден в системе! Установите FFmpeg и добавьте его в PATH")
        
        logger.info("=" * 80)
        logger.info("ИНИЦИАЛИЗАЦИЯ УНИКАЛИЗАТОРА С GPU ПОДДЕРЖКОЙ")
        logger.info("=" * 80)
        
        # Детальная проверка окружения
        is_docker = os.path.exists('/.dockerenv')
        logger.info(f"Окружение: {'Docker контейнер' if is_docker else 'Локальная система'}")
        
        # Проверка NVIDIA переменных окружения
        nvidia_vars = {
            'NVIDIA_VISIBLE_DEVICES': os.environ.get('NVIDIA_VISIBLE_DEVICES'),
            'NVIDIA_DRIVER_CAPABILITIES': os.environ.get('NVIDIA_DRIVER_CAPABILITIES'),
            'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES'),
        }
        logger.info("NVIDIA переменные окружения:")
        for key, value in nvidia_vars.items():
            logger.info(f"  {key}: {value if value else 'НЕ УСТАНОВЛЕНО'}")
        
        # Проверка nvidia-smi
        has_nvidia_smi = False
        nvidia_smi_output = None
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                has_nvidia_smi = True
                nvidia_smi_output = result.stdout.strip()
                logger.info(f"nvidia-smi доступен:")
                logger.info(f"  {nvidia_smi_output}")
            else:
                logger.warning(f"nvidia-smi вернул код ошибки: {result.returncode}")
                logger.warning(f"  stderr: {result.stderr[:500]}")
        except FileNotFoundError:
            logger.warning("nvidia-smi не найден в PATH")
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi не отвечает (таймаут)")
        except Exception as e:
            logger.warning(f"Ошибка при проверке nvidia-smi: {str(e)}")
        
        # Проверка доступности nvidia-smi через путь
        nvidia_smi_paths = ['/usr/bin/nvidia-smi', '/usr/local/bin/nvidia-smi']
        nvidia_smi_found = any(os.path.exists(path) for path in nvidia_smi_paths)
        logger.info(f"nvidia-smi в стандартных путях: {'Найден' if nvidia_smi_found else 'Не найден'}")
        
        # Определяем GPU-ускорение один раз при инициализации
        logger.info("Определение GPU-ускорения через FFmpeg...")
        self.gpu_config = detect_gpu_acceleration()
        
        if self.gpu_config:
            logger.info(f"✓ GPU кодек обнаружен FFmpeg:")
            logger.info(f"  Тип: {self.gpu_config['type'].upper()}")
            logger.info(f"  Кодек: {self.gpu_config['encoder']}")
            logger.info(f"  Hardware acceleration: {self.gpu_config.get('hwaccel', 'N/A')}")
        else:
            logger.error("✗ GPU кодек НЕ обнаружен в FFmpeg!")
            logger.error("  Проверьте, что FFmpeg скомпилирован с поддержкой GPU")
        
        # Проверка доступности GPU
        has_nvidia_runtime = has_nvidia_smi or os.environ.get('NVIDIA_VISIBLE_DEVICES') is not None
        
        if is_docker:
            if not has_nvidia_runtime:
                logger.error("=" * 80)
                logger.error("КРИТИЧЕСКАЯ ОШИБКА: Docker контейнер без GPU доступа!")
                logger.error("=" * 80)
                logger.error("Требуется:")
                logger.error("  1. Установить nvidia-container-toolkit на хосте")
                logger.error("  2. Раскомментировать GPU настройки в docker-compose.yml")
                logger.error("  3. Перезапустить Docker daemon")
                logger.error("=" * 80)
                raise RuntimeError("GPU недоступен в Docker контейнере! Настройте nvidia-container-runtime.")
            else:
                logger.info("✓ NVIDIA runtime обнаружен в Docker")
        
        if not self.gpu_config:
            logger.error("=" * 80)
            logger.error("КРИТИЧЕСКАЯ ОШИБКА: GPU кодек не найден!")
            logger.error("=" * 80)
            logger.error("Проверьте:")
            logger.error("  1. FFmpeg скомпилирован с поддержкой GPU (h264_nvenc, h264_qsv и т.д.)")
            logger.error("  2. Драйверы GPU установлены")
            logger.error("  3. GPU доступен в системе")
            logger.error("=" * 80)
            raise RuntimeError("GPU кодек не найден! Уникализация требует GPU.")
        
        logger.info("=" * 80)
        logger.info(f"✓ УНИКАЛИЗАТОР ГОТОВ К РАБОТЕ С GPU: {self.gpu_config['type'].upper()}")
        logger.info("=" * 80)

    async def uniquize_video(self, video_path: str, copies: int = 3) -> List[str]:
        """
        Обрабатывает видео локально с помощью video_uniqueizer и возвращает список путей к уникализированным видео
        
        Args:
            video_path: Путь к исходному видео файлу
            copies: Количество уникализированных копий для создания
            
        Returns:
            Список путей к уникализированным видео файлам
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Видео файл не найден: {video_path}")
        
        if copies < 1:
            copies = 1
        
        logger.info(f"Начало локальной уникализации: {video_path}, copies={copies}")

        video_files = []
        input_path = Path(video_path)
        
        # Определяем расширение исходного файла
        file_ext = input_path.suffix or '.mp4'
        
        # Создаем временную директорию для выходных файлов
        extract_dir = tempfile.mkdtemp()
        logger.debug(f"Временная директория для уникализированных видео: {extract_dir}")
        
        try:
            # Обрабатываем каждую копию (обязательно с GPU)
            for i in range(copies):
                # Генерируем уникальное имя для выходного файла
                output_filename = f"unique_video_{uuid.uuid4()}{file_ext}"
                output_path = Path(extract_dir) / output_filename
                
                logger.info("=" * 80)
                logger.info(f"ОБРАБОТКА КОПИИ {i+1}/{copies}: {output_filename}")
                logger.info(f"Исходный файл: {video_path}")
                logger.info(f"Выходной файл: {output_path}")
                logger.info(f"GPU конфигурация: {self.gpu_config['type'].upper()} ({self.gpu_config['encoder']})")
                logger.info("=" * 80)
                
                # Запускаем обработку видео в отдельном потоке (так как process_video синхронная)
                try:
                    success, error_msg = await asyncio.to_thread(
                        process_video,
                        input_path,
                        output_path,
                        i + 1,
                        copies,
                        self.gpu_config
                    )
                    
                    if success and output_path.exists():
                        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                        video_files.append(str(output_path))
                        logger.info("=" * 80)
                        logger.info(f"✓ КОПИЯ {i+1} УСПЕШНО ОБРАБОТАНА")
                        logger.info(f"  Размер: {file_size:.2f} MB")
                        logger.info(f"  Путь: {output_path}")
                        logger.info("=" * 80)
                    else:
                        error_msg = error_msg or "Неизвестная ошибка"
                        
                        # Детальный анализ ошибки GPU
                        logger.error("=" * 80)
                        logger.error(f"✗ ОШИБКА ОБРАБОТКИ КОПИИ {i+1}")
                        logger.error("=" * 80)
                        logger.error(f"Полное сообщение об ошибке:")
                        logger.error(f"{error_msg}")
                        logger.error("=" * 80)
                        
                        # Проверяем тип ошибки
                        is_gpu_error = (
                            'nvenc' in error_msg.lower() or 
                            'gpu' in error_msg.lower() or 
                            'operation not permitted' in error_msg.lower() or
                            'invalid argument' in error_msg.lower() or
                            'could not open encoder' in error_msg.lower() or
                            'encoder' in error_msg.lower()
                        )
                        
                        if is_gpu_error:
                            logger.error("ДИАГНОСТИКА GPU ОШИБКИ:")
                            logger.error("=" * 80)
                            
                            # Проверяем nvidia-smi
                            try:
                                nvidia_check = subprocess.run(
                                    ['nvidia-smi', '--query-gpu=index,name,driver_version,memory.used,memory.total', '--format=csv'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if nvidia_check.returncode == 0:
                                    logger.error("nvidia-smi статус:")
                                    logger.error(nvidia_check.stdout)
                                else:
                                    logger.error(f"nvidia-smi недоступен (код: {nvidia_check.returncode})")
                                    logger.error(f"stderr: {nvidia_check.stderr[:500]}")
                            except Exception as e:
                                logger.error(f"Не удалось выполнить nvidia-smi: {str(e)}")
                            
                            # Проверяем FFmpeg кодеки
                            try:
                                ffmpeg_encoders = subprocess.run(
                                    ['ffmpeg', '-hide_banner', '-encoders'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if ffmpeg_encoders.returncode == 0:
                                    if 'h264_nvenc' in ffmpeg_encoders.stdout:
                                        logger.error("✓ h264_nvenc найден в FFmpeg")
                                    else:
                                        logger.error("✗ h264_nvenc НЕ найден в FFmpeg!")
                                        logger.error("  FFmpeg не скомпилирован с поддержкой NVENC")
                            except Exception as e:
                                logger.error(f"Не удалось проверить FFmpeg кодеки: {str(e)}")
                            
                            logger.error("=" * 80)
                            logger.error("ВОЗМОЖНЫЕ ПРИЧИНЫ:")
                            logger.error("  1. GPU недоступен в Docker (проверьте nvidia-container-runtime)")
                            logger.error("  2. FFmpeg не скомпилирован с поддержкой GPU")
                            logger.error("  3. Драйверы GPU не установлены или устарели")
                            logger.error("  4. GPU занят другим процессом")
                            logger.error("  5. Недостаточно памяти GPU")
                            logger.error("=" * 80)
                        
                        # Не продолжаем обработку при ошибке GPU - требуем исправления
                        raise Exception(f"Ошибка GPU при обработке копии {i+1}: {error_msg}")
                        
                except Exception as e:
                    logger.error("=" * 80)
                    logger.error(f"✗ КРИТИЧЕСКАЯ ОШИБКА ПРИ ОБРАБОТКЕ КОПИИ {i+1}")
                    logger.error("=" * 80)
                    logger.error(f"Тип ошибки: {type(e).__name__}")
                    logger.error(f"Сообщение: {str(e)}")
                    logger.error("=" * 80)
                    import traceback
                    logger.error("Полный traceback:")
                    logger.error(traceback.format_exc())
                    logger.error("=" * 80)
                    raise  # Пробрасываем ошибку дальше, не продолжаем
            
            if not video_files:
                raise Exception("Не удалось обработать ни одной копии видео")
            
            logger.info(f"Уникализация завершена. Получено {len(video_files)} видео из {copies} запрошенных")
            return video_files

        except Exception as e:
            logger.error(f"Ошибка уникализации видео: {str(e)}", exc_info=True)
            # Очищаем временные файлы при ошибке
            for video_file in video_files:
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                except:
                    pass
            raise Exception(f"Ошибка уникализации видео: {str(e)}")

    async def get_download_url(self, download_id: str, token: str) -> bytes:
        """
        Этот метод больше не используется, так как мы работаем локально.
        Оставлен для обратной совместимости.
        """
        logger.warning("get_download_url вызван, но не используется в локальном режиме")
        raise NotImplementedError("Локальный уникализатор не поддерживает скачивание по URL")


uniq_service = UniquizationService()
