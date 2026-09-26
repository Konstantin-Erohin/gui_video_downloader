# Video Downloader — Tkinter + yt-dlp

Простое настольное приложение для Windows и macOS для скачивания видео с помощью `yt-dlp`.

Интерфейс написан на Tkinter. Получение информации о видео и скачивание выполняются в отдельном потоке, поэтому интерфейс приложения остаётся отзывчивым во время работы.

## Возможности

- получение информации о видео по URL;
- получение доступных вариантов качества;
- выбор качества видео;
- выбор папки для сохранения;
- отображение прогресса скачивания;
- отображение текущего этапа работы;
- отображение предупреждений `yt-dlp`;
- объединение отдельных видео- и аудиопотоков через FFmpeg;
- поддержка macOS Apple Silicon (ARM64);
- поддержка Windows x64;
- включение FFmpeg, ffprobe и Deno в готовую сборку.

Плейлисты и текущие прямые эфиры не поддерживаются.

Ссылка на отдельное видео, содержащая параметры плейлиста, обрабатывается как ссылка на одно видео.

---

# Архитектура проекта

Приложение разделено на графический интерфейс, логику скачивания и систему сборки.

```text
┌──────────────────────────────┐
│            app.py            │
│                              │
│        Tkinter GUI           │
│ URL / качество / папка       │
│ прогресс / статус / ошибки   │
└──────────────┬───────────────┘
               │
               │ запуск задачи
               ▼
┌──────────────────────────────┐
│       фоновый поток          │
│                              │
│        downloader.py         │
│          yt-dlp              │
│     FFmpeg / ffprobe         │
│           Deno               │
└──────────────┬───────────────┘
               │
               │ события
               ▼
┌──────────────────────────────┐
│        queue.Queue           │
│                              │
│ progress / stage / warning   │
│ inspected / downloaded       │
│ error                        │
└──────────────┬───────────────┘
               │
               │ poll()
               ▼
┌──────────────────────────────┐
│      главный поток GUI       │
│                              │
│   обновление интерфейса      │
└──────────────────────────────┘
```

## `app.py`

Содержит графический интерфейс Tkinter.

Отвечает за:

- ввод URL;
- получение доступных качеств;
- отображение названия видео;
- выбор качества;
- выбор папки сохранения;
- запуск скачивания;
- отображение прогресса;
- отображение статуса, предупреждений и ошибок.

Tkinter работает в главном потоке приложения.

Сетевые операции и скачивание непосредственно в главном потоке не выполняются, поскольку длительная операция заблокировала бы интерфейс.

Для получения информации о видео и скачивания создаётся отдельный фоновый поток.

## `downloader.py`

Содержит основную логику работы с `yt-dlp`.

Модуль отвечает за:

- получение информации о видео;
- получение списка доступных качеств;
- выбор формата;
- скачивание видео;
- передачу прогресса в интерфейс;
- поиск FFmpeg и ffprobe;
- использование Deno для JavaScript-компонентов `yt-dlp`.

Для ограничения выбранного качества используется фильтр `yt-dlp`:

```text
bestvideo[height<=QUALITY]+bestaudio/best[height<=QUALITY]
```

Выбранное качество является верхней границей. Например, при выборе `1080p`, если подходящий формат 1080p отсутствует, `yt-dlp` может выбрать более низкое качество.

Если видео и аудио предоставляются сайтом отдельными потоками, они скачиваются отдельно и затем объединяются FFmpeg.

## Очередь событий

Фоновый поток не изменяет Tkinter-виджеты напрямую.

Для обмена данными между фоновым и главным потоками используется потокобезопасная очередь:

```python
queue.Queue
```

Фоновая задача помещает в очередь события:

```text
progress
stage
warning
inspected
downloaded
error
```

Главный поток Tkinter периодически проверяет очередь с помощью `after()` и обновляет интерфейс.

Такая архитектура позволяет:

- сохранять отзывчивость интерфейса;
- выполнять скачивание в фоне;
- безопасно обновлять Tkinter;
- передавать прогресс, этапы работы, предупреждения и ошибки в GUI.

## `build.py`

