import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from downloader import available_heights, find_ffmpeg, format_selector, validate_url


# Проверяем логику без сети, запуска окна и скачивания реального видео.
# unittest.TestCase предоставляет проверки assertEqual, assertRaises и другие.
class DownloaderTests(unittest.TestCase):
    # В список качеств должны попасть только уникальные высоты подходящих видео.
    def test_heights_exclude_audio_drm_and_unknown_codec(self):
        # Два кодека для 720p проверяют удаление дубликатов. DRM, аудио и записи
        # без высоты или известного видеокодека не должны попасть в результат.
        formats = [
            {'height': 720, 'vcodec': 'h264'},
            {'height': 720, 'vcodec': 'vp9'},
            {'height': 1080, 'vcodec': 'av1'},
            {'height': 2160, 'vcodec': 'av1', 'has_drm': True},
            {'height': 480, 'vcodec': 'none'},
            {'height': 360}, {'vcodec': 'h264'},
        ]
        # Проверяем и состав списка, и порядок высот по возрастанию.
        self.assertEqual(available_heights({'formats': formats}), [720, 1080])

    # Пустые метаданные, плейлист и текущий эфир должны отклоняться.
    def test_empty_playlist_and_live_fail(self):
        for info in (None, {}, {'_type': 'playlist'}, {'is_live': True}):
            # subTest отмечает конкретный неудачный набор данных и позволяет
            # продолжить остальные случаи. assertRaises ожидает указанную ошибку.
            with self.subTest(info=info), self.assertRaises(ValueError):
                available_heights(info)

    # Проверяем форму URL и удаление пробелов; доступность сайта здесь не проверяется.
    def test_url_validation(self):
        self.assertEqual(validate_url(' https://example.com/video '), 'https://example.com/video')
        # Отклоняем пустую строку, локальный файл, URL без адреса и адрес без схемы.
        for url in ('', 'file:///tmp/video', 'https://', 'example.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    # Фиксируем исходную логику: видео до выбранной высоты + лучшее аудио,
    # а при отсутствии пары — готовый смешанный формат до той же высоты.
    def test_original_format_filter(self):
        self.assertEqual(format_selector(720), 'bestvideo[height<=720]+bestaudio/best[height<=720]')
        # Нулевая высота недопустима и не должна превращаться в фильтр yt-dlp.
        with self.assertRaises(ValueError):
            format_selector(0)

    # Отсутствие FFmpeg должно приводить к понятной ошибке независимо от настроек Mac/Windows.
    def test_missing_ffmpeg_is_clear_error(self):
        # Временная пустая папка имитирует bin без бинарников и удаляется при выходе.
        with tempfile.TemporaryDirectory() as folder:
            # Подменяем поиск bin и поиск в PATH именно там, где их вызывает downloader.
            # Даже установленный на машине FFmpeg не повлияет на этот тест.
            # При выходе из with исходные функции автоматически восстанавливаются.
            with patch('downloader.bundled_bin', return_value=Path(folder)), patch('downloader.shutil.which', return_value=None):
                # Проверяем тип ошибки и наличие слова FFmpeg в её сообщении.
                with self.assertRaisesRegex(RuntimeError, 'FFmpeg'):
                    find_ffmpeg()


# Позволяет запустить тестовый модуль как программу; также работает unittest discover.
if __name__ == '__main__':
    unittest.main()
