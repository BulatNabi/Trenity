#!/usr/bin/env python3
"""
Trenity Video Uniqueizer
Локальная пакетная уникализация видео с помощью FFmpeg

Скрипт обрабатывает все видео файлы в папке input,
применяет случайные незаметные модификации для уникализации
и сохраняет результаты в папку output.
"""

import os
import sys
import subprocess
import random
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Установите tqdm для отображения прогресс-бара: pip install tqdm")


# Поддерживаемые форматы видео
SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi',
                        '.mkv', '.MP4', '.MOV', '.AVI', '.MKV'}

# Директории по умолчанию
INPUT_DIR = "input"
OUTPUT_DIR = "output"
LOG_FILE = "uniqueizer.log"


def check_ffmpeg() -> bool:
    """Проверяет наличие FFmpeg в системе"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def detect_gpu_acceleration() -> Optional[dict]:
    """
    Определяет доступное GPU-ускорение в системе

    Returns:
        dict с информацией о GPU или None если GPU не найден
        Формат: {'type': 'nvenc'|'qsv'|'amf'|'videotoolbox', 'encoder': 'h264_xxx', 'hwaccel': 'xxx'}
    """
    gpu_configs = [
        {
            'type': 'nvenc',
            'encoder': 'h264_nvenc',
            'hwaccel': 'cuda',
            'check_cmd': ['ffmpeg', '-hide_banner', '-encoders'],
            'check_string': 'h264_nvenc'
        },
        {
            'type': 'qsv',
            'encoder': 'h264_qsv',
            'hwaccel': 'qsv',
            'check_cmd': ['ffmpeg', '-hide_banner', '-encoders'],
            'check_string': 'h264_qsv'
        },
        {
            'type': 'amf',
            'encoder': 'h264_amf',
            'hwaccel': 'd3d11va',
            'check_cmd': ['ffmpeg', '-hide_banner', '-encoders'],
            'check_string': 'h264_amf'
        },
        {
            'type': 'videotoolbox',
            'encoder': 'h264_videotoolbox',
            'hwaccel': 'videotoolbox',
            'check_cmd': ['ffmpeg', '-hide_banner', '-encoders'],
            'check_string': 'h264_videotoolbox'
        }
    ]

    for config in gpu_configs:
        try:
            result = subprocess.run(
                config['check_cmd'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and config['check_string'] in result.stdout:
                print(f"✓ Обнаружено GPU-ускорение: {config['type'].upper()}")
                return config
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue

    return None


def create_directories():
    """Создает необходимые директории если их нет"""
    Path(INPUT_DIR).mkdir(exist_ok=True)
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    print(f"✓ Директории проверены: {INPUT_DIR}/ и {OUTPUT_DIR}/")


def get_video_files(input_dir: str) -> List[Path]:
    """Получает список всех видео файлов в директории"""
    video_files = []
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"✗ Директория {input_dir} не найдена!")
        return video_files

    for file in input_path.iterdir():
        if file.is_file() and file.suffix in SUPPORTED_EXTENSIONS:
            video_files.append(file)

    return sorted(video_files)


def get_video_resolution(video_path: Path) -> Optional[Tuple[int, int]]:
    """
    Получает разрешение видео (ширина x высота) с помощью FFprobe

    Returns:
        Tuple[int, int] или None в случае ошибки
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0',
            str(video_path)
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            dimensions = result.stdout.strip().split('x')
            if len(dimensions) == 2:
                width = int(dimensions[0])
                height = int(dimensions[1])
                return (width, height)
    except Exception as e:
        print(f"  ⚠ Предупреждение: не удалось определить разрешение: {e}")

    return None