Содержит конфигурацию сборки приложения через PyInstaller.

Скрипт:

1. определяет текущую операционную систему;
2. определяет архитектуру используемого Python;
3. проверяет наличие FFmpeg и ffprobe;
4. добавляет FFmpeg и ffprobe в приложение;
5. добавляет Deno, если он находится в `bin/`;
6. включает модули и ресурсы `yt-dlp`;
7. включает `yt-dlp-ejs`, если пакет установлен;
8. устанавливает иконку приложения;
9. запускает PyInstaller.

Windows собирается в один `.exe`.

macOS собирается как `.app`.

---

# Структура проекта

```text
tk_downloader/
├── app.py
├── downloader.py
├── build.py
│
├── README.md
├── requirements.txt
├── requirements-build.txt
│
├── assets/
│   ├── icon.ico
│   └── icon.icns
│
├── bin/
│   ├── README.md
│   ├── ffmpeg / ffmpeg.exe
│   ├── ffprobe / ffprobe.exe
│   └── deno / deno.exe
│
└── tests/
    └── test_downloader.py
```

На macOS:

```text
bin/
├── ffmpeg
├── ffprobe
└── deno
```

На Windows:

```text
bin/
├── ffmpeg.exe
├── ffprobe.exe
└── deno.exe
```

---

# Поддерживаемые платформы

Проект рассчитан на две целевые платформы:

```text
macOS Apple Silicon (ARM64)
Windows x64 (Intel/AMD)
```

Для каждой платформы необходимо использовать соответствующие версии Python, FFmpeg, ffprobe и Deno.

## macOS Apple Silicon

Используются:

```text
macOS ARM64 Python
macOS ARM64 FFmpeg
macOS ARM64 ffprobe
macOS ARM64 Deno
```

Результат сборки:

```text
dist/VideoDownloader-macOS-arm64.app
```

## Windows x64

Используются:

```text
Windows x64 Python
Windows x64 FFmpeg
Windows x64 ffprobe
Windows x64 Deno
```

Результат сборки:

```text
dist/VideoDownloader-Windows-x64.exe
```

Бинарники разных операционных систем и архитектур нельзя смешивать.

---

# Требования

Для запуска из исходного кода требуется:

- Python 3.10 или новее;
- Tkinter;
- зависимости из `requirements.txt`;
- FFmpeg;
- ffprobe;
- Deno для полноценной поддержки YouTube.

Для создания готового приложения дополнительно требуются зависимости из:

```text
requirements-build.txt
```

---

# Бинарники FFmpeg, ffprobe и Deno

Готовые бинарники для поддерживаемых платформ можно скачать здесь:

**Google Drive:**  
`https://drive.google.com/drive/folders/1NIN4KmOYF3LU_Nzp808dwdH6PUnt6LSj?usp=share_link`

Доступны два комплекта:

```text
macOS Apple Silicon (ARM64)
Windows x64
```

Необходимо скачать комплект для нужной операционной системы и поместить файлы в папку `bin/`.

## macOS Apple Silicon

В `bin/` должны находиться:

```text
bin/
├── ffmpeg
├── ffprobe
└── deno
```

После копирования необходимо дать бинарникам право на выполнение:

```bash
chmod +x bin/ffmpeg bin/ffprobe bin/deno
```

Проверка:

```bash
./bin/ffmpeg -version
./bin/ffprobe -version
./bin/deno --version
```

## Windows x64

В `bin/` должны находиться:

```text
bin/
├── ffmpeg.exe
├── ffprobe.exe
└── deno.exe
```

Дополнительный `chmod` на Windows не требуется.

Проверка из PowerShell:

```powershell
.\bin\ffmpeg.exe -version
.\bin\ffprobe.exe -version
.\bin\deno.exe --version
```

---

# Иконки приложения

Для сборки используются разные форматы иконок.

macOS:

```text
assets/icon.icns
```

Windows:

```text
assets/icon.ico
```

Обе иконки можно создать из одного исходного PNG размером `1024×1024`.

`build.py` передаёт соответствующую иконку PyInstaller в зависимости от операционной системы.

---

# Запуск из исходного кода на macOS Apple Silicon

