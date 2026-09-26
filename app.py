"""Простой загрузчик видео на tkinter. Запустить: python app.py."""
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from downloader import download_video, inspect_video, validate_url


class App(tk.Tk):
    def __init__(self):

        # Создаём главное окно; ниже задаём его заголовок и размеры.
        super().__init__()

        # Иконка окна Tkinter.
        # При обычном запуске берём PNG из папки проекта.
        # В PyInstaller-сборке — из временной папки _MEIPASS.
        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / 'assets' / 'icon.png'
        else:
            icon_path = Path(__file__).resolve().parent / 'assets' / 'icon.png'

        self.app_icon = tk.PhotoImage(file=icon_path)
        self.iconphoto(True, self.app_icon)
        
        self.title('Video Downloader')
        self.geometry('730x420')
        self.minsize(600, 400)

        # Состояние приложения. Очередь безопасно передаёт события из фонового потока.
        # busy блокирует новые операции, inspected_url хранит URL полученных качеств.
        self.events = queue.Queue()
        self.busy = False
        self.inspected_url = None

        # Переменные Tkinter связывают значения Python с полями и подписями окна.
        # Вызов .set() автоматически обновляет связанный виджет.
        self.url = tk.StringVar()
        self.quality = tk.StringVar()

        # Начальная папка: Movies на macOS, Videos на остальных системах.
        self.folder = tk.StringVar(value=str(Path.home() / ('Movies' if sys.platform == 'darwin' else 'Videos')))
        self.status = tk.StringVar(value='Вставьте ссылку и получите список качеств.')
        self.title_text = tk.StringVar()
        self.warning = tk.StringVar()

        # Общий контейнер с внутренними отступами. pack размещает его в окне,
        # а grid ниже размещает элементы внутри него — это разные родители.
        body = ttk.Frame(self, padding=20)
        body.pack(fill='both', expand=True)

        # Первая колонка получает свободное место при расширении окна.
        body.columnconfigure(0, weight=1)

        # Блок URL и кнопка запроса форматов. command получает функцию без вызова.
        # sticky="ew" растягивает поле по горизонтали; padx/pady задают отступы.
        ttk.Label(body, text='Ссылка на видео').grid(row=0, column=0, sticky='w')
        self.url_entry = ttk.Entry(body, textvariable=self.url)
        self.url_entry.grid(row=1, column=0, sticky='ew', pady=(4, 12))
        self.inspect_button = ttk.Button(body, text='Получить качества', command=self.inspect)
        self.inspect_button.grid(row=1, column=1, padx=(10, 0), pady=(4, 12))

        # Название видео занимает две колонки; wraplength задаёт перенос текста.
        ttk.Label(body, textvariable=self.title_text, wraplength=660).grid(row=2, column=0, columnspan=2, sticky='w')

        # Блок качества. Список включается после успешного получения форматов.
        ttk.Label(body, text='Качество (по дефолту максимальное)').grid(row=3, column=0, sticky='w', pady=(12, 4))
        self.combo = ttk.Combobox(body, textvariable=self.quality, state='disabled', width=18)
        self.combo.grid(row=4, column=0, sticky='w')

        # Блок папки сохранения: путь можно ввести вручную или выбрать в диалоге.
        ttk.Label(body, text='Папка сохранения').grid(row=5, column=0, sticky='w', pady=(12, 4))
        self.folder_entry = ttk.Entry(body, textvariable=self.folder)
        self.folder_entry.grid(row=6, column=0, sticky='ew')
        self.browse_button = ttk.Button(body, text='Выбрать…', command=self.browse)
        self.browse_button.grid(row=6, column=1, padx=(10, 0))

        # Кнопка скачивания недоступна до получения качеств для текущей ссылки.
        self.download_button = ttk.Button(body, text='Скачать', command=self.download, state='disabled')
        self.download_button.grid(row=7, column=0, sticky='w', pady=16)

        # Прогресс текущего потока (видео или аудио), статус и предупреждения.
        # При неизвестном размере или объединении вместо процента показываем анимацию.
        self.bar = ttk.Progressbar(body, maximum=100)
        self.bar.grid(row=8, column=0, columnspan=2, sticky='ew')
        ttk.Label(body, textvariable=self.status, wraplength=660).grid(row=9, column=0, columnspan=2, sticky='w', pady=8)
        ttk.Label(body, textvariable=self.warning, wraplength=660, foreground='#986000').grid(row=10, column=0, columnspan=2, sticky='w')

        # Обработчики событий. Изменение URL сбрасывает старые качества.
        self.url.trace_add('write', self.invalidate)

        # Перехватываем закрытие окна, чтобы не оборвать работающий загрузчик.
        self.protocol('WM_DELETE_WINDOW', self.close)

        # Планируем чтение очереди через 100 мс, не блокируя интерфейс.
        # after срабатывает один раз; poll планирует следующий вызов заново.
        self.after(100, self.poll)

    # Сбрасываем результат предыдущего запроса при изменении ссылки.
    def invalidate(self, *_):
        if self.url.get().strip() != self.inspected_url:
            self.inspected_url = None
            self.quality.set('')
            self.combo.configure(values=(), state='disabled')
            self.title_text.set('')
            self.download_button.configure(state='disabled')

    # Открываем системный диалог; при отмене оставляем прежний путь.
    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get(), parent=self)
        if folder:
            self.folder.set(folder)

    # Блокируем изменение параметров и повторный запуск на время операции.
    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.url_entry, self.folder_entry, self.browse_button, self.inspect_button):
            widget.configure(state='disabled' if busy else 'normal')
        self.combo.configure(state='readonly' if not busy and self.inspected_url else 'disabled')
        self.download_button.configure(state='normal' if not busy and self.inspected_url else 'disabled')

    # Общий запуск получения форматов или скачивания в отдельном потоке.
    def launch(self, operation, *args):
        self.set_busy(True)
        self.warning.set('')
        self.bar.configure(mode='indeterminate', value=0)
        self.bar.start(12)

        # Фоновый поток не обращается к Tkinter: все изменения окна идут через очередь.
        def worker():
            last_progress = 0.0

            # Обратный вызов для downloader: упаковывает сообщение в пару (тип, данные).
            def emit(kind, value):
                nonlocal last_progress
                # Обновляем прогресс не чаще раза в 0,15 с, чтобы не переполнять очередь.
                now = time.monotonic()
                if kind == 'progress' and now - last_progress < 0.15:
                    return
                if kind == 'progress':
                    last_progress = now
                self.events.put((kind, value))

            try:

                # Передаём функции обычные данные и emit для отправки промежуточных событий.
                result = operation(*args, emit)
                self.events.put(('inspected' if operation is inspect_video else 'downloaded', result))

            # Ошибку тоже передаём в очередь; диалог покажет главный поток.
            except Exception as exc:
                self.events.put(('error', str(exc)))

        # Запускаем работу без ожидания результата в главном потоке.
        threading.Thread(target=worker, daemon=True).start()

    # Проверяем URL и запрашиваем метаданные без скачивания самого видео.
    def inspect(self):
        if self.busy:
            return
        try:
            url = validate_url(self.url.get())
        except ValueError as exc:
            messagebox.showerror('Ссылка', str(exc), parent=self)
            return
        self.inspected_url = None
        self.quality.set('')
        self.title_text.set('')
        self.status.set('Получение доступных разрешений…')
        self.launch(inspect_video, url)

    # Читаем поля окна до запуска потока; Tkinter-переменные в поток не передаём.
    def download(self):
        if self.busy or not self.inspected_url:
            return
        if not self.folder.get().strip():
            messagebox.showerror('Папка', 'Выберите папку сохранения.', parent=self)
            return
        quality = int(self.quality.get().removesuffix('p'))
        self.status.set(f'Подготовка скачивания {quality}p…')
        self.launch(download_video, self.inspected_url, quality, self.folder.get().strip())

    # Обрабатываем события в главном потоке, где разрешено обновлять виджеты.
    def poll(self):

        # Лимит на один проход не даёт большой очереди надолго занять интерфейс.
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'warning':
                self.warning.set(value)
            elif kind == 'progress':
                percent, text = value
                if percent is not None:
                    self.bar.stop()
                    self.bar.configure(mode='determinate', value=percent)
                    text += f' · {percent:.1f}% потока'
                elif self.bar['mode'] != 'indeterminate':
                    self.bar.configure(mode='indeterminate')
                    self.bar.start(12)
                self.status.set(text)

            # Для объединения FFmpeg процент неизвестен — запускаем анимацию.
            elif kind == 'stage':
                self.bar.stop()
                self.bar.configure(mode='indeterminate')
                self.bar.start(12)
                self.status.set(value)
            else:
                self.bar.stop()
                self.bar.configure(mode='determinate', value=0)
                if kind == 'inspected':
                    self.inspected_url = self.url.get().strip()
                    values = [f'{q}p' for q in value['qualities']]
                    self.combo.configure(values=values)
                    self.quality.set(values[-1])
                    self.title_text.set(f"Название видео: {value['title']}")
                    self.status.set('Выберите качество и нажмите «Скачать».')
                elif kind == 'downloaded':
                    self.bar.configure(value=100)
                    self.status.set(f'Готово. Файл сохранён в {value}')
                elif kind == 'error':
                    self.status.set('Операция не завершена. Можно повторить попытку.')
                    messagebox.showerror('Ошибка', value, parent=self)

                # После результата или ошибки снова разрешаем действия пользователя.
                self.set_busy(False)

        # Планируем чтение очереди через 100 мс, не блокируя интерфейс.
        # after срабатывает один раз; poll планирует следующий вызов заново.
        self.after(100, self.poll)

    # Отмена не реализована: разрешаем закрытие только после завершения операции.
    def close(self):
        if self.busy:
            messagebox.showinfo('Операция выполняется', 'Дождитесь завершения операции перед закрытием окна.', parent=self)
            return
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