def generate_random_filters(original_resolution: Optional[Tuple[int, int]] = None) -> str:
    """
    Генерирует случайные FFmpeg фильтры для уникализации видео

    Фильтр-цепочка применяется последовательно:
    1. noise - добавляет очень слабый шум для изменения пиксельных данных
    2. eq - корректирует цветовые параметры (яркость, контраст, насыщенность, гамма)

    Все параметры случайны для каждого файла, что обеспечивает уникальность
    MD5 хеша и отпечатков, при этом визуальные изменения минимальны.

    ВАЖНО: Фильтры НЕ изменяют разрешение (width x height) видео.

    Args:
        original_resolution: (width, height) исходного видео (не используется, но может быть полезен)

    Returns:
        Строка с FFmpeg фильтрами в формате "filter1,filter2"
    """
    filters = []

    # 1. Фильтр шума (noise)
    # noise=alls=X - добавляет шум ко всем каналам (RGB)
    # allf=t+u - временной и равномерный шум
    # Значение 0.3-0.8 = очень слабый шум (едва заметен, но изменяет пиксели)
    noise_strength = random.uniform(0.3, 0.8)
    filters.append(f"noise=alls={noise_strength}:allf=t+u")

    # 2. Фильтр коррекции цвета (eq - equalizer)
    # Применяет микро-изменения к цветовым параметрам
    # Все значения в очень узком диапазоне (±2-3%) для незаметности

    # brightness: -0.03 до +0.03 (изменение яркости на ±3%)
    brightness = random.uniform(-0.03, 0.03)

    # contrast: 0.98 до 1.02 (изменение контраста на ±2%)
    # 1.0 = исходный контраст, <1.0 = меньше контраста, >1.0 = больше контраста
    contrast = random.uniform(0.98, 1.02)

    # saturation: 0.98 до 1.02 (изменение насыщенности на ±2%)
    # 1.0 = исходная насыщенность, <1.0 = менее насыщенные цвета, >1.0 = более насыщенные
    saturation = random.uniform(0.98, 1.02)

    # gamma: 0.98 до 1.02 (изменение гаммы на ±2%)
    # 1.0 = исходная гамма, влияет на яркость средних тонов
    gamma = random.uniform(0.98, 1.02)

    # Формируем eq фильтр со всеми параметрами
    filters.append(
        f"eq=brightness={brightness:.4f}:contrast={contrast:.4f}:saturation={saturation:.4f}:gamma={gamma:.4f}")

    # Объединяем фильтры через запятую
    # FFmpeg применяет их последовательно: сначала noise, потом eq
    # Формат: "filter1,filter2" означает: применить filter1, затем filter2
    filter_chain = ",".join(filters)

    return filter_chain


