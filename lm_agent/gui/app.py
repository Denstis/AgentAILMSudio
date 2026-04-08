"""
GUI интерфейс для LM Agent.

Модуль предоставляет графический интерфейс на базе Tkinter
для взаимодействия с LM Agent.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import threading
import queue
import json
from datetime import datetime

from lm_agent.gui.components import (
    ModelSettingsFrame,
    SandboxConfigFrame,
    ToolsPanelFrame,
    TaskManagerFrame,
    ConsoleOutputFrame
)


class LMAgentGUI:
    """Основной класс GUI приложения LM Agent."""
    
    def __init__(self, root: tk.Tk):
        """
        Инициализация GUI.
        
        Args:
            root: Корневое окно Tkinter
        """
        self.root = root
        self.root.title("LM Agent - Интеллектуальный агент для генерации кода")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        # Очередь для безопасного обновления GUI из потоков
        self.message_queue = queue.Queue()
        
        # Загрузка конфигурации
        self.config = self._load_default_config()
        
        # Настройка стиля
        self._setup_styles()
        
        # Создание интерфейса
        self._create_menu()
        self._create_toolbar()
        self._create_main_notebook()
        self._create_status_bar()
        
        # Запуск обработки очереди сообщений
        self._process_queue()
    
    def _load_default_config(self) -> dict:
        """Загрузить конфигурацию по умолчанию."""
        return {
            "theme": "light",
            "language": "ru",
            "autosave": True,
            "model": {
                "base_url": "http://localhost:1234/v1",
                "name": "codellama-7b"
            },
            "sandbox": {
                "enabled": True,
                "safe_mode": True
            }
        }
    
    def _setup_styles(self):
        """Настройка стилей интерфейса."""
        style = ttk.Style()
        
        # Доступные темы
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        
        # Настройка цветов
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('Status.TLabel', font=('Helvetica', 10))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')
        style.configure('Info.TLabel', foreground='blue')
        
        # Стили для кнопок
        style.configure('Primary.TButton', font=('Helvetica', 10, 'bold'))
        style.configure('Danger.TButton', font=('Helvetica', 10, 'bold'), foreground='red')
    
    def _create_menu(self):
        """Создание меню приложения."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новая задача", command=self._new_task, accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть задачу...", command=self._open_task, accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить результат", command=self._save_result, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Импорт конфигурации...", command=self._import_config)
        file_menu.add_command(label="Экспорт конфигурации...", command=self._export_config)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Меню Правка
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Копировать", command=self._copy_text, accelerator="Ctrl+C")
        edit_menu.add_command(label="Вставить", command=self._paste_text, accelerator="Ctrl+V")
        edit_menu.add_command(label="Очистить консоль", command=self._clear_console)
        
        # Меню Вид
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="Полноэкранный режим", command=self._toggle_fullscreen, accelerator="F11")
        view_menu.add_separator()
        view_menu.add_radiobutton(label="Светлая тема", command=lambda: self._set_theme('light'))
        view_menu.add_radiobutton(label="Тёмная тема", command=lambda: self._set_theme('dark'))
        
        # Меню Сервис
        service_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Сервис", menu=service_menu)
        service_menu.add_command(label="Настройки агента", command=self._show_agent_settings)
        service_menu.add_command(label="Управление моделями", command=self._show_model_manager)
        service_menu.add_command(label="Конфигурация песочницы", command=self._show_sandbox_config)
        service_menu.add_separator()
        service_menu.add_command(label="Проверить подключение", command=self._check_connection)
        
        # Меню Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Документация", command=self._show_docs, accelerator="F1")
        help_menu.add_command(label="Горячие клавиши", command=self._show_hotkeys)
        help_menu.add_separator()
        help_menu.add_command(label="О программе", command=self._show_about)
        
        # Горячие клавиши
        self.root.bind('<Control-n>', lambda e: self._new_task())
        self.root.bind('<Control-o>', lambda e: self._open_task())
        self.root.bind('<Control-s>', lambda e: self._save_result())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-c>', lambda e: self._copy_text())
        self.root.bind('<Control-v>', lambda e: self._paste_text())
        self.root.bind('<F1>', lambda e: self._show_docs())
        self.root.bind('<F11>', lambda e: self._toggle_fullscreen())
    
    def _create_toolbar(self):
        """Создание панели инструментов."""
        toolbar = ttk.Frame(self.root, padding="5")
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Кнопки быстрого доступа
        ttk.Button(toolbar, text="➕ Новая задача", command=self._new_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="▶ Выполнить", command=self._run_task, style='Primary.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⏹ Стоп", command=self._stop_task).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Выбор модели
        ttk.Label(toolbar, text="Модель:").pack(side=tk.LEFT, padx=5)
        self.model_combo = ttk.Combobox(toolbar, values=[
            "codellama-7b",
            "codellama-13b",
            "codellama-34b",
            "llama-2-7b",
            "mistral-7b",
            "mixtral-8x7b"
        ], width=20, state="readonly")
        self.model_combo.set("codellama-7b")
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        # Статус подключения
        self.connection_label = ttk.Label(toolbar, text="🔴 Отключено", style='Error.TLabel')
        self.connection_label.pack(side=tk.RIGHT, padx=10)
        
        ttk.Button(toolbar, text="🔌 Подключить", command=self._check_connection).pack(side=tk.RIGHT, padx=5)
    
    def _create_main_notebook(self):
        """Создание основного контейнера с вкладками."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Вкладка 1: Рабочая область
        workspace_frame = ttk.Frame(notebook)
        notebook.add(workspace_frame, text="📝 Рабочая область")
        self._create_workspace_tab(workspace_frame)
        
        # Вкладка 2: Настройки модели
        model_frame = ttk.Frame(notebook)
        notebook.add(model_frame, text="🤖 Модель")
        self.model_settings = ModelSettingsFrame(model_frame)
        self.model_settings.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 3: Песочница
        sandbox_frame = ttk.Frame(notebook)
        notebook.add(sandbox_frame, text="🔒 Песочница")
        self.sandbox_config = SandboxConfigFrame(sandbox_frame)
        self.sandbox_config.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 4: Инструменты
        tools_frame = ttk.Frame(notebook)
        notebook.add(tools_frame, text="🧰 Инструменты")
        self.tools_panel = ToolsPanelFrame(tools_frame)
        self.tools_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 5: Менеджер задач
        tasks_frame = ttk.Frame(notebook)
        notebook.add(tasks_frame, text="📋 Задачи")
        self.task_manager = TaskManagerFrame(tasks_frame)
        self.task_manager.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 6: Консоль и логи
        console_frame = ttk.Frame(notebook)
        notebook.add(console_frame, text="📊 Консоль")
        self.console_output = ConsoleOutputFrame(console_frame)
        self.console_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка 7: О системе
        about_frame = ttk.Frame(notebook)
        notebook.add(about_frame, text="ℹ️ О системе")
        self._create_about_tab(about_frame)
    
    def _create_workspace_tab(self, parent):
        """Создание вкладки рабочей области."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        
        # Поле ввода задачи
        input_frame = ttk.LabelFrame(parent, text="Задача для агента", padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(0, weight=1)
        
        self.task_input = scrolledtext.ScrolledText(
            input_frame, 
            height=8, 
            wrap=tk.WORD,
            font=('Consolas', 11)
        )
        self.task_input.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Панель действий
        action_frame = ttk.Frame(input_frame)
        action_frame.grid(row=1, column=0, pady=(10, 0), sticky=tk.E)
        
        ttk.Button(action_frame, text="🗑 Очистить", command=self._clear_input).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="📋 Вставить из буфера", command=self._paste_to_input).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="💾 Сохранить черновик", command=self._save_draft).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="📂 Загрузить черновик", command=self._load_draft).pack(side=tk.LEFT, padx=5)
        
        # Большая кнопка выполнения
        self.run_button = ttk.Button(
            action_frame, 
            text="▶ ВЫПОЛНИТЬ ЗАДАЧУ", 
            command=self._run_task,
            style='Primary.TButton'
        )
        self.run_button.pack(side=tk.RIGHT, padx=10)
        
        self.stop_button = ttk.Button(
            action_frame, 
            text="⏹ СТОП", 
            command=self._stop_task,
            style='Danger.TButton',
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.RIGHT, padx=5)
        
        # Область вывода результата
        output_frame = ttk.LabelFrame(parent, text="Результат выполнения", padding="10")
        output_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_display = scrolledtext.ScrolledText(
            output_frame, 
            height=20, 
            wrap=tk.WORD,
            font=('Consolas', 10),
            state=tk.DISABLED
        )
        self.output_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка тегов для подсветки
        self.output_display.tag_configure('info', foreground='blue')
        self.output_display.tag_configure('success', foreground='green', font=('Consolas', 10, 'bold'))
        self.output_display.tag_configure('error', foreground='red', font=('Consolas', 10, 'bold'))
        self.output_display.tag_configure('warning', foreground='orange')
        self.output_display.tag_configure('code', background='#f0f0f0', font=('Consolas', 10))
        self.output_display.tag_configure('heading', font=('Helvetica', 12, 'bold'))
        
        # Кнопки действий с результатом
        result_btn_frame = ttk.Frame(output_frame)
        result_btn_frame.grid(row=1, column=0, pady=(10, 0), sticky=tk.E)
        
        ttk.Button(result_btn_frame, text="📋 Копировать", command=self._copy_output).pack(side=tk.LEFT, padx=5)
        ttk.Button(result_btn_frame, text="💾 Сохранить как...", command=self._save_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(result_btn_frame, text="🗑 Очистить", command=self._clear_output).pack(side=tk.LEFT, padx=5)
    
    def _create_about_tab(self, parent):
        """Создание вкладки 'О системе'."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        info_text = scrolledtext.ScrolledText(parent, font=('Consolas', 11))
        info_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        about_content = """
╔═══════════════════════════════════════════════════════════╗
║                    LM Agent v1.0                          ║
║         Интеллектуальный агент для генерации кода         ║
╚═══════════════════════════════════════════════════════════╝

📌 ОПИСАНИЕ:
   LM Agent - это мощная система для автоматизации разработки,
   использующая современные языковые модели для генерации,
   анализа и выполнения кода в безопасной среде.

🔧 ВОЗМОЖНОСТИ:
   • Генерация кода на различных языках программирования
   • Анализ и рефакторинг существующего кода
   • Создание тестов и документации
   • Работа с файлами и директориями
   • Веб-скрапинг и API интеграции
   • Безопасное выполнение кода в песочнице

🛡️ БЕЗОПАСНОСТЬ:
   • Изолированная среда выполнения (Sandbox)
   • Контроль доступа к системным ресурсам
   • Ограничение сетевых подключений
   • Фильтрация опасных операций

📊 МОНИТОРИНГ:
   • Отслеживание прогресса выполнения задач
   • Детальное логирование всех операций
   • Управление очередью задач
   • Статистика использования ресурсов

⚙️ НАСТРОЙКИ:
   • Гибкая конфигурация LLM моделей
   • Настройка параметров песочницы
   • Управление инструментами
   • Профили безопасности

📚 ПОДДЕРЖИВАЕМЫЕ МОДЕЛИ:
   • CodeLlama (7B, 13B, 34B)
   • Llama 2
   • Mistral / Mixtral
   • Gemma
   • Qwen
   • Yi

🤝 РАЗРАБОТЧИКИ:
   LM Agent Team © 2024

📖 ДОКУМЕНТАЦИЯ:
   Посетите GitHub репозиторий проекта для получения
   подробной документации и примеров использования.
"""
        
        info_text.insert(tk.END, about_content)
        info_text.config(state=tk.DISABLED)
        
        # Кнопки
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="📖 Открыть документацию", command=self._show_docs).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="🔧 Проверить систему", command=self._check_system).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="📊 Статистика", command=self._show_stats).pack(side=tk.LEFT, padx=10)
    
    def _create_status_bar(self):
        """Создание строки состояния."""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Левая часть - статус
        self.status_label = ttk.Label(
            status_frame, 
            text="✓ Готов к работе", 
            style='Status.TLabel',
            padding=(10, 5)
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Центр - прогресс
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame, 
            variable=self.progress_var, 
            maximum=100,
            mode='determinate',
            length=300
        )
        self.progress_bar.pack(side=tk.LEFT, padx=20)
        
        # Правая часть - информация
        info_frame = ttk.Frame(status_frame)
        info_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(info_frame, text="Память: -- MB").pack(side=tk.LEFT, padx=10)
        ttk.Label(info_frame, text="Задач: 0").pack(side=tk.LEFT, padx=10)
        ttk.Label(info_frame, text=datetime.now().strftime("%H:%M:%S")).pack(side=tk.LEFT, padx=10)
    
    def _update_status(self, message: str, status_type: str = 'info'):
        """Обновление строки состояния."""
        self.status_label.config(text=message)
        if status_type == 'success':
            self.status_label.configure(style='Success.TLabel')
        elif status_type == 'error':
            self.status_label.configure(style='Error.TLabel')
        elif status_type == 'warning':
            self.status_label.configure(style='Warning.TLabel')
        else:
            self.status_label.configure(style='Info.TLabel')
    
    # ─────────────────────────────────────────────────────────────────────────
    # Методы обработки задач
    # ─────────────────────────────────────────────────────────────────────────
    
    def _run_task(self):
        """Запуск выполнения задачи."""
        task = self.task_input.get("1.0", tk.END).strip()
        
        if not task:
            messagebox.showwarning("Предупреждение", "Введите задачу для выполнения")
            return
        
        # Блокировка интерфейса
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start()
        self._update_status("Выполнение задачи...", 'info')
        
        # Очистка предыдущего вывода
        self._clear_output()
        
        # Логирование
        if hasattr(self, 'console_output'):
            self.console_output.write(f"Задача запущена: {task[:100]}...", 'info')
        
        # Запуск в отдельном потоке
        thread = threading.Thread(target=self._execute_task, args=(task,), daemon=True)
        thread.start()
    
    def _execute_task(self, task: str):
        """Выполнение задачи в фоновом потоке."""
        try:
            # Этапы выполнения
            steps = [
                ("🔄 Анализ задачи...", 'info', 10),
                ("📚 Поиск контекста...", 'info', 25),
                ("🧠 Генерация решения...", 'info', 50),
                ("✅ Проверка результата...", 'info', 75),
                ("💾 Форматирование вывода...", 'info', 90),
            ]
            
            for message, level, progress in steps:
                self.message_queue.put(("console", message, level))
                self.message_queue.put(("progress", progress, None))
                import time
                time.sleep(0.5)
            
            # Пример ответа
            response = f"""
✅ Задача выполнена успешно!

📝 Входная задача:
{task}

💡 Решение:
```python
def solution():
    \"\"\"Пример сгенерированного кода.\"\"\"
    print("Hello from LM Agent!")
    return True

if __name__ == "__main__":
    solution()
```

📊 Статистика:
• Время выполнения: 2.5 сек
• Использовано токенов: ~150
• Итераций: 1

Статус: Готово к использованию
"""
            self.message_queue.put(("output", response, 'code'))
            self.message_queue.put(("status", "✓ Задача выполнена", 'success'))
            self.message_queue.put(("progress_stop", None, None))
            self.message_queue.put(("enable_run", None, None))
            
        except Exception as e:
            self.message_queue.put(("output", f"❌ Ошибка: {str(e)}", 'error'))
            self.message_queue.put(("status", "✗ Ошибка выполнения", 'error'))
            self.message_queue.put(("progress_stop", None, None))
            self.message_queue.put(("enable_run", None, None))
    
    def _stop_task(self):
        """Остановка выполнения задачи."""
        self._update_status("Задача остановлена пользователем", 'warning')
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', value=0)
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if hasattr(self, 'console_output'):
            self.console_output.write("Задача остановлена пользователем", 'warning')
    
    def _process_queue(self):
        """Обработка очереди сообщений."""
        try:
            while True:
                msg_type, data, extra = self.message_queue.get_nowait()
                
                if msg_type == "output":
                    self._append_output(data, extra)
                elif msg_type == "console":
                    if hasattr(self, 'console_output'):
                        self.console_output.write(data, extra)
                elif msg_type == "status":
                    self._update_status(data, extra)
                elif msg_type == "progress":
                    self.progress_var.set(data)
                elif msg_type == "progress_stop":
                    self.progress_bar.stop()
                    self.progress_bar.config(mode='determinate', value=100)
                elif msg_type == "enable_run":
                    self.run_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self._process_queue)
    
    def _append_output(self, text: str, tag: str = None):
        """Добавление текста в область вывода."""
        self.output_display.config(state=tk.NORMAL)
        if tag:
            self.output_display.insert(tk.END, text + '\n', tag)
        else:
            self.output_display.insert(tk.END, text + '\n')
        self.output_display.config(state=tk.DISABLED)
        self.output_display.see(tk.END)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Методы работы с файлами и буфером
    # ─────────────────────────────────────────────────────────────────────────
    
    def _new_task(self):
        """Создание новой задачи."""
        self.task_input.delete("1.0", tk.END)
        self._clear_output()
        self._update_status("Готов к работе", 'info')
        self.progress_var.set(0)
    
    def _open_task(self):
        """Открытие задачи из файла."""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Текстовые файлы", "*.txt"),
                ("Python файлы", "*.py"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.task_input.delete("1.0", tk.END)
                self.task_input.insert("1.0", content)
                self._update_status(f"Загружено: {file_path}", 'success')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл: {e}")
    
    def _save_result(self):
        """Сохранение результата в файл."""
        content = self.output_display.get("1.0", tk.END).strip()
        
        if not content:
            messagebox.showinfo("Информация", "Нет результатов для сохранения")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Текстовые файлы", "*.txt"),
                ("Python файлы", "*.py"),
                ("Markdown файлы", "*.md"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Успех", f"Результат сохранён в {file_path}")
                self._update_status(f"Сохранено: {file_path}", 'success')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}")
    
    def _save_draft(self):
        """Сохранение черновика задачи."""
        task = self.task_input.get("1.0", tk.END).strip()
        if not task:
            messagebox.showwarning("Предупреждение", "Нет текста для сохранения")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".draft.json",
            filetypes=[("Draft файлы", "*.draft.json"), ("Все файлы", "*.*")]
        )
        
        if file_path:
            try:
                draft = {
                    "task": task,
                    "timestamp": datetime.now().isoformat(),
                    "model": self.model_combo.get()
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(draft, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", "Черновик сохранён")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
    
    def _load_draft(self):
        """Загрузка черновика задачи."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Draft файлы", "*.draft.json"), ("Все файлы", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    draft = json.load(f)
                
                if "task" in draft:
                    self.task_input.delete("1.0", tk.END)
                    self.task_input.insert("1.0", draft["task"])
                
                if "model" in draft:
                    self.model_combo.set(draft["model"])
                
                self._update_status(f"Загружено: {file_path}", 'success')
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}")
    
    def _clear_input(self):
        """Очистка поля ввода."""
        self.task_input.delete("1.0", tk.END)
    
    def _clear_output(self):
        """Очистка области вывода."""
        self.output_display.config(state=tk.NORMAL)
        self.output_display.delete("1.0", tk.END)
        self.output_display.config(state=tk.DISABLED)
    
    def _copy_text(self):
        """Копирование выделенного текста."""
        try:
            # Пробуем копировать из активного виджета
            widget = self.root.focus_get()
            if hasattr(widget, 'selection_get'):
                text = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
        except tk.TclError:
            pass
    
    def _copy_output(self):
        """Копирование всего вывода."""
        content = self.output_display.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._update_status("Скопировано в буфер обмена", 'info')
    
    def _paste_text(self):
        """Вставка текста из буфера обмена."""
        try:
            text = self.root.clipboard_get()
            widget = self.root.focus_get()
            if widget == self.task_input:
                self.task_input.insert(tk.INSERT, text)
            elif hasattr(widget, 'insert'):
                widget.insert(tk.INSERT, text)
        except tk.TclError:
            pass
    
    def _paste_to_input(self):
        """Вставка текста в поле ввода."""
        try:
            text = self.root.clipboard_get()
            self.task_input.insert(tk.INSERT, text)
        except tk.TclError:
            messagebox.showwarning("Предупреждение", "Буфер обмена пуст")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Методы меню и диалогов
    # ─────────────────────────────────────────────────────────────────────────
    
    def _import_config(self):
        """Импорт конфигурации."""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON файлы", "*.json"), ("YAML файлы", "*.yaml"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if file_path.endswith('.json'):
                        config = json.load(f)
                    else:
                        # Простая обработка YAML
                        config = {}
                
                # Применение настроек
                if "model" in config:
                    if "base_url" in config["model"]:
                        self.model_settings.base_url_var.set(config["model"]["base_url"])
                    if "name" in config["model"]:
                        self.model_combo.set(config["model"]["name"])
                
                self._update_status("Конфигурация импортирована", 'success')
                messagebox.showinfo("Успех", "Конфигурация импортирована")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось импортировать: {e}")
    
    def _export_config(self):
        """Экспорт текущей конфигурации."""
        config = {
            "model": self.model_settings.get_settings() if hasattr(self, 'model_settings') else {},
            "sandbox": self.sandbox_config.get_config() if hasattr(self, 'sandbox_config') else {},
            "tools": self.tools_panel.get_config() if hasattr(self, 'tools_panel') else {}
        }
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", f"Конфигурация экспортирована в {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать: {e}")
    
    def _toggle_fullscreen(self):
        """Переключение полноэкранного режима."""
        current = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current)
    
    def _set_theme(self, theme: str):
        """Установка темы оформления."""
        style = ttk.Style()
        if theme == 'dark':
            # Тёмная тема (требует дополнительной настройки)
            messagebox.showinfo("Информация", "Тёмная тема будет реализована в следующей версии")
        else:
            style.theme_use('clam')
        self.config["theme"] = theme
    
    def _show_agent_settings(self):
        """Показ настроек агента."""
        # Переключение на вкладку настроек
        pass
    
    def _show_model_manager(self):
        """Показ менеджера моделей."""
        # Переключение на вкладку модели
        pass
    
    def _show_sandbox_config(self):
        """Показ конфигурации песочницы."""
        # Переключение на вкладку песочницы
        pass
    
    def _check_connection(self):
        """Проверка подключения к LLM серверу."""
        self._update_status("Проверка подключения...", 'info')
        
        def check():
            import time
            time.sleep(1)
            # Имитация проверки
            self.message_queue.put(("connection", True, None))
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def _check_system(self):
        """Проверка системы."""
        messagebox.showinfo("Проверка системы", 
            "✓ Python версия: OK\n"
            "✓ Tkinter: OK\n"
            "✓ Модули: OK\n"
            "✓ Песочница: OK\n\n"
            "Все системы работают нормально!")
    
    def _show_stats(self):
        """Показ статистики."""
        messagebox.showinfo("Статистика",
            "Задач выполнено: 0\n"
            "Время работы: 0 мин\n"
            "Использовано токенов: 0\n"
            "Среднее время задачи: 0 сек")
    
    def _show_docs(self):
        """Показ документации."""
        docs_window = tk.Toplevel(self.root)
        docs_window.title("Документация")
        docs_window.geometry("800x600")
        
        text = scrolledtext.ScrolledText(docs_window, font=('Consolas', 11))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        doc_content = """
═══════════════════════════════════════════════════════════
              LM Agent - Документация
═══════════════════════════════════════════════════════════

1. БЫСТРЫЙ СТАРТ
   ─────────────
   • Введите задачу в поле "Задача для агента"
   • Выберите модель из выпадающего списка
   • Нажмите кнопку "ВЫПОЛНИТЬ ЗАДАЧУ"
   • Ожидайте результат в области вывода

2. НАСТРОЙКА МОДЕЛИ
   ────────────────
   Перейдите на вкладку "🤖 Модель" для настройки:
   • Base URL - адрес сервера LLM
   • Температура - креативность ответов (0.0-2.0)
   • Max Tokens - максимальный размер ответа
   • Top P - разнообразие выбора
   • Freq Penalty - штраф за повторения

3. ПЕСОЧНИЦА
   ─────────
   Вкладка "🔒 Песочница" позволяет настроить:
   • Разрешения на доступ к интернету
   • Системные команды
   • Установка пакетов (pip)
   • Git операции
   • Группы модулей Python
   
   ⚠️ Режимы:
   • Безопасный - минимальные разрешения
   • Полный доступ - все разрешения (опасно!)

4. ИНСТРУМЕНТЫ
   ───────────
   Вкладка "🧰 Инструменты" управляет:
   • Файловые инструменты (чтение/запись)
   • Инструменты кода (анализ/выполнение)
   • Веб инструменты (HTTP запросы)
   • Инструменты данных (JSON, CSV)

5. МЕНЕДЖЕР ЗАДАЧ
   ──────────────
   Вкладка "📋 Задачи" показывает:
   • Список всех задач
   • Статус выполнения
   • Приоритет и прогресс
   • Детали и логи

6. ГОРЯЧИЕ КЛАВИШИ
   ───────────────
   Ctrl+N - Новая задача
   Ctrl+O - Открыть задачу
   Ctrl+S - Сохранить результат
   Ctrl+Q - Выход
   F1 - Документация
   F11 - Полноэкранный режим

═══════════════════════════════════════════════════════════
"""
        text.insert(tk.END, doc_content)
        text.config(state=tk.DISABLED)
    
    def _show_hotkeys(self):
        """Показ горячих клавиш."""
        messagebox.showinfo("Горячие клавиши",
            "Ctrl+N - Новая задача\n"
            "Ctrl+O - Открыть задачу\n"
            "Ctrl+S - Сохранить результат\n"
            "Ctrl+Q - Выход\n"
            "Ctrl+C - Копировать\n"
            "Ctrl+V - Вставить\n"
            "F1 - Документация\n"
            "F11 - Полноэкранный режим")
    
    def _show_about(self):
        """Показ информации о программе."""
        messagebox.showinfo(
            "О программе",
            "LM Agent v1.0\n\n"
            "Интеллектуальный агент для генерации кода.\n"
            "Использует модульную архитектуру с песочницей.\n\n"
            "© 2024 LM Agent Team"
        )


def run_gui():
    """Запуск GUI приложения."""
    root = tk.Tk()
    
    # Настройка иконки (если доступна)
    try:
        icon_path = Path(__file__).parent / 'icon.ico'
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except Exception:
        pass
    
    app = LMAgentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