## 1. Установка Python

Необходим Python 3.10 или новее с Tkinter.

При использовании Homebrew Python 3.12 Tkinter можно установить командой:

```bash
brew install python-tk@3.12
```

Проверка:

```bash
python3.12 -m tkinter
```

Должно открыться тестовое окно Tkinter.

## 2. Создание виртуального окружения

Перейти в папку проекта:

```bash
cd ~/projects/tk_downloader
```

Создать виртуальное окружение:

```bash
python3.12 -m venv .venv
```

Активировать:

```bash
source .venv/bin/activate
```

## 3. Установка зависимостей

```bash
python -m pip install -U pip
python -m pip install -U -r requirements.txt
```

## 4. Подготовка бинарников

Поместить в `bin/`:

```text
ffmpeg
ffprobe
deno
```

Дать бинарникам право на выполнение:

```bash
chmod +x bin/ffmpeg bin/ffprobe bin/deno
```

## 5. Запуск

```bash
python app.py
```

---

# Запуск из исходного кода на Windows x64

## 1. Установка Python

Установить Python 3.10 или новее x64 с поддержкой Tcl/Tk.

Проверка Tkinter:

```powershell
py -3.12 -m tkinter
```

## 2. Создание виртуального окружения

В PowerShell перейти в папку проекта и выполнить:

```powershell
py -3.12 -m venv .venv
```