def process_video(
    input_file: Path,
    output_file: Path,
    video_index: int,
    total_videos: int,
    gpu_config: Optional[dict] = None
) -> Tuple[bool, Optional[str]]:
    """
    Обрабатывает одно видео файл с применением уникализации

    Args:
        input_file: Путь к исходному видео
        output_file: Путь для сохранения обработанного видео
        video_index: Номер текущего видео (для прогресс-бара)
        total_videos: Общее количество видео

    Returns:
        Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
    """
    try:
        # Получаем разрешение исходного видео
        resolution = get_video_resolution(input_file)

        if resolution:
            width, height = resolution
            if not HAS_TQDM:
                print(f"  📐 Разрешение: {width}x{height} (будет сохранено)")
        else:
            if not HAS_TQDM:
                print(f"  ⚠ Не удалось определить разрешение, продолжаем...")

        # Генерируем случайные фильтры для этого файла
        filter_chain = generate_random_filters(resolution)

        # Генерируем случайный битрейт (небольшое изменение)
        # Определяем базовый битрейт на основе размера файла
        file_size_mb = input_file.stat().st_size / (1024 * 1024)
        base_bitrate = max(1000, int(file_size_mb * 200))  # Примерная оценка
        # Изменяем битрейт на ±5%
        bitrate = int(base_bitrate * random.uniform(0.95, 1.05))

        # Формируем команду FFmpeg с GPU-ускорением
        # Фильтр-цепочка объяснение:
        # 1. noise - добавляет очень слабый шум для изменения пикселей
        # 2. eq - корректирует цвет (яркость, контраст, насыщенность, гамма)
        # Оба фильтра применяются последовательно через запятую
        # Разрешение сохраняется автоматически (без scale/crop фильтров)
        cmd = ['ffmpeg']

        # Для GPU: декодируем на CPU (чтобы фильтры работали), кодируем на GPU
        # Hardware acceleration для декодирования не используем, так как фильтры работают на CPU
        # Это гибридный подход: CPU для фильтров, GPU для кодирования

        cmd.extend([
            '-i', str(input_file),
            # Удаляем все метаданные (изменяет файл на уровне метаданных)
            '-map_metadata', '-1',
        ])

        # Применяем фильтры уникализации на CPU
        # Фильтры noise и eq работают только на CPU, поэтому применяем их до GPU-кодирования
        cmd.extend(['-vf', filter_chain])

        # Выбираем кодек: GPU или CPU
        if gpu_config:
            # GPU кодирование - параметры зависят от типа GPU
            cmd.extend(['-c:v', gpu_config['encoder']])

            # Специфичные параметры для разных GPU
            if gpu_config['type'] == 'nvenc':
                # NVIDIA NVENC параметры
                # Используем preset p4 (balanced) для хорошего качества и скорости
                cmd.extend([
                    '-preset', 'p4',  # p1-p7: p1=fastest, p7=slowest but best quality
                    '-rc', 'vbr',  # Variable bitrate
                    '-b:v', f'{bitrate}k',  # Битрейт
                    # Максимальный битрейт
                    '-maxrate', f'{int(bitrate * 1.5)}k',
                    '-bufsize', f'{int(bitrate * 2)}k',  # Размер буфера
                    '-rc-lookahead', '20',  # Lookahead для лучшего качества
                    '-spatial-aq', '1',  # Spatial adaptive quantization
                    '-temporal-aq', '1',  # Temporal adaptive quantization
                    '-b_ref_mode', 'middle'  # B-frame reference mode
                ])
            elif gpu_config['type'] == 'qsv':
                # Intel QSV параметры
                # Используем global_quality вместо битрейта (аналог CRF)
                cmd.extend([
                    '-global_quality', '23',  # 1-51, где меньше = лучше качество
                    '-preset', 'balanced'  # fast, balanced, slow
                ])
            elif gpu_config['type'] == 'amf':
                # AMD AMF параметры
                # Используем quality preset вместо битрейта
                cmd.extend([
                    '-quality', 'balanced',  # speed, balanced, quality
                    '-rc', 'vbr_peak',  # Rate control mode
                    '-b:v', f'{bitrate}k'  # Битрейт
                ])
            elif gpu_config['type'] == 'videotoolbox':
                # Apple VideoToolbox параметры
                cmd.extend([
                    '-b:v', f'{bitrate}k',  # Битрейт
                    '-allow_sw', '1',  # Разрешить software fallback
                    '-realtime', '1'  # Режим реального времени
                ])
        else:
            # CPU кодирование (fallback, но не должно использоваться)
            cmd.extend([
                '-c:v', 'libx264',
                '-b:v', f'{bitrate}k',
                '-crf', '23',
            ])

        # Аудио и выходной файл
        cmd.extend([
            # Копируем аудио без изменений (быстрее и без потери качества)
            '-c:a', 'copy',
            # Перезаписываем выходной файл если существует
            '-y',
            # Выходной файл
            str(output_file)
        ])

        if not HAS_TQDM:
            gpu_info = f" (GPU: {gpu_config['type'].upper()})" if gpu_config else " (CPU)"
            print(f"  🔧 Фильтры: {filter_chain[:80]}...")
            print(f"  📊 Битрейт: {bitrate}k{gpu_info}")
            print(
                f"  🔧 Кодек: {gpu_config['encoder'] if gpu_config else 'libx264'}")

        # Выполняем команду FFmpeg
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # Таймаут 10 минут на файл
        )

        if process.returncode == 0:
            return (True, None)
        else:
            # Получаем полную ошибку
            error_output = process.stderr if process.stderr else process.stdout
            # Ищем реальную ошибку, пропуская информационные сообщения
            error_lines = error_output.split('\n')
            # Берем последние строки, где обычно находится ошибка
            error_text = '\n'.join(
                error_lines[-10:]) if len(error_lines) > 10 else error_output
            # Увеличиваем до 1000 символов
            error_msg = f"FFmpeg ошибка: {error_text[:1000]}"

            if not HAS_TQDM:
                # Показываем начало команды
                print(f"  ✗ Команда FFmpeg: {' '.join(cmd[:10])}...")
                print(f"  ✗ Детали ошибки: {error_text[:300]}")

            return (False, error_msg)

    except subprocess.TimeoutExpired:
        return (False, "Таймаут обработки (файл слишком большой или поврежден)")
    except Exception as e:
        return (False, f"Неожиданная ошибка: {str(e)}")


def log_error(message: str):
    """Записывает ошибку в лог файл"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")


def parse_arguments():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description='Trenity Video Uniqueizer - Локальная уникализация видео с помощью FFmpeg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python video_uniqueizer.py                          # Обработать все видео в папке input/
  python video_uniqueizer.py video.mp4                # Обработать один файл
  python video_uniqueizer.py /path/to/video.mp4       # Обработать файл по полному пути
  python video_uniqueizer.py /path/to/folder          # Обработать все видео в папке
  python video_uniqueizer.py video.mp4 -o output.mp4  # Указать выходной файл
        """
    )

    parser.add_argument(
        'input_path',
        nargs='?',
        default=None,
        help='Путь к видео файлу или папке с видео (по умолчанию: папка input/)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Путь к выходному файлу (только для одного файла)'
    )

    return parser.parse_args()


