"""
GUI компоненты для LM Agent.

Модуль содержит переиспользуемые компоненты интерфейса:
- Настройки моделей
- Управление инструментами
- Конфигуратор песочницы
- Менеджер задач
- Мониторинг агентов
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, colorchooser
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
import json


# ─────────────────────────────────────────────────────────────────────────────
# Компонент: Настройки LLM модели
# ─────────────────────────────────────────────────────────────────────────────
class ModelSettingsFrame(ttk.LabelFrame):
    """Фрейм настройки параметров LLM модели."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="🤖 Настройки модели", **kwargs)
        
        self.columnconfigure(1, weight=1)
        
        # URL сервера
        ttk.Label(self, text="Base URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.base_url_var = tk.StringVar(value="http://localhost:1234/v1")
        self.base_url_entry = ttk.Entry(self, textvariable=self.base_url_var, width=50)
        self.base_url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Название модели
        ttk.Label(self, text="Модель:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.model_name_var = tk.StringVar(value="codellama-7b")
        self.model_name_entry = ttk.Combobox(
            self, 
            textvariable=self.model_name_var,
            values=[
                "codellama-7b",
                "codellama-13b", 
                "codellama-34b",
                "llama-2-7b",
                "llama-2-13b",
                "mistral-7b",
                "mixtral-8x7b",
                "gemma-7b",
                "qwen-7b",
                "yi-34b"
            ],
            width=47
        )
        self.model_name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Температура
        ttk.Label(self, text="Temperature:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.temperature_var = tk.DoubleVar(value=0.7)
        self.temperature_scale = ttk.Scale(
            self, 
            from_=0.0, 
            to=2.0, 
            variable=self.temperature_var,
            orient=tk.HORIZONTAL,
            length=300
        )
        self.temperature_scale.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.temp_value_label = ttk.Label(self, text="0.70", width=6)
        self.temp_value_label.grid(row=2, column=2, pady=5)
        
        # Max tokens
        ttk.Label(self, text="Max Tokens:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_tokens_var = tk.IntVar(value=4096)
        self.max_tokens_spin = ttk.Spinbox(
            self, 
            from_=256, 
            to=32768, 
            increment=256,
            textvariable=self.max_tokens_var,
            width=20
        )
        self.max_tokens_spin.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        
        # Top P
        ttk.Label(self, text="Top P:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.top_p_var = tk.DoubleVar(value=0.9)
        self.top_p_scale = ttk.Scale(
            self, 
            from_=0.0, 
            to=1.0, 
            variable=self.top_p_var,
            orient=tk.HORIZONTAL,
            length=300
        )
        self.top_p_scale.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
        self.top_p_value_label = ttk.Label(self, text="0.90", width=6)
        self.top_p_value_label.grid(row=4, column=2, pady=5)
        
        # Frequency Penalty
        ttk.Label(self, text="Freq Penalty:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.freq_penalty_var = tk.DoubleVar(value=0.5)
        self.freq_penalty_scale = ttk.Scale(
            self, 
            from_=-2.0, 
            to=2.0, 
            variable=self.freq_penalty_var,
            orient=tk.HORIZONTAL,
            length=300
        )
        self.freq_penalty_scale.grid(row=5, column=1, sticky=tk.W, pady=5, padx=5)
        self.freq_penalty_value_label = ttk.Label(self, text="0.50", width=6)
        self.freq_penalty_value_label.grid(row=5, column=2, pady=5)
        
        # Таймаут
        ttk.Label(self, text="Таймаут (сек):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.timeout_var = tk.IntVar(value=120)
        self.timeout_spin = ttk.Spinbox(
            self, 
            from_=10, 
            to=600, 
            increment=10,
            textvariable=self.timeout_var,
            width=20
        )
        self.timeout_spin.grid(row=6, column=1, sticky=tk.W, pady=5, padx=5)
        
        # Кнопки управления
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=7, column=0, columnspan=3, pady=10)
        
        ttk.Button(btn_frame, text="💾 Сохранить", command=self._save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 Загрузить", command=self._load_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Сбросить", command=self._reset_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔍 Проверить", command=self._test_connection).pack(side=tk.LEFT, padx=5)
        
        # Обновление меток значений
        self._update_labels()
        
    def _update_labels(self):
        """Обновить метки значений ползунков."""
        def update_temp(*args):
            self.temp_value_label.config(text=f"{self.temperature_var.get():.2f}")
        def update_top_p(*args):
            self.top_p_value_label.config(text=f"{self.top_p_var.get():.2f}")
        def update_freq(*args):
            self.freq_penalty_value_label.config(text=f"{self.freq_penalty_var.get():.2f}")
        
        self.temperature_var.trace_add('write', update_temp)
        self.top_p_var.trace_add('write', update_top_p)
        self.freq_penalty_var.trace_add('write', update_freq)
    
    def _save_settings(self):
        """Сохранить настройки в файл."""
        settings = self.get_settings()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", f"Настройки сохранены в {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
    
    def _load_settings(self):
        """Загрузить настройки из файла."""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                self.set_settings(settings)
                messagebox.showinfo("Успех", "Настройки загружены")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}")
    
    def _reset_settings(self):
        """Сбросить настройки к значениям по умолчанию."""
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки к значениям по умолчанию?"):
            self.base_url_var.set("http://localhost:1234/v1")
            self.model_name_var.set("codellama-7b")
            self.temperature_var.set(0.7)
            self.max_tokens_var.set(4096)
            self.top_p_var.set(0.9)
            self.freq_penalty_var.set(0.5)
            self.timeout_var.set(120)
    
    def _test_connection(self):
        """Проверить подключение к LLM серверу."""
        from lm_agent.api.lmstudio import LMStudioClient, LMStudioAPIError
        
        base_url = self.base_url_var.get()
        model_name = self.model_name_var.get()
        
        try:
            client = LMStudioClient(base_url=base_url)
            models = client.list_models(force_refresh=True)
            
            available_models = [model.id for model in models.models]
            
            if model_name in available_models:
                status = f"✓ Модель '{model_name}' доступна"
            else:
                status = f"⚠ Модель '{model_name}' не найдена\nДоступные модели:\n" + "\n".join(available_models[:10])
            
            messagebox.showinfo("Проверка подключения", 
                f"✓ Подключение успешно!\n\n"
                f"URL: {base_url}\n"
                f"Найдено моделей: {len(available_models)}\n\n"
                f"{status}")
        except LMStudioAPIError as e:
            messagebox.showerror("Ошибка подключения", 
                f"Не удалось подключиться к серверу:\n{e}\n\n"
                f"URL: {base_url}\n"
                f"Убедитесь, что LM Studio запущен")
        except Exception as e:
            messagebox.showerror("Ошибка", 
                f"Ошибка при проверке подключения:\n{e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Получить текущие настройки."""
        return {
            "base_url": self.base_url_var.get(),
            "model_name": self.model_name_var.get(),
            "temperature": self.temperature_var.get(),
            "max_tokens": self.max_tokens_var.get(),
            "top_p": self.top_p_var.get(),
            "frequency_penalty": self.freq_penalty_var.get(),
            "timeout": self.timeout_var.get()
        }
    
    def set_settings(self, settings: Dict[str, Any]):
        """Установить настройки."""
        if "base_url" in settings:
            self.base_url_var.set(settings["base_url"])
        if "model_name" in settings:
            self.model_name_var.set(settings["model_name"])
        if "temperature" in settings:
            self.temperature_var.set(settings["temperature"])
        if "max_tokens" in settings:
            self.max_tokens_var.set(settings["max_tokens"])
        if "top_p" in settings:
            self.top_p_var.set(settings["top_p"])
        if "frequency_penalty" in settings:
            self.freq_penalty_var.set(settings["frequency_penalty"])
        if "timeout" in settings:
            self.timeout_var.set(settings["timeout"])


# ─────────────────────────────────────────────────────────────────────────────
# Компонент: Конфигуратор песочницы
# ─────────────────────────────────────────────────────────────────────────────
class SandboxConfigFrame(ttk.LabelFrame):
    """Фрейм конфигурации песочницы."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="🔒 Песочница (Sandbox)", **kwargs)
        
        # Разрешения - основные
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(main_frame, text="Основные разрешения:", font=('Helvetica', 10, 'bold')).pack(anchor=tk.W)
        
        self.enable_internet_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="🌐 Доступ к интернету", 
                       variable=self.enable_internet_var).pack(anchor=tk.W)
        
        self.enable_system_cmds_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="💻 Системные команды", 
                       variable=self.enable_system_cmds_var).pack(anchor=tk.W)
        
        self.enable_pip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="📦 Установка пакетов (pip)", 
                       variable=self.enable_pip_var).pack(anchor=tk.W)
        
        self.enable_git_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="🔀 Git операции", 
                       variable=self.enable_git_var).pack(anchor=tk.W)
        
        self.enable_venv_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="🐍 Виртуальные окружения", 
                       variable=self.enable_venv_var).pack(anchor=tk.W)
        
        # Группы модулей
        modules_frame = ttk.Frame(self)
        modules_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(modules_frame, text="Группы модулей:", font=('Helvetica', 10, 'bold')).pack(anchor=tk.W)
        
        self.enable_math_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(modules_frame, text="📐 Математические модули", 
                       variable=self.enable_math_var).pack(anchor=tk.W)
        
        self.enable_science_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(modules_frame, text="🔬 Научные библиотеки", 
                       variable=self.enable_science_var).pack(anchor=tk.W)
        
        self.enable_testing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(modules_frame, text="✅ Тестовые фреймворки", 
                       variable=self.enable_testing_var).pack(anchor=tk.W)
        
        self.enable_gui_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(modules_frame, text="🖼️ GUI библиотеки", 
                       variable=self.enable_gui_var).pack(anchor=tk.W)
        
        self.enable_network_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(modules_frame, text="🔗 Сетевые операции", 
                       variable=self.enable_network_var).pack(anchor=tk.W)
        
        # Опасные опции
        danger_frame = ttk.Frame(self)
        danger_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.enable_all_modules_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(danger_frame, text="⚠️ ВСЕ модули (ОПАСНО!)", 
                       variable=self.enable_all_modules_var,
                       style='Danger.TCheckbutton').pack(anchor=tk.W)
        
        # Настройки путей и таймаутов
        settings_frame = ttk.LabelFrame(self, text="Дополнительные настройки")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Рабочая директория
        ttk.Label(settings_frame, text="Рабочая директория:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.work_dir_var = tk.StringVar(value="~/lm_agent_sandbox")
        ttk.Entry(settings_frame, textvariable=self.work_dir_var, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(settings_frame, text="...", command=self._browse_work_dir).grid(row=0, column=2, pady=5)
        
        # Pip индекс
        ttk.Label(settings_frame, text="Pip индекс URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.pip_index_var = tk.StringVar(value="https://pypi.org/simple")
        ttk.Entry(settings_frame, textvariable=self.pip_index_var, width=50).grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Таймауты
        ttk.Label(settings_frame, text="Max pip таймаут (сек):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_pip_timeout_var = tk.IntVar(value=120)
        ttk.Spinbox(settings_frame, from_=10, to=600, textvariable=self.max_pip_timeout_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(settings_frame, text="Max git таймаут (сек):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_git_timeout_var = tk.IntVar(value=300)
        ttk.Spinbox(settings_frame, from_=10, to=1800, textvariable=self.max_git_timeout_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Пользовательские списки
        custom_frame = ttk.LabelFrame(self, text="Пользовательские настройки")
        custom_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(custom_frame, text="Разрешённые модули (через запятую):").pack(anchor=tk.W)
        self.custom_modules_text = scrolledtext.ScrolledText(custom_frame, height=3, width=50)
        self.custom_modules_text.pack(fill=tk.X, pady=5)
        
        ttk.Label(custom_frame, text="Запрещённые паттерны (regex, через запятую):").pack(anchor=tk.W)
        self.custom_forbidden_text = scrolledtext.ScrolledText(custom_frame, height=3, width=50)
        self.custom_forbidden_text.pack(fill=tk.X, pady=5)
        
        # Кнопки
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="💾 Сохранить профиль", command=self._save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 Загрузить профиль", command=self._load_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🛡️ Безопасный режим", command=self._safe_mode).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⚡ Полный доступ", command=self._full_access).pack(side=tk.LEFT, padx=5)
    
    def _browse_work_dir(self):
        """Выбрать рабочую директорию."""
        directory = filedialog.askdirectory()
        if directory:
            self.work_dir_var.set(directory)
    
    def _save_profile(self):
        """Сохранить профиль песочницы."""
        profile = self.get_config()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", f"Профиль сохранён в {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
    
    def _load_profile(self):
        """Загрузить профиль песочницы."""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON файлы", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                self.set_config(profile)
                messagebox.showinfo("Успех", "Профиль загружён")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}")
    
    def _safe_mode(self):
        """Установить безопасный режим."""
        self.enable_internet_var.set(False)
        self.enable_system_cmds_var.set(False)
        self.enable_git_var.set(False)
        self.enable_venv_var.set(False)
        self.enable_all_modules_var.set(False)
        self.enable_network_var.set(False)
        self.enable_gui_var.set(False)
        self.enable_pip_var.set(True)
        self.enable_math_var.set(True)
        self.enable_science_var.set(True)
        self.enable_testing_var.set(True)
    
    def _full_access(self):
        """Установить полный доступ (с предупреждением)."""
        if messagebox.askyesno("Предупреждение", 
            "⚠️ Вы собираетесь включить ПОЛНЫЙ ДОСТУП!\n\n"
            "Это может быть ОПАСНО - код сможет:\n"
            "- Получать доступ к интернету\n"
            "- Выполнять системные команды\n"
            "- Использовать любые модули\n\n"
            "Продолжить только если вы доверяете коду!"):
            self.enable_internet_var.set(True)
            self.enable_system_cmds_var.set(True)
            self.enable_git_var.set(True)
            self.enable_venv_var.set(True)
            self.enable_all_modules_var.set(True)
            self.enable_network_var.set(True)
            self.enable_gui_var.set(True)
    
    def get_config(self) -> Dict[str, Any]:
        """Получить текущую конфигурацию."""
        return {
            "enable_internet": self.enable_internet_var.get(),
            "enable_system_cmds": self.enable_system_cmds_var.get(),
            "enable_pip": self.enable_pip_var.get(),
            "enable_git": self.enable_git_var.get(),
            "enable_venv": self.enable_venv_var.get(),
            "enable_all_modules": self.enable_all_modules_var.get(),
            "enable_math": self.enable_math_var.get(),
            "enable_science": self.enable_science_var.get(),
            "enable_testing": self.enable_testing_var.get(),
            "enable_gui": self.enable_gui_var.get(),
            "enable_network": self.enable_network_var.get(),
            "work_dir": self.work_dir_var.get(),
            "pip_index_url": self.pip_index_var.get(),
            "max_pip_timeout": self.max_pip_timeout_var.get(),
            "max_git_timeout": self.max_git_timeout_var.get(),
            "custom_allowed_modules": self.custom_modules_text.get("1.0", tk.END).strip(),
            "custom_forbidden_patterns": self.custom_forbidden_text.get("1.0", tk.END).strip()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """Установить конфигурацию."""
        for key, value in config.items():
            var_name = f"{key}_var"
            if hasattr(self, var_name):
                var = getattr(self, var_name)
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                elif isinstance(var, tk.IntVar):
                    var.set(int(value))
                elif isinstance(var, tk.StringVar):
                    var.set(str(value))
        
        if "custom_allowed_modules" in config:
            self.custom_modules_text.delete("1.0", tk.END)
            self.custom_modules_text.insert("1.0", config["custom_allowed_modules"])
        if "custom_forbidden_patterns" in config:
            self.custom_forbidden_text.delete("1.0", tk.END)
            self.custom_forbidden_text.insert("1.0", config["custom_forbidden_patterns"])
        if "work_dir" in config:
            self.work_dir_var.set(config["work_dir"])
        if "pip_index_url" in config:
            self.pip_index_var.set(config["pip_index_url"])


# ─────────────────────────────────────────────────────────────────────────────
# Компонент: Панель инструментов
# ─────────────────────────────────────────────────────────────────────────────
class ToolsPanelFrame(ttk.LabelFrame):
    """Панель управления инструментами."""
    
    TOOLS_INFO = {
        "file_tools": {
            "name": "📁 Файловые инструменты",
            "description": "Чтение, запись, поиск файлов",
            "tools": ["FileReadTool", "FileWriteTool", "FileSearchTool", "DirListTool"]
        },
        "code_tools": {
            "name": "💻 Инструменты кода",
            "description": "Анализ, выполнение, отладка кода",
            "tools": ["CodeAnalyzerTool", "CodeExecutorTool", "DebuggerTool"]
        },
        "web_tools": {
            "name": "🌐 Веб инструменты",
            "description": "HTTP запросы, парсинг сайтов",
            "tools": ["HttpGetTool", "HttpPostTool", "WebScraperTool"]
        },
        "data_tools": {
            "name": "📊 Инструменты данных",
            "description": "Работа с данными, JSON, CSV",
            "tools": ["JsonParserTool", "CsvProcessorTool", "DataValidatorTool"]
        }
    }
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="🧰 Инструменты", **kwargs)
        
        self.tool_vars: Dict[str, tk.BooleanVar] = {}
        
        # Создание чекбоксов для каждой группы инструментов
        row = 0
        for tool_key, tool_info in self.TOOLS_INFO.items():
            frame = ttk.Frame(self)
            frame.pack(fill=tk.X, padx=5, pady=3)
            
            var = tk.BooleanVar(value=True)
            self.tool_vars[tool_key] = var
            
            chk = ttk.Checkbutton(frame, text=tool_info["name"], variable=var)
            chk.pack(side=tk.LEFT)
            
            lbl = ttk.Label(frame, text=tool_info["description"], foreground='gray')
            lbl.pack(side=tk.LEFT, padx=10)
            
            # Список инструментов
            tools_lbl = ttk.Label(frame, text=", ".join(tool_info["tools"]), foreground='blue')
            tools_lbl.pack(side=tk.RIGHT)
            
            row += 1
        
        # Разделитель
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)
        
        # Настройки инструментов
        settings_frame = ttk.LabelFrame(self, text="Настройки инструментов")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Max размер файла (MB):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.max_file_size_var = tk.IntVar(value=10)
        ttk.Spinbox(settings_frame, from_=1, to=100, textvariable=self.max_file_size_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(settings_frame, text="Timeout для веб (сек):").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.web_timeout_var = tk.IntVar(value=30)
        ttk.Spinbox(settings_frame, from_=5, to=300, textvariable=self.web_timeout_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(settings_frame, text="User-Agent:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_agent_var = tk.StringVar(value="LM-Agent/1.0")
        ttk.Entry(settings_frame, textvariable=self.user_agent_var, width=40).grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Кнопки управления
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="✅ Включить все", command=self._enable_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Отключить все", command=self._disable_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 Сохранить конфиг", command=self._save_config).pack(side=tk.RIGHT, padx=5)
    
    def _enable_all(self):
        """Включить все инструменты."""
        for var in self.tool_vars.values():
            var.set(True)
    
    def _disable_all(self):
        """Отключить все инструменты."""
        for var in self.tool_vars.values():
            var.set(False)
    
    def _save_config(self):
        """Сохранить конфигурацию инструментов."""
        config = {
            "enabled_tools": {k: v.get() for k, v in self.tool_vars.items()},
            "max_file_size_mb": self.max_file_size_var.get(),
            "web_timeout": self.web_timeout_var.get(),
            "user_agent": self.user_agent_var.get()
        }
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", f"Конфигурация сохранена в {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Получить текущую конфигурацию."""
        return {
            "enabled_tools": {k: v.get() for k, v in self.tool_vars.items()},
            "max_file_size_mb": self.max_file_size_var.get(),
            "web_timeout": self.web_timeout_var.get(),
            "user_agent": self.user_agent_var.get()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """Установить конфигурацию."""
        if "enabled_tools" in config:
            for key, value in config["enabled_tools"].items():
                if key in self.tool_vars:
                    self.tool_vars[key].set(bool(value))
        if "max_file_size_mb" in config:
            self.max_file_size_var.set(config["max_file_size_mb"])
        if "web_timeout" in config:
            self.web_timeout_var.set(config["web_timeout"])
        if "user_agent" in config:
            self.user_agent_var.set(config["user_agent"])


# ─────────────────────────────────────────────────────────────────────────────
# Компонент: Менеджер задач
# ─────────────────────────────────────────────────────────────────────────────
class TaskManagerFrame(ttk.LabelFrame):
    """Панель управления задачами."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="📋 Менеджер задач", **kwargs)
        
        # Дерево задач
        columns = ("id", "description", "status", "priority", "progress")
        self.task_tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        
        self.task_tree.heading("id", text="ID")
        self.task_tree.heading("description", text="Описание")
        self.task_tree.heading("status", text="Статус")
        self.task_tree.heading("priority", text="Приоритет")
        self.task_tree.heading("progress", text="Прогресс")
        
        self.task_tree.column("id", width=50)
        self.task_tree.column("description", width=300)
        self.task_tree.column("status", width=100)
        self.task_tree.column("priority", width=80)
        self.task_tree.column("progress", width=100)
        
        # Скроллбары
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.task_tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.task_tree.xview)
        self.task_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.task_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Кнопки управления
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, pady=10, sticky=tk.W)
        
        ttk.Button(btn_frame, text="➕ Новая задача", command=self._new_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="▶ Запустить", command=self._run_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⏹ Стоп", command=self._stop_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑 Удалить", command=self._delete_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Обновить", command=self._refresh_tasks).pack(side=tk.LEFT, padx=5)
        
        # Детали задачи
        details_frame = ttk.LabelFrame(self, text="Детали задачи")
        details_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(details_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.detail_id_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.detail_id_var).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(details_frame, text="Описание:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.detail_desc_text = scrolledtext.ScrolledText(details_frame, height=3, width=50, state=tk.DISABLED)
        self.detail_desc_text.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(details_frame, text="Лог выполнения:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.detail_log_text = scrolledtext.ScrolledText(details_frame, height=4, width=50, state=tk.DISABLED)
        self.detail_log_text.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Привязка события выбора
        self.task_tree.bind('<<TreeviewSelect>>', self._on_task_select)
        
        # Пример данных
        self._add_sample_tasks()
    
    def _add_sample_tasks(self):
        """Добавить примерные задачи."""
        samples = [
            ("001", "Анализ кода проекта", "completed", "high", "100%"),
            ("002", "Генерация тестов", "running", "medium", "45%"),
            ("003", "Оптимизация функций", "pending", "low", "0%"),
            ("004", "Документирование API", "queued", "medium", "0%"),
        ]
        for item in samples:
            self.task_tree.insert("", tk.END, values=item)
    
    def _on_task_select(self, event):
        """Обработка выбора задачи."""
        selection = self.task_tree.selection()
        if selection:
            item = self.task_tree.item(selection[0])
            values = item["values"]
            self.detail_id_var.set(values[0])
            
            self.detail_desc_text.config(state=tk.NORMAL)
            self.detail_desc_text.delete("1.0", tk.END)
            self.detail_desc_text.insert("1.0", values[1])
            self.detail_desc_text.config(state=tk.DISABLED)
            
            self.detail_log_text.config(state=tk.NORMAL)
            self.detail_log_text.delete("1.0", tk.END)
            self.detail_log_text.insert("1.0", f"[LOG] Задача {values[0]}: {values[3]} приоритет\n")
            self.detail_log_text.insert("1.0", f"[STATUS] {values[2]}\n")
            self.detail_log_text.insert("1.0", f"[PROGRESS] {values[4]}\n")
            self.detail_log_text.config(state=tk.DISABLED)
    
    def _new_task(self):
        """Создать новую задачу."""
        # Переключаем на вкладку рабочей области для создания задачи
        parent = self.master
        while parent and not hasattr(parent, 'main_notebook'):
            parent = parent.master
        
        if hasattr(parent, 'main_notebook'):
            for index in range(parent.main_notebook.index('end')):
                if parent.main_notebook.tab(index, 'text').strip() == '📝 Рабочая область':
                    parent.main_notebook.select(index)
                    break
        messagebox.showinfo("Новая задача", "Перейдите на вкладку 'Рабочая область' для создания задачи")
    
    def _run_task(self):
        """Запустить выбранную задачу."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для запуска")
            return
        
        item = self.task_tree.item(selection[0])
        task_id = item["values"][0]
        task_desc = item["values"][1]
        
        # Переключаем на вкладку рабочей области и заполняем задачу
        parent = self.master
        while parent and not hasattr(parent, 'main_notebook'):
            parent = parent.master
        
        if hasattr(parent, 'main_notebook'):
            for index in range(parent.main_notebook.index('end')):
                if parent.main_notebook.tab(index, 'text').strip() == '📝 Рабочая область':
                    parent.main_notebook.select(index)
                    if hasattr(parent, 'task_input'):
                        parent.task_input.delete("1.0", tk.END)
                        parent.task_input.insert("1.0", f"Задача #{task_id}: {task_desc}")
                    break
        
        messagebox.showinfo("Запуск", f"Задача #{task_id} подготовлена к выполнению")
    
    def _stop_task(self):
        """Остановить задачу."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для остановки")
            return
        
        item = self.task_tree.item(selection[0])
        task_id = item["values"][0]
        
        # Обновляем статус задачи на "stopped"
        current_values = list(item["values"])
        current_values[2] = "stopped"
        self.task_tree.item(selection[0], values=tuple(current_values))
        
        messagebox.showinfo("Стоп", f"Задача #{task_id} остановлена")
    
    def _delete_task(self):
        """Удалить задачу."""
        selection = self.task_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите задачу для удаления")
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранную задачу?"):
            self.task_tree.delete(selection[0])
    
    def _refresh_tasks(self):
        """Обновить список задач."""
        messagebox.showinfo("Обновление", "Список задач обновлён")


# ─────────────────────────────────────────────────────────────────────────────
# Компонент: Консоль вывода
# ─────────────────────────────────────────────────────────────────────────────
class ConsoleOutputFrame(ttk.LabelFrame):
    """Панель консоли вывода с логами."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="📝 Консоль вывода", **kwargs)
        
        # Текстовое поле с прокруткой
        self.console_text = scrolledtext.ScrolledText(
            self, 
            height=15, 
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.console_text.pack(fill=tk.BOTH, expand=True)
        
        # Настройка тегов для подсветки
        self.console_text.tag_configure('info', foreground='blue')
        self.console_text.tag_configure('success', foreground='green')
        self.console_text.tag_configure('error', foreground='red')
        self.console_text.tag_configure('warning', foreground='orange')
        self.console_text.tag_configure('debug', foreground='gray')
        self.console_text.tag_configure('code', background='#f0f0f0', font=('Consolas', 10))
        
        # Панель инструментов консоли
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=5)
        
        ttk.Button(toolbar, text="🧹 Очистить", command=self.clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 Сохранить лог", command=self.save_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 Копировать", command=self.copy_text).pack(side=tk.LEFT, padx=2)
        
        # Фильтры уровня логов
        ttk.Label(toolbar, text="Фильтр:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.filter_vars = {
            'info': tk.BooleanVar(value=True),
            'success': tk.BooleanVar(value=True),
            'error': tk.BooleanVar(value=True),
            'warning': tk.BooleanVar(value=True),
            'debug': tk.BooleanVar(value=False)
        }
        
        for level, var in self.filter_vars.items():
            ttk.Checkbutton(toolbar, text=level.upper(), variable=var, 
                          command=self._apply_filter).pack(side=tk.LEFT, padx=2)
        
        # Автоскролл
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Автоскролл", variable=self.auto_scroll_var).pack(side=tk.RIGHT, padx=5)
        
        # Буфер строк
        self.log_buffer: List[tuple] = []
        self.max_buffer_size = 1000
    
    def write(self, message: str, level: str = 'info'):
        """
        Записать сообщение в консоль.
        
        Args:
            message: Сообщение для записи
            level: Уровень лога (info, success, error, warning, debug, code)
        """
        if not self.filter_vars.get(level, tk.BooleanVar(value=True)).get():
            return
        
        self.console_text.config(state=tk.NORMAL)
        
        timestamp = tk.datetime.now().strftime("%H:%M:%S") if hasattr(tk, 'datetime') else ""
        prefix = f"[{timestamp}] [{level.upper()}] " if timestamp else f"[{level.upper()}] "
        
        self.console_text.insert(tk.END, prefix, level)
        self.console_text.insert(tk.END, message + "\n")
        
        # Сохранение в буфер
        self.log_buffer.append((level, message))
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer.pop(0)
        
        self.console_text.config(state=tk.DISABLED)
        
        if self.auto_scroll_var.get():
            self.console_text.see(tk.END)
    
    def clear(self):
        """Очистить консоль."""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        self.log_buffer.clear()
        self.console_text.config(state=tk.DISABLED)
    
    def save_log(self):
        """Сохранить лог в файл."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log файлы", "*.log"), ("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for level, message in self.log_buffer:
                        f.write(f"[{level.upper()}] {message}\n")
                messagebox.showinfo("Успех", f"Лог сохранён в {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")
    
    def copy_text(self):
        """Копировать выделенный текст."""
        try:
            text = self.console_text.selection_get()
            self.console_text.clipboard_clear()
            self.console_text.clipboard_append(text)
        except tk.TclError:
            pass
    
    def _apply_filter(self):
        """Применить фильтр логов (перезагрузка из буфера)."""
        # Получаем текст фильтра
        filter_text = self.filter_var.get().lower()
        
        if not filter_text:
            # Если фильтр пустой, показываем все логи
            self.console_text.config(state=tk.NORMAL)
            self.console_text.delete("1.0", tk.END)
            for log_entry in self.log_buffer:
                self._display_log_entry(log_entry)
            self.console_text.config(state=tk.DISABLED)
            return
        
        # Фильтруем логи по тексту
        filtered_logs = [
            log for log in self.log_buffer 
            if filter_text in log['message'].lower() 
            or filter_text in log['level'].lower()
            or filter_text in log.get('source', '').lower()
        ]
        
        # Обновляем отображение
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        for log_entry in filtered_logs:
            self._display_log_entry(log_entry)
        self.console_text.config(state=tk.DISABLED)
        
        # Обновляем статус
        self.status_label.config(
            text=f"Найдено {len(filtered_logs)} из {len(self.log_buffer)} записей"
        )


# Экспорт всех компонентов
__all__ = [
    'ModelSettingsFrame',
    'SandboxConfigFrame', 
    'ToolsPanelFrame',
    'TaskManagerFrame',
    'ConsoleOutputFrame'
]