## 3. Установка зависимостей

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -U -r requirements.txt
```

## 4. Подготовка бинарников

Поместить в `bin/`:

```text
ffmpeg.exe
ffprobe.exe
deno.exe
```

## 5. Запуск

```powershell
.\.venv\Scripts\python.exe app.py
```

Активация виртуального окружения не обязательна.

---

# Сборка приложения

Для сборки используется PyInstaller.

Сборка выполняется отдельно для каждой целевой платформы:

```text
macOS Apple Silicon → .app
Windows x64         → .exe
```

Python, FFmpeg, ffprobe и Deno должны соответствовать целевой операционной системе и архитектуре.

---

# Сборка macOS Apple Silicon

## 1. Перейти в папку проекта

```bash
cd ~/projects/tk_downloader
```

## 2. Активировать виртуальное окружение

```bash
source .venv/bin/activate
```

## 3. Установить зависимости сборки

```bash
python -m pip install -U -r requirements-build.txt
```

## 4. Проверить бинарники

В `bin/` должны находиться:

```text
ffmpeg
ffprobe
deno
```

Установить права на выполнение:

```bash
chmod +x bin/ffmpeg bin/ffprobe bin/deno
```

Проверить бинарники:

```bash
./bin/ffmpeg -version
./bin/ffprobe -version
./bin/deno --version
```

## 5. Проверить иконку

Должен существовать файл:

```text
assets/icon.icns
```

## 6. Запустить сборку

```bash
python build.py
```

Результат:

```text
dist/VideoDownloader-macOS-arm64.app
```

macOS использует `onedir`-сборку PyInstaller. Распространять необходимо весь `.app`.

Автоматическая подпись Developer ID и notarization в проекте не настроены.

---

# Сборка Windows x64

## 1. Установить зависимости сборки

```powershell
.\.venv\Scripts\python.exe -m pip install -U -r requirements-build.txt
```

## 2. Проверить бинарники

В `bin/` должны находиться:

```text
ffmpeg.exe
ffprobe.exe
deno.exe
```

Проверить:

```powershell
.\bin\ffmpeg.exe -version
.\bin\ffprobe.exe -version
.\bin\deno.exe --version
```

## 3. Проверить иконку

Должен существовать файл:

```text
assets/icon.ico
```

## 4. Запустить сборку

```powershell
.\.venv\Scripts\python.exe build.py
```

Результат:

```text
dist/VideoDownloader-Windows-x64.exe
```

Windows использует `onefile`-сборку PyInstaller.

Python, библиотеки приложения, FFmpeg, ffprobe и Deno включаются в итоговый `.exe`. На компьютере, где запускается готовое приложение, отдельно устанавливать Python, FFmpeg или Deno не требуется.

---

# Сборка Windows x64 через UTM на Apple Silicon

На Mac с Apple Silicon можно использовать Windows ARM64 в UTM для создания Windows-сборки.

Для получения приложения для обычных Windows-компьютеров на Intel/AMD внутри Windows ARM64 необходимо использовать x64-компоненты под эмуляцией:

```text
Python x64
FFmpeg x64
ffprobe x64
Deno x64
```

Сборка запускается:

```powershell
.\.venv\Scripts\python.exe build.py
```

Результат:

```text
dist/VideoDownloader-Windows-x64.exe
```

Итоговый `.exe` рекомендуется дополнительно проверить на обычной Windows x64.

---

# FFmpeg

FFmpeg используется для обработки и объединения видео- и аудиопотоков.

`ffmpeg` и `ffprobe` являются отдельными исполняемыми программами. Python-пакет с названием `ffmpeg` не заменяет эти бинарники.

Приложение сначала ищет соответствующие файлы внутри `bin/`, а затем может использовать программы из `PATH`.

При сборке локальные бинарники из `bin/` включаются PyInstaller в готовое приложение.

---

# Deno и YouTube

`yt-dlp` использует JavaScript-компоненты для полноценной обработки некоторых сайтов, в частности YouTube.

Deno используется как JavaScript runtime.

На macOS:

```text
bin/deno
```

На Windows:

```text
bin/deno.exe
```

При наличии локального Deno `build.py` включает его в готовое приложение.

Без JavaScript runtime часть форматов YouTube может быть недоступна.

---

# Файлы результата

PyInstaller создаёт служебные каталоги:

```text
build/
dist/
```

Также создаётся файл:

```text
*.spec
```

Готовое приложение находится в:

```text
dist/
```

Служебные файлы сборки не требуется хранить в Git.

---

# Состав Git-репозитория

В Git хранятся исходный код, документация, тесты и файлы зависимостей:

```text
app.py
downloader.py
build.py
README.md
requirements.txt
requirements-build.txt
assets/
tests/
bin/README.md
```

Не требуется хранить:

```text
.venv/
build/
dist/
__pycache__/
*.spec
```

Бинарники:

```text
ffmpeg
ffprobe
deno
```

и их Windows-версии также не требуется хранить в Git. Они скачиваются отдельно с Google Drive и помещаются в `bin/` перед запуском или сборкой.

---

# Проверка проекта

Проверка Python-файлов:

```bash
python -m compileall -q app.py downloader.py build.py tests
```

Запуск тестов:

```bash
python -m unittest discover -s tests -v
```

Обновление зависимостей:

```bash
python -m pip install -U -r requirements.txt
```

Тесты не скачивают внешние видео.

Для ручной проверки приложения рекомендуется проверить:

- получение информации о публичном видео;
- получение списка качеств;
- выбор качества;
- выбор папки;
- скачивание видео;
- наличие изображения и звука в результате;
- отображение прогресса;
- неверный URL;
- недоступное видео;
- отсутствие FFmpeg;
- предупреждения `yt-dlp`.

После обновления `yt-dlp` готовое приложение необходимо собрать заново.

---

# Обновление yt-dlp

Поддержка сайтов со временем меняется, поэтому при проблемах со скачиванием в первую очередь следует обновить зависимости:

```bash
python -m pip install -U -r requirements.txt
```

После обновления рекомендуется запустить тесты и вручную проверить скачивание.

Для сохранения точных версий рабочего окружения:

```bash
python -m pip freeze > requirements-lock.txt
```

---

# Ограничения

В текущей версии не реализованы:

- очередь нескольких загрузок;
- отмена текущей загрузки;
- скачивание плейлистов;
- скачивание текущих прямых эфиров;
- cookies и авторизация через интерфейс.

Видео, требующие входа в аккаунт или недоступные в конкретном регионе, могут не скачиваться.

---

# Используемые компоненты

Проект использует:

- Python;
- Tkinter;
- yt-dlp;
- FFmpeg;
- ffprobe;
- Deno;
- PyInstaller.

Перед распространением готовых сборок необходимо учитывать лицензии включённых сторонних компонентов.