def get_video_files_from_path(input_path: str) -> List[Path]:
    """
    Получает список видео файлов из пути (файл или директория)

    Args:
        input_path: Путь к файлу или директории

    Returns:
        Список путей к видео файлам
    """
    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(f"Путь не найден: {input_path}")

    if path.is_file():
        # Это файл
        if path.suffix in SUPPORTED_EXTENSIONS:
            return [path]
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")
    elif path.is_dir():
        # Это директория
        return get_video_files(str(path))
    else:
        raise ValueError(f"Неизвестный тип пути: {input_path}")


def main():
    """Основная функция"""
    # Парсим аргументы
    args = parse_arguments()

    print("=" * 60)
    print("Trenity Video Uniqueizer")
    print("Локальная пакетная уникализация видео")
    print("=" * 60)
    print()

    # Проверяем FFmpeg
    if not check_ffmpeg():
        print("✗ ОШИБКА: FFmpeg не найден в системе!")
        print("  Установите FFmpeg и добавьте его в PATH")
        print("  Скачать: https://ffmpeg.org/download.html")
        sys.exit(1)
    print("✓ FFmpeg найден")

    # Определяем GPU-ускорение (обязательно)
    print("🔍 Поиск GPU-ускорения...")
    gpu_config = detect_gpu_acceleration()

    if not gpu_config:
        print("✗ ОШИБКА: GPU-ускорение не найдено!")
        print("  Уникализатор требует GPU для работы.")
        print("  Поддерживаемые GPU:")
        print("    - NVIDIA (CUDA/NVENC)")
        print("    - Intel (Quick Sync Video)")
        print("    - AMD (AMF)")
        print("    - Apple (VideoToolbox)")
        print()
        print("  Убедитесь, что:")
        print("    1. Установлены драйверы GPU")
        print("    2. FFmpeg скомпилирован с поддержкой GPU")
        print("    3. GPU доступен в системе")
        sys.exit(1)

    print(
        f"✓ GPU-ускорение: {gpu_config['type'].upper()} ({gpu_config['encoder']})")
    print()

    # Определяем входной путь
    if args.input_path:
        input_path = args.input_path
        print(f"📁 Входной путь: {input_path}")
    else:
        # Режим по умолчанию - папка input
        create_directories()
        input_path = INPUT_DIR
        print(f"📁 Используется папка по умолчанию: {INPUT_DIR}/")
    print()

    # Получаем список видео файлов
    try:
        video_files = get_video_files_from_path(input_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ ОШИБКА: {str(e)}")
        print(f"  Поддерживаемые форматы: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    if not video_files:
        print(f"✗ Видео файлы не найдены в: {input_path}")
        print(f"  Поддерживаемые форматы: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    print(f"✓ Найдено видео файлов: {len(video_files)}")
    print()

    # Очищаем лог файл
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    # Обрабатываем каждый файл
    successful = 0
    failed = 0

    if HAS_TQDM:
        iterator = tqdm(enumerate(video_files, 1),
                        total=len(video_files), desc="Обработка")
    else:
        iterator = enumerate(video_files, 1)

    for index, video_file in iterator:
        if not HAS_TQDM:
            print(f"[{index}/{len(video_files)}] Обработка: {video_file.name}")

        # Определяем выходной файл
        if args.output and len(video_files) == 1:
            # Если указан выходной файл и обрабатывается только один файл
            output_file = Path(args.output)
            # Создаем директорию если нужно
            output_file.parent.mkdir(parents=True, exist_ok=True)
        elif len(video_files) == 1:
            # Один файл без указания выхода - сохраняем рядом с исходным
            output_file = video_file.parent / \
                f"{video_file.stem}_unique{video_file.suffix}"
        else:
            # Несколько файлов - используем папку output
            Path(OUTPUT_DIR).mkdir(exist_ok=True)
            output_file = Path(OUTPUT_DIR) / video_file.name

        # Обрабатываем видео
        success, error_msg = process_video(
            video_file,
            output_file,
            index,
            len(video_files),
            gpu_config
        )

        if success:
            successful += 1
            if not HAS_TQDM:
                file_size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"  ✓ Успешно обработано: {output_file}")
                print(f"    Размер: {file_size_mb:.2f} MB")
        else:
            failed += 1
            error_log = f"Ошибка обработки {video_file.name}: {error_msg}"
            print(f"  ✗ {error_log}")
            log_error(error_log)

    print()
    print("=" * 60)
    print("Обработка завершена!")
    print(f"✓ Успешно: {successful}")
    print(f"✗ Ошибок: {failed}")
    if failed > 0:
        print(f"  Детали ошибок в файле: {LOG_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
