# Быстрый старт

## Шаг 1: Установка FFmpeg с поддержкой GPU

**⚠️ ВАЖНО: Уникализатор требует GPU для работы!**

### Windows (NVIDIA)
1. Скачайте FFmpeg с поддержкой CUDA: https://www.gyan.dev/ffmpeg/builds/
2. Выберите версию "ffmpeg-release-essentials.zip" или "ffmpeg-release-full.zip"
3. Распакуйте архив
4. Добавьте папку `bin` в PATH системы
5. Проверьте: `ffmpeg -encoders | findstr nvenc`

### Linux (NVIDIA)
```bash
sudo apt install ffmpeg
# Убедитесь, что установлены драйверы NVIDIA и CUDA
ffmpeg -encoders | grep nvenc
```

### Linux (Intel QSV)
```bash
sudo apt install ffmpeg
# Убедитесь, что установлены драйверы Intel Media SDK
ffmpeg -encoders | grep qsv
```

### Mac
```bash
brew install ffmpeg
# VideoToolbox поддерживается по умолчанию
ffmpeg -encoders | grep videotoolbox
```

## Шаг 2: Установка зависимостей Python

```bash
pip install -r requirements.txt
```

## Шаг 3: Использование

### Вариант 1: Обработка всех видео в папке input/
1. Поместите видео файлы в папку `input/`
2. Запустите скрипт:
```bash
python video_uniqueizer.py
```
3. Обработанные видео появятся в папке `output/`

### Вариант 2: Обработка конкретного файла
```bash
# Обработать один файл
python video_uniqueizer.py video.mp4

# С указанием выходного файла
python video_uniqueizer.py video.mp4 -o output.mp4
```

## Пример

```bash
# Создайте папку input и поместите туда видео
mkdir input
cp your_video.mp4 input/

# Запустите обработку
python video_uniqueizer.py

# Результат будет в output/your_video.mp4
```

## Что делает скрипт

- ✅ Обрабатывает все видео в папке `input/`
- ✅ Применяет случайные незаметные модификации
- ✅ Сохраняет исходное разрешение
- ✅ Удаляет все метаданные
- ✅ Сохраняет высокое качество
- ✅ Каждое видео получает уникальные параметры

## Поддерживаемые форматы

- .mp4
- .mov
- .avi
- .mkv

