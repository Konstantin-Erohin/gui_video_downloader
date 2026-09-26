"""Получение информации и скачивание через yt-dlp без обращения к виджетам Tkinter."""
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse


# Проверяем форму ссылки; доступность сайта проверит yt-dlp при запросе.
def validate_url(url):
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('Вставьте корректную ссылку http:// или https://.')
    return url


# Собираем уникальные качества видео, исключая аудио, неизвестные кодеки и DRM.
def available_qualities(info):
    if not info or info.get('_type') in ('playlist', 'multi_video'):
        raise ValueError('Нужна ссылка на одно видео, а не на плейлист.')
    if info.get('is_live'):
        raise ValueError('Дождитесь окончания трансляции и используйте ссылку на запись.')

    # Множество убирает дубликаты: одному качеству могут соответствовать разные кодеки.
    qualities = {
        int(f['height']) for f in info.get('formats', [])
        if isinstance(f.get('height'), (int, float)) and f['height'] > 0
        and f.get('vcodec') not in (None, 'none') and not f.get('has_drm')
    }
    if not qualities:
        raise ValueError('Не найдены доступные качества видео.')
    return sorted(qualities)


# Выбранное качество задаёт максимальное разрешение видео.
# Сначала ищем отдельные видео и аудио.
# После / указан резерв: готовый формат с обеими дорожками, если пары нет.
# Это резерв выбора формата, а не повтор после сетевой ошибки.
def format_selector(quality):
    quality = int(quality)
    if quality <= 0:
        raise ValueError('Некорректное качество.')
    return f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'


# В сборке PyInstaller ресурсы находятся в _MEIPASS, при запуске исходников — рядом с файлом.
def bundled_bin():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'bin'


# Сначала ищем оба бинарника в bin проекта/сборки, затем в системном PATH.
def find_ffmpeg():
    suffix = '.exe' if sys.platform == 'win32' else ''
    folder = bundled_bin()
    if all((folder / (name + suffix)).is_file() for name in ('ffmpeg', 'ffprobe')):
        return str(folder)
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg and shutil.which('ffprobe'):
        return ffmpeg
    raise RuntimeError(
        'Не найдены FFmpeg и ffprobe. '
        'Поместите их в bin или добавьте в PATH (см. README).'
    )


# Адаптер сообщений yt-dlp. Служебный вывод пропускаем, предупреждения отправляем в GUI.
class Logger:
    def __init__(self, emit):
        self.emit = emit

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        self.emit('warning', str(message))

    def error(self, message):
        # yt-dlp также выбрасывает DownloadError; его обработает фоновый поток.
        pass


# Общие настройки запроса: одно видео, ограниченные повторы и отсутствие консольного прогресса.
def common_options(emit):
    opts = {
        'noplaylist': True,
        'quiet': True,
        'noprogress': True,
        'logger': Logger(emit),
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'cachedir': False
    }

    # Если Deno включён в приложение, явно передаём путь движка JavaScript yt-dlp.
    deno = bundled_bin() / ('deno.exe' if sys.platform == 'win32' else 'deno')
    if deno.is_file():
        opts['js_runtimes'] = {'deno': {'path': str(deno)}}
    return opts


# Получаем только метаданные; возвращаем окну название и отсортированные качества.
def inspect_video(url, emit):
    import yt_dlp

    with yt_dlp.YoutubeDL(common_options(emit)) as ydl:
        info = ydl.extract_info(validate_url(url), download=False)

    return {
        'title': info.get('title', 'Видео') if info else '',
        'qualities': available_qualities(info)
    }


# Скачиваем потоки выбранного качества и дожидаемся окончания их объединения.
def download_video(url, quality, folder, emit):
    import yt_dlp

    # Проверяем наличие инструментов до начала скачивания и готовим папку результата.
    ffmpeg = find_ffmpeg()
    folder = Path(folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)

    # yt-dlp вызывает этот обработчик по мере скачивания каждого потока.
    def progress(data):
        if data['status'] == 'downloading':

            # Точный размер бывает неизвестен; используем оценку, а без неё не вычисляем процент.
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            downloaded = data.get('downloaded_bytes', 0)
            percent = min(100, downloaded / total * 100) if total else None
            kind = 'Аудио' if data.get('info_dict', {}).get('vcodec') == 'none' else 'Видео'
            speed = data.get('speed')
            text = f'{kind}: {downloaded / 1048576:.1f} МБ'

            if speed:
                text += f' · {speed / 1048576:.1f} МБ/с'
            if data.get('eta') is not None:
                text += f' · осталось {data["eta"]} с'

            emit('progress', (percent, text))

        # Завершился только текущий поток; аудио или объединение ещё могут выполняться.
        elif data['status'] == 'finished':
            emit('stage', 'Поток загружен. Подготовка следующего этапа…')

    # Отдельный обработчик сообщает о начале постобработки, включая объединение.
    def postprocess(data):
        if data['status'] == 'started':
            emit('stage', 'Обработка и объединение видео/аудио через FFmpeg…')

    opts = common_options(emit)

    # Шаблон имени содержит название и id; 180B ограничивает длину названия в байтах.
    # MKV используется при объединении разных дорожек без перекодирования.
    # hooks передают прогресс через emit; существующие файлы не перезаписываются.
    opts.update({
        'format': format_selector(quality),
        'ffmpeg_location': ffmpeg,
        'paths': {'home': str(folder)},
        'outtmpl': '%(title).180B [%(id)s].%(ext)s',
        'windowsfilenames': True,
        'overwrites': False,
        'merge_output_format': 'mkv',
        'progress_hooks': [progress],
        'postprocessor_hooks': [postprocess]
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.download([validate_url(url)])

    # Ненулевой код означает ошибку; успешный возврат происходит после постобработки.
    if result:
        raise RuntimeError('Не удалось завершить загрузку.')

    return str(folder)