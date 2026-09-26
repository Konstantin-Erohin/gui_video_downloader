"""Сборка на целевой ОС с использованием Python нужной архитектуры."""
import importlib.util
import platform
import subprocess
import sys
from pathlib import Path


# Сборка запускается на целевой ОС и использует Python текущего окружения.
def main():

    # Пути вычисляем от файла скрипта, а не от папки запуска команды.
    root = Path(__file__).resolve().parent
    if sys.platform not in ('win32', 'darwin'):
        raise SystemExit('Сборка поддерживается на Windows и macOS.')

    # Выбираем расширения бинарников и формат иконки для текущей ОС.
    icon = root / 'assets' / ('icon.ico' if sys.platform == 'win32' else 'icon.icns')

    # Проверяем наличие иконки приложения.
    if not icon.is_file():
        raise SystemExit(f'Не найдена иконка {icon}.')

    # Включаем FFmpeg и ffprobe из bin; проверяем наличие и возможность запуска.
    suffix = '.exe' if sys.platform == 'win32' else ''
    binaries = [root / 'bin' / (name + suffix) for name in ('ffmpeg', 'ffprobe')]

    # До сборки проверяем каждый бинарник запуском с параметром -version.
    for binary in binaries:
        if not binary.is_file():
            raise SystemExit(f'Не найден {binary}. См. bin/README.md.')
        subprocess.run([str(binary), '-version'], check=True, capture_output=True)

    # Имя результата содержит ОС и архитектуру используемого Python.
    name = 'VideoDownloader-' + ('Windows' if sys.platform == 'win32' else 'macOS')
    arch = platform.machine().lower()
    arch = {
        'amd64': 'x64',
        'x86_64': 'x64',
        'aarch64': 'arm64'
    }.get(arch, arch)
    name += '-' + arch

    # Запускаем PyInstaller тем же Python.
    # Windows получает один EXE, macOS — пакет .app.
    # collect-all включает динамически загружаемые модули и ресурсы yt-dlp.
    cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onefile' if sys.platform == 'win32' else '--onedir',
        '--name',
        name,
        '--icon',
        str(icon),
        '--collect-all',
        'yt_dlp'
    ]

    # При наличии добавляем JS-компоненты yt-dlp для обработки YouTube.
    if importlib.util.find_spec('yt_dlp_ejs'):
        cmd += ['--collect-all', 'yt_dlp_ejs']

    # Deno включается только если пользователь положил его в bin.
    deno = root / 'bin' / ('deno' + suffix)
    if deno.is_file():
        binaries.append(deno)

    # Каждый бинарник помещаем в bin внутри приложения; там его найдёт downloader.
    for binary in binaries:
        cmd += ['--add-binary', f'{binary}:bin']
    cmd.append(str(root / 'app.py'))

    # Сборка выполняется в папке проекта. При ошибке завершаемся с исключением.
    subprocess.run(cmd, cwd=root, check=True)


if __name__ == '__main__':
    main()
