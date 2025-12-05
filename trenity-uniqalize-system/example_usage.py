#!/usr/bin/env python3
"""
Пример использования Trenity Video Uniqueizer

Этот скрипт демонстрирует, как можно программно использовать
функции уникализатора для обработки видео.
"""

from video_uniqueizer import (
    check_ffmpeg,
    create_directories,
    get_video_files,
    process_video
)
from pathlib import Path

def example_batch_processing():
    """Пример пакетной обработки"""
    print("Пример использования Video Uniqueizer")
    print("=" * 50)
    
    # Проверяем FFmpeg
    if not check_ffmpeg():
        print("FFmpeg не найден!")
        return
    
    # Создаем директории
    create_directories()
    
    # Получаем список видео
    videos = get_video_files("input")
    print(f"Найдено видео: {len(videos)}")
    
    # Обрабатываем первое видео как пример
    if videos:
        video = videos[0]
        output = Path("output") / video.name
        success, error = process_video(video, output, 1, 1)
        if success:
            print(f"✓ Пример обработан: {output}")
        else:
            print(f"✗ Ошибка: {error}")

if __name__ == "__main__":
    example_batch_processing()

