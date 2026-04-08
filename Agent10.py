#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LM Studio + LangChain Code Agent GUI v12.0.0
✅ ИСПРАВЛЕНО: Все синтаксические ошибки (__init__, __future__, f-строки, __name__)
✅ ИСПРАВЛЕНО: Пробелы в ключах словарей и именах переменных
✅ ИСПРАВЛЕНО: stdout захватывается через redirect_stdout (print() теперь работает)
✅ ИСПРАВЛЕНО: callbacks через RunnableConfig (LangChain 1.2.15 совместимость)
✅ ИСПРАВЛЕНО: _run() принимает **kwargs вместо tool_input
✅ ИСПРАВЛЕНО: Прогресс отображается между итерациями (буфер + частые вызовы progress_cb)
✅ ИСПРАВЛЕНО: base_url вместо openai_api_base для ChatOpenAI
✅ ДОБАВЛЕНО: Инструмент ask_user для общения с пользователем
✅ ДОБАВЛЕНО: Детальное логирование выполнения между итерациями
"""
from __future__ import annotations
import sys
import os
import io
import threading
import queue
import time
import uuid
import json
import logging
import re
import ast
import builtins
import requests
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from pathlib import Path
from contextlib import redirect_stdout
from typing import Any, Optional, TypedDict, List, Dict, Callable, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

# ─────────────────────────────────────────────────────────────────────────────
# 0. ЛОГИРОВАНИЕ И ТИПЫ
# ─────────────────────────────────────────────────────────────────────────────
LOG_DIR = Path.home() / ".lm_agent"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"agent_{datetime.now():%Y%m%d}.log"

class ProgressEntry(TypedDict):
    timestamp: str
    level: str
    message: str
    details: Optional[str]
    iteration: Optional[int]
    tool_call: Optional[dict]
    ask_user: Optional[dict]

class ColoredFormatter(logging.Formatter):
    COLORS = {'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m', 'ERROR': '\033[31m', 'CRITICAL': '\033[35m', 'RESET': '\033[0m'}
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s', datefmt='%H:%M:%S'))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ColoredFormatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler], force=True)
logger = logging.getLogger(__name__)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt): return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
threading.excepthook = lambda args: handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

# ─────────────────────────────────────────────────────────────────────────────
# 1. УПРАВЛЕНИЕ ЗАДАЧЕЙ + ОЧЕРЕДЬ ВОПРОСОВ + БУФЕР ПРОГРЕССА
# ─────────────────────────────────────────────────────────────────────────────
class TaskControl:
    """Управление состоянием выполнения задачи + очередь вопросов + буфер прогресса."""
    def __init__(self):
        self.cancelled = threading.Event()
        self.paused = threading.Event()
        self.ask_queue: queue.Queue[dict] = queue.Queue()
        self.answer_queue: queue.Queue[str] = queue.Queue()
        self.progress_buffer: queue.Queue[ProgressEntry] = queue.Queue()  # ✅ Буфер для надёжной доставки
    
    def cancel(self) -> None: self.cancelled.set()
    def pause(self) -> None: self.paused.set()
    def resume(self) -> None: self.paused.clear()
    def is_cancelled(self) -> bool: return self.cancelled.is_set()
    def wait_if_paused(self) -> None:
        while self.paused.is_set() and not self.cancelled.is_set(): time.sleep(0.1)
    
    def ask_user(self, question: str, options: List[str] = None, timeout: float = 300.0) -> Optional[str]:
        msg = {'question': question, 'options': options, 'timestamp': datetime.now().isoformat(), 'answered': False}
        self.ask_queue.put(msg)
        logger.info(f"❓ Вопрос пользователю: {question}")
        try:
            answer = self.answer_queue.get(timeout=timeout)
            msg['answered'] = True
            msg['answer'] = answer
            return answer
        except queue.Empty:
            return None
    
    def buffer_progress(self, entry: ProgressEntry):
        """Добавляет запись прогресса в буфер для надёжной доставки."""
        try:
            self.progress_buffer.put(entry, block=False)
        except queue.Full:
            pass  # Пропускаем если буфер полон

# ─────────────────────────────────────────────────────────────────────────────
# 2. CALLBACK ДЛЯ LANGCHAIN
# ─────────────────────────────────────────────────────────────────────────────
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class LangChainProgressHandler(BaseCallbackHandler):
    def __init__(self, progress_cb: Optional[Callable[[str,str,str,int,dict],None]]):
        self.progress_cb = progress_cb
        self.start_time = 0.0
        self._tc = 0

    def on_llm_start(self, serialized: dict, prompts: List[str], **kwargs) -> None:
        self.start_time = time.time()
        if self.progress_cb: self.progress_cb("info", "🤖 LLM: Начинаю генерацию...", f"Промптов: {len(prompts)}", None, None)
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self._tc += 1
        if self._tc % 50 == 0 and self.progress_cb: self.progress_cb("info", "⏳ LLM: Генерация...", f"Токенов: ~{self._tc}", None, None)
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        if self.progress_cb:
            usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            self.progress_cb("success", "✅ LLM: Ответ готов", f"⏱️ {time.time()-self.start_time:.1f}с | Токены: {usage.get('total_tokens','N/A')}", None, None)
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        if self.progress_cb: self.progress_cb("error", "❌ LLM: Ошибка", str(error)[:100], None, None)
    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:
        if self.progress_cb: self.progress_cb("debug", f"⛓️ Chain: {serialized.get('name','Chain')}", None, None, None)
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        if self.progress_cb: self.progress_cb("info", f"🔧 LangChain Tool: {serialized.get('name','tool')}", input_str[:80], None, None)

# ─────────────────────────────────────────────────────────────────────────────
# 3. ОКНО ПРОГРЕССА + ОБРАБОТКА ВОПРОСОВ + БУФЕР
# ─────────────────────────────────────────────────────────────────────────────
class ProgressWindow(tk.Toplevel):
    _LEVEL_COLORS = {'debug': '#888888', 'info': '#2196F3', 'success': '#4CAF50', 'warning': '#FF9800', 'error': '#F44336', 'ask': '#9C27B0'}
    _LEVEL_ICONS = {'debug': '🔍', 'info': 'ℹ️', 'success': '✅', 'warning': '⚠️', 'error': '❌', 'ask': '❓'}
    
    def __init__(self, parent, task_id: str, task_desc: str, control: TaskControl, answer_cb: Callable[[str], None]):
        super().__init__(parent)
        self.task_id = task_id
        self.task_desc = task_desc[:50] + ("..." if len(task_desc) > 50 else "")
        self.control = control
        self.answer_cb = answer_cb
        self._entries: List[ProgressEntry] = []
        self._start_time = time.time()
        self._ask_active = False
        
        self.title(f"🔄 Прогресс: {self.task_id}")
        self.geometry("900x700")
        self.minsize(600, 400)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._dark_mode = tk.BooleanVar(value=False)
        self._build_ui()
        self._apply_theme()
        self._update_queue: queue.Queue[ProgressEntry] = queue.Queue()
        self._poll_progress()
        self._poll_ask()

    def _build_ui(self):
        header = ttk.Frame(self, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"🔄 Задача: {self.task_id}", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(header, text=self.task_desc, foreground="gray").pack(anchor=tk.W)
        
        self._progress = ttk.Progressbar(self, mode='indeterminate')
        self._progress.pack(fill=tk.X, padx=10, pady=5)
        self._progress.start(10)
        
        stats = ttk.Frame(self, padding=(10, 0))
        stats.pack(fill=tk.X)
        self._stat_label = ttk.Label(stats, text="⏳ Итерация: 0/50 | ⏱️ 00:00")
        self._stat_label.pack(anchor=tk.W)
        
        # Блок для вопросов пользователю
        self._ask_frame = ttk.Frame(self, padding=10, relief=tk.RIDGE, borderwidth=2)
        self._ask_frame.pack(fill=tk.X, padx=10, pady=5)
        self._ask_frame.pack_forget()
        self._ask_question = ttk.Label(self._ask_frame, text="", wraplength=800, font=("Arial", 10, "bold"))
        self._ask_question.pack(anchor=tk.W, pady=(0,5))
        self._ask_options_frame = ttk.Frame(self._ask_frame)
        self._ask_options_frame.pack(anchor=tk.W, fill=tk.X)
        self._ask_answer = tk.Entry(self._ask_frame, width=70)
        self._ask_answer.pack(fill=tk.X, pady=5)
        self._ask_answer.bind("<Return>", lambda e: self._send_answer())
        btn_f = ttk.Frame(self._ask_frame)
        btn_f.pack(fill=tk.X)
        ttk.Button(btn_f, text="✅ Ответить", command=self._send_answer).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="⏭️ Пропустить", command=lambda: self._send_answer("")).pack(side=tk.LEFT, padx=2)
        
        log_f = ttk.Frame(self, padding=10)
        log_f.pack(fill=tk.BOTH, expand=True)
        self._log = tk.Text(log_f, height=18, font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        self._log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_f, command=self._log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.configure(yscrollcommand=scrollbar.set)
        for lv, col in self._LEVEL_COLORS.items(): self._log.tag_config(lv, foreground=col)
        self._log.tag_config("timestamp", foreground="#666666")
        self._log.tag_config("tool", foreground="#9C27B0")
        
        btn_f = ttk.Frame(self, padding=10)
        btn_f.pack(fill=tk.X)
        self._pause_btn = ttk.Button(btn_f, text="⏸️ Пауза", command=self._toggle_pause)
        self._pause_btn.pack(side=tk.LEFT, padx=2)
        self._cancel_btn = ttk.Button(btn_f, text="🛑 Отмена", command=self._cancel)
        self._cancel_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="📋 Копировать", command=self._copy_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="📤 Экспорт", command=self._export_log).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(btn_f, text="🌙 Тёмная тема", variable=self._dark_mode, command=self._apply_theme).pack(side=tk.RIGHT)

    def _apply_theme(self):
        bg, fg = ("#1e1e1e", "#d4d4d4") if self._dark_mode.get() else ("#f0f2f5", "#000000")
        self.configure(bg=bg)
        log_bg = "#2d2d2d" if self._dark_mode.get() else "#ffffff"
        ts_fg = "#888888" if self._dark_mode.get() else "#666666"
        self._log.configure(bg=log_bg, fg=fg, insertbackground=fg)
        self._log.tag_config("timestamp", foreground=ts_fg)

    def _toggle_pause(self):
        if self.control.paused.is_set():
            self.control.resume()
            self._pause_btn.config(text="⏸️ Пауза")
            self.add("info", "▶️ Выполнение возобновлено")
        else:
            self.control.pause()
            self._pause_btn.config(text="▶️ Продолжить")
            self.add("warning", "⏸️ Выполнение приостановлено")

    def _cancel(self):
        if messagebox.askyesno("Подтверждение", "Отменить выполнение задачи?"):
            self.control.cancel()
            self.add("error", "🛑 Отменено пользователем")
            self._progress.stop()
            self.after(1500, self.destroy)
        
    def _on_close(self):
        if not self.control.cancelled.is_set(): self.add("warning", "⚠️ Окно закрыто, задача в фоне")
        self.destroy()

    def _copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self._log.get("1.0", tk.END))
        self.add("info", "📋 Лог скопирован")
    
    def _export_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".log", initialfile=f"progress_{self.task_id}.log")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    for e in self._entries: f.write(f"[{e['timestamp']}] [{e['level'].upper()}] {e['message']}\n")
                self.add("success", f"📤 Экспортировано: {path}")
            except Exception as ex: self.add("error", f"❌ Ошибка: {ex}")
        
    def _render_entry(self, entry: ProgressEntry):
        self._log.config(state=tk.NORMAL)
        ts = entry['timestamp'].split(' ')[1] if ' ' in entry['timestamp'] else entry['timestamp']
        icon = self._LEVEL_ICONS.get(entry['level'], '•')
        self._log.insert(tk.END, f"[{ts}] {icon} {entry['message']}\n", entry['level'])
        if entry.get('details'): self._log.insert(tk.END, f"   └─ {entry['details']}\n", "debug")
        if entry.get('tool_call'):
            tc = entry['tool_call']
            args_str = str(tc.get('args',''))[:80]
            self._log.insert(tk.END, f"   🔧 {tc.get('name')}({args_str}) ", "tool")
            if tc.get('result'): self._log.insert(tk.END, f" → {tc['result'][:80]}\n", "success")
            else: self._log.insert(tk.END, "\n")
        self._log.config(state=tk.DISABLED)
        self._log.see(tk.END)

    def _show_ask(self, question: str, options: List[str] = None):
        self._ask_active = True
        self._ask_question.config(text=f"❓ {question}")
        for w in self._ask_options_frame.winfo_children(): w.destroy()
        if options:
            for opt in options:
                ttk.Button(self._ask_options_frame, text=opt, command=lambda o=opt: self._send_answer(o)).pack(side=tk.LEFT, padx=2)
        else:
            self._ask_answer.delete(0, tk.END)
            self._ask_answer.focus()
        self._ask_frame.pack(fill=tk.X, padx=10, pady=5)
        self._log.insert(tk.END, f"\n[❓] {question}\n", "ask")
        self._log.see(tk.END)
        self.lift()

    def _hide_ask(self):
        self._ask_active = False
        self._ask_frame.pack_forget()
        for w in self._ask_options_frame.winfo_children(): w.destroy()

    def _send_answer(self, answer: str = None):
        if answer is None:
            answer = self._ask_answer.get().strip()
        self.answer_cb(answer)
        self._hide_ask()
        self.add("info", f"💬 Ответ отправлен: {answer or '(пропущено)'}")
        self.control.resume()

    def add(self, level: str, message: str, details: str = None, iteration: int = None, tool_call: dict = None, ask_user: dict = None):
        entry: ProgressEntry = {'timestamp': datetime.now().strftime("%H:%M:%S"), 'level': level, 'message': message, 'details': details, 'iteration': iteration, 'tool_call': tool_call, 'ask_user': ask_user}
        self._entries.append(entry)
        self._update_queue.put(entry)
        
        # ✅ Копируем в буфер контроллера для надёжности
        if hasattr(self.control, 'progress_buffer'):
            try:
                self.control.progress_buffer.put(entry, block=False)
            except queue.Full:
                pass
        
        if iteration is not None:
            elapsed = time.time() - self._start_time
            self._stat_label.config(text=f"⏳ Итерация: {iteration}/50 | ⏱️ {int(elapsed)//60:02d}:{int(elapsed)%60:02d}")
        if ask_user and not self._ask_active:
            self._show_ask(ask_user.get('question', ''), ask_user.get('options'))
        
    def _poll_progress(self):
        # ✅ Обрабатываем локальную очередь
        try:
            while not self._update_queue.empty():
                self._render_entry(self._update_queue.get_nowait())
        except (queue.Empty, tk.TclError):
            pass
        
        # ✅ Обрабатываем буфер из контроллера (резервный канал)
        if hasattr(self.control, 'progress_buffer'):
            try:
                while not self.control.progress_buffer.empty():
                    entry = self.control.progress_buffer.get_nowait()
                    if entry not in self._entries:
                        self._entries.append(entry)
                        self._render_entry(entry)
            except (queue.Empty, tk.TclError):
                pass
        
        # ✅ Безопасная проверка существования окна
        if self.winfo_exists():
            self.after(100, self._poll_progress)

    def _poll_ask(self):
        try:
            while not self.control.ask_queue.empty():
                ask_msg = self.control.ask_queue.get_nowait()
                self.add("ask", "❓ Вопрос от агента", None, None, None, ask_msg)
        except queue.Empty: pass
        if self.winfo_exists() and not self._ask_active: self.after(500, self._poll_ask)

# ─────────────────────────────────────────────────────────────────────────────
# 4. УТИЛИТЫ И КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────────────────────────────────────
def get_safe_builtins(allowed: set[str]) -> dict[str, Any]:
    source = builtins if isinstance(builtins, dict) else vars(builtins)
    return {k: v for k, v in source.items() if k in allowed}

def validate_url(url: str) -> str:
    url = url.strip().rstrip('/')
    if url.endswith('/v1'): return url
    if not url.startswith(('http://', 'https://')): url = f'http://{url}'
    return url if url.endswith('/v1') else f'{url}/v1'

def safe_path(path: str, base: Path) -> Optional[Path]:
    try:
        resolved = (base / path).resolve()
        if resolved.is_relative_to(base.resolve()): return resolved
    except (OSError, ValueError, RuntimeError): pass
    return None

def parse_json_list(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip(): return []
    try: return json.loads(text) if text.strip().startswith('[') else [x.strip() for x in text.split(',') if x.strip()]
    except Exception: return [x.strip() for x in text.split(',') if x.strip()]

# ─────────────────────────────────────────────────────────────────────────────
# 5. КОНФИГУРАЦИЯ ПЕСОЧНИЦЫ
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SandboxAdvancedConfig:
    enable_internet: bool = False
    enable_system_cmds: bool = False
    enable_pip: bool = True
    enable_git: bool = False
    enable_venv: bool = False
    enable_all_modules: bool = False
    enable_math: bool = True
    enable_bool: bool = True  # ✅ Исправлено
    enable_network: bool = False
    enable_gui: bool = False
    enable_science: bool = True
    enable_testing: bool = True
    custom_allowed_modules: str = ""
    custom_forbidden_patterns: str = ""
    pip_index_url: str = "https://pypi.org/simple"
    venv_dir: str = ""
    max_pip_timeout: int = 120
    max_git_timeout: int = 300
    allow_local_files: bool = True
    
    def to_dict(self) -> dict: return {k: v for k, v in self.__dict__.items()}
    @classmethod
    def from_dict(cls, d: dict) -> "SandboxAdvancedConfig":
        return cls(**{k: d.get(k, getattr(cls, k, None)) for k in cls.__dataclass_fields__.keys()})

# ─────────────────────────────────────────────────────────────────────────────
# 6. ГРУППЫ МОДУЛЕЙ (ВСЕ ОПЕЧАТКИ ИСПРАВЛЕНЫ)
# ─────────────────────────────────────────────────────────────────────────────
MODULE_GROUPS = {
    'core': {'builtins', '__future__', 'typing', 'typing_extensions', 'abc', 'collections', 'itertools', 'functools', 'operator', 'copy', 'weakref', 'types', 'contextlib', 'contextvars', 'dataclasses', 'enum'},
    'math': {'math', 'cmath', 'decimal', 'fractions', 'random', 'statistics', 'numbers'},
    'datetime': {'datetime', 'time', 'calendar', 'zoneinfo'},
    'text': {'re', 'string', 'textwrap', 'unicodedata', 'difflib', 'struct', 'codecs'},
    'data': {'json', 'csv', 'pickle', 'shelve', 'pprint'},
    'files': {'os', 'sys', 'io', 'pathlib', 'tempfile', 'shutil', 'glob', 'fnmatch', 'linecache', 'stat'},
    'debug': {'traceback', 'warnings', 'logging', 'inspect', 'dis', 'ast', 'tokenize', 'token', 'keyword', 'pdb'},
    'concurrency': {'threading', 'queue', 'concurrent', 'concurrent.futures', 'asyncio', 'selectors'},
    'utils': {'uuid', 'hashlib', 'hmac', 'secrets', 'base64', 'binascii', 'quopri', 'uu', 'argparse', 'configparser'},
    'network': {'socket', 'urllib', 'urllib.parse', 'urllib.request', 'http', 'http.client', 'ssl', 'email', 'requests', 'aiohttp'},
    'gui': {'tkinter', 'tkinter.ttk', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PySide6', 'pygame', 'kivy'},
    'science': {'numpy', 'pandas', 'matplotlib', 'matplotlib.pyplot', 'scipy', 'plotly', 'seaborn', 'sympy', 'sklearn'},
    'testing': {'unittest', 'doctest', 'pytest', 'mock'},
}

ALWAYS_FORBIDDEN = {r'__import__', r'importlib', r'exec\s*\(', r'eval\s*\(', r'compile\s*\(', r'__class__', r'__mro__', r'__getattribute__', r'__setattr__', r'__builtins__', r'__globals__', r'__code__', r'__subclasses__', r'__base__'}
SYSTEM_MODULES = {r'os.system', r'subprocess', r'popen', r'spawn', r'pty', r'ctypes'}
FORBIDDEN_ATTRS = {'__class__', '__mro__', '__subclasses__', '__globals__', '__builtins__', '__import__', 'eval', 'exec', 'compile', '__code__', '__closure__'}

# ─────────────────────────────────────────────────────────────────────────────
# 7. ИНСТРУМЕНТЫ
# ─────────────────────────────────────────────────────────────────────────────
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict

class PythonCodeInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)
    code: str = Field(..., min_length=1, max_length=50000, description="Python-код для выполнения")

class PipInstallInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    packages: str = Field(..., description="Пакеты для установки")

class GitOperationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command: str = Field(..., description="Git-команда")

class VenvSetupInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str = Field(..., description="Действие: create, activate, list")
    path: str = Field(default="", description="Путь к venv")

class AskUserInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(..., description="Вопрос пользователю")
    options: str = Field(default="", description="Варианты ответа через запятую (необязательно)")

class SafePythonREPL(BaseTool):
    name: str = "python_repl_safe"
    description: str = "Выполняет Python-код с настраиваемыми правилами безопасности"
    args_schema: type[BaseModel] = PythonCodeInput
    timeout: int = Field(default=1800, ge=1)
    work_dir: str = Field(default_factory=lambda: str(Path.home() / "lm_agent_sandbox"))
    sandbox_config: SandboxAdvancedConfig = Field(default_factory=SandboxAdvancedConfig)
    _base_path: Path = PrivateAttr(default=None)
    _allowed: frozenset = PrivateAttr(default=None)
    _forbidden: re.Pattern = PrivateAttr(default=None)
    _safe_builtins: dict = PrivateAttr(default=None)
    _cached_imports: dict = PrivateAttr(default_factory=dict)
    handle_tool_error: bool = True
    
    def __init__(self, timeout: int = 1800, work_dir: str | None = None, sandbox_config: SandboxAdvancedConfig | None = None, **kwargs):
        wd = work_dir or str(Path.home() / "lm_agent_sandbox")
        cfg = sandbox_config or SandboxAdvancedConfig()
        Path(wd).mkdir(parents=True, exist_ok=True)
        super().__init__(timeout=timeout, work_dir=wd, sandbox_config=cfg, **kwargs)
        self._base_path = Path(wd).resolve()
        self._apply_sandbox_rules(cfg)

    def _apply_sandbox_rules(self, cfg: SandboxAdvancedConfig):
        if cfg.enable_all_modules:
            self._allowed = frozenset(['math','random','datetime','collections','itertools','functools','re','json','time','typing','pathlib','string','copy','os','sys','io','textwrap','csv','pickle','dataclasses','enum','threading','queue','concurrent','asyncio','uuid','hashlib','base64','argparse','logging','warnings','traceback','inspect','ast','unittest','numpy','pandas','matplotlib','scipy','plotly','flask','django','requests','tkinter','PyQt5','pygame','torch','tensorflow','sklearn'])
            self._forbidden = re.compile('|'.join([r'__import__',r'importlib',r'exec\s*\(',r'eval\s*\(',r'__class__',r'__subclasses__',r'__builtins__']), re.I)
        else:
            allowed = set(MODULE_GROUPS['core'])
            if cfg.enable_math: allowed.update(MODULE_GROUPS['math'])
            allowed.update(MODULE_GROUPS['datetime']); allowed.update(MODULE_GROUPS['text'])
            if cfg.enable_bool: allowed.update(MODULE_GROUPS['data'])
            allowed.update(MODULE_GROUPS['files']); allowed.update(MODULE_GROUPS['debug']); allowed.update(MODULE_GROUPS['utils'])
            if cfg.enable_internet or cfg.enable_network: allowed.update(MODULE_GROUPS['network'])
            if cfg.enable_system_cmds or cfg.enable_gui: allowed.update(MODULE_GROUPS['gui'])
            if cfg.enable_science: allowed.update(MODULE_GROUPS['science'])
            if cfg.enable_testing: allowed.update(MODULE_GROUPS['testing'])
            allowed.update(MODULE_GROUPS['concurrency'])
            allowed.update(parse_json_list(cfg.custom_allowed_modules))
            self._allowed = frozenset(allowed)
            forbidden = list(ALWAYS_FORBIDDEN)
            if not cfg.enable_system_cmds: forbidden.extend(SYSTEM_MODULES)
            forbidden.extend(parse_json_list(cfg.custom_forbidden_patterns))
            self._forbidden = re.compile('|'.join(forbidden), re.I)
        self._safe_builtins = get_safe_builtins({'print','len','range','list','dict','str','int','float','bool','sum','min','max','abs','round','enumerate','zip','sorted','reversed','any','all','True','False','None','Exception','ValueError','TypeError','KeyError','IndexError','FileNotFoundError','ImportError','open','repr','format','ord','chr','isinstance','issubclass','type','hasattr','getattr','setattr','delattr','id','hash','dir','vars','locals','globals','callable'})

    def _is_safe(self, code: str) -> tuple[bool, str]:
        if self._forbidden.search(code): return False, "Запрещённая операция"
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = (node.names[0].name if isinstance(node, ast.Import) else node.module or "").split('.')[0]
                    if mod and mod not in self._allowed: return False, f"Модуль '{mod}' не разрешён"
                elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                    return False, f"Доступ к '{node.attr}' запрещён"
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'open':
                    if not self.sandbox_config.allow_local_files: return False, "Доступ к файлам отключён"
                    if node.args and isinstance(node.args[0], ast.Constant):
                        p = Path(node.args[0].value)
                        if p.is_absolute() and not str(p.resolve()).startswith(str(self._base_path)): return False, "Путь вне work_dir"
        except SyntaxError as e: return False, f"Синтаксис: {e}"
        return True, "OK"

    def _create_safe_globals(self) -> dict[str, Any]:
        def safe_open(path: str, mode: str = 'r', **kw):
            if not self.sandbox_config.allow_local_files: raise PermissionError("Доступ к файлам отключён")
            resolved = safe_path(path, self._base_path)
            if not resolved: raise PermissionError(f"Доступ запрещён: {path}")
            return open(resolved, mode, **kw)
        def safe_pathlib_path(p: str):
            path_obj = Path(p)
            return self._base_path / path_obj if not path_obj.is_absolute() else (path_obj if safe_path(str(path_obj), self._base_path) else None)
        
        safe_imports = {}
        for mod in self._allowed:
            if mod in self._cached_imports:
                safe_imports[mod] = self._cached_imports[mod]
            elif mod not in {'socket','urllib','requests','subprocess','os','sys','http','aiohttp','tkinter','PyQt5','pygame'}:
                try:
                    self._cached_imports[mod] = __import__(mod)
                    safe_imports[mod] = self._cached_imports[mod]
                except ImportError: pass
        # ✅ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: добавляем 'os' если разрешены файлы
        if self.sandbox_config.allow_local_files and 'os' not in safe_imports and 'os' in self._allowed:
            try: safe_imports['os'] = __import__('os')
            except ImportError: pass
        return {'__builtins__': {**self._safe_builtins, 'open': safe_open}, 'Path': safe_pathlib_path, **safe_imports}

    def _exec_code(self, code: str) -> str:
        # ✅ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: захват stdout через redirect_stdout
        globals_, locals_ = self._create_safe_globals(), {}
        output_buffer = io.StringIO()
        try:
            with redirect_stdout(output_buffer):
                exec(code, globals_, locals_)
            output = output_buffer.getvalue().strip()
            return output or str(locals_.get('result', locals_.get('output', '✓ Выполнено')))
        except Exception as e:
            return f"❌ {type(e).__name__}: {e}"

    def _run(self, **kwargs) -> str:  # ✅ Исправлено: **kwargs вместо tool_input
        code = kwargs.get('code')
        if code is None:
            tool_input = kwargs.get('tool_input')
            code = tool_input if isinstance(tool_input, str) else (tool_input.get('code', str(tool_input)) if isinstance(tool_input, dict) else str(tool_input))
        code = str(code).strip()
        if not code: return "⚠️ Пустой код"
        ok, msg = self._is_safe(code)
        if not ok: return f"⚠️ Заблокировано: {msg}"
        res, err = [None], [None]
        def runner():
            try: res[0] = self._exec_code(code)
            except Exception as e: err[0] = f"{type(e).__name__}: {e}"
        t = threading.Thread(target=runner, daemon=True)
        t.start(); t.join(timeout=self.timeout)
        if t.is_alive(): return "⏱️ Таймаут"
        if err[0]: return f"❌ {err[0]}"
        return res[0] if res[0] is not None else "✓ Выполнено"
    
    async def _arun(self, tool_input: Union[str, dict]) -> str: return self._run(**(tool_input if isinstance(tool_input, dict) else {'code': tool_input}))

class PipInstallTool(BaseTool):
    name: str = "pip_installer"; args_schema: type[BaseModel] = PipInstallInput
    sandbox_config: SandboxAdvancedConfig = Field(default_factory=SandboxAdvancedConfig)
    description: str = "Устанавливает пакеты через pip"; handle_tool_error: bool = True
    def _run(self, **kwargs) -> str:
        if not self.sandbox_config.enable_pip: return "⚠️ pip отключён"
        pkgs = kwargs.get('packages') or kwargs.get('tool_input', '')
        if not pkgs: return "⚠️ Укажите пакеты"
        pkgs = str(pkgs).strip()
        cmd = [sys.executable, "-m", "pip", "install", "--quiet", *pkgs.split()]
        try: subprocess.run(cmd, capture_output=True, text=True, timeout=self.sandbox_config.max_pip_timeout, check=True); return f"✅ Установлено: {pkgs}"
        except subprocess.TimeoutExpired: return "⏱️ Таймаут pip"
        except subprocess.CalledProcessError as e: return f"❌ pip: {e.stderr}"
        except FileNotFoundError: return "❌ pip не найден"
    async def _arun(self, tool_input: Union[str, dict]) -> str: return self._run(**(tool_input if isinstance(tool_input, dict) else {'packages': tool_input}))

class GitOperationTool(BaseTool):
    name: str = "git_runner"; args_schema: type[BaseModel] = GitOperationInput
    sandbox_config: SandboxAdvancedConfig = Field(default_factory=SandboxAdvancedConfig)
    description: str = "Выполняет git-команды"; handle_tool_error: bool = True
    def _run(self, **kwargs) -> str:
        if not self.sandbox_config.enable_git: return "⚠️ Git отключён"
        cmd_str = kwargs.get('command') or kwargs.get('tool_input', '')
        if not cmd_str: return "⚠️ Укажите команду"
        cmd_str = str(cmd_str).strip()
        if any(d in cmd_str.lower() for d in ['rm -rf','push -f','reset --hard']): return "⚠️ Команда заблокирована"
        try: res = subprocess.run(['git', *cmd_str.split()], capture_output=True, text=True, timeout=self.sandbox_config.max_git_timeout, cwd=str(Path.home()/'lm_agent_sandbox'), check=True); return f"✅ Git: {res.stdout or 'OK'}"
        except Exception as e: return f"❌ Git: {e}"
    async def _arun(self, tool_input: Union[str, dict]) -> str: return self._run(**(tool_input if isinstance(tool_input, dict) else {'command': tool_input}))

class VenvManagerTool(BaseTool):
    name: str = "venv_manager"; args_schema: type[BaseModel] = VenvSetupInput
    sandbox_config: SandboxAdvancedConfig = Field(default_factory=SandboxAdvancedConfig)
    description: str = "Управляет виртуальными окружениями"; handle_tool_error: bool = True
    def _run(self, **kwargs) -> str:
        if not self.sandbox_config.enable_venv: return "⚠️ Venv отключён"
        action = kwargs.get('action', 'list'); venv_name = kwargs.get('path', 'venv')
        venv_path = Path(self.sandbox_config.venv_dir or Path.home()/"lm_agent_sandbox") / venv_name
        if action == "create":
            if venv_path.exists(): return "⚠️ Уже существует"
            try: subprocess.run([sys.executable, "-m", "venv", str(venv_path)], capture_output=True, check=True); return f"✅ Venv создан: {venv_path}"
            except Exception as e: return f"❌ Ошибка: {e}"
        elif action == "list":
            venvs = [d.name for d in Path(venv_path.parent).iterdir() if d.is_dir() and (d/'pyvenv.cfg').exists()]
            return f"📋 Venv: {venvs or 'Нет'}"
        return "⚠️ Поддерживаются: create, list"
    async def _arun(self, tool_input: Union[str, dict]) -> str: return self._run(**(tool_input if isinstance(tool_input, dict) else {'action': tool_input}))

class AskUserTool(BaseTool):
    name: str = "ask_user"
    description: str = "Задаёт вопрос пользователю и получает ответ. Используйте, если задача неясна или нужен выбор."
    args_schema: type[BaseModel] = AskUserInput
    control: Optional[TaskControl] = Field(default=None, exclude=True)
    
    def _run(self, **kwargs) -> str:
        question = kwargs.get('question') or kwargs.get('tool_input', '')
        options_str = kwargs.get('options', '')
        if not question: return "⚠️ Укажите вопрос"
        options = [o.strip() for o in options_str.split(',') if o.strip()] if options_str else None
        if self.control:
            answer = self.control.ask_user(question, options, timeout=300.0)
            if answer is None: return "⏱️ Таймаут ожидания ответа"
            return f"💬 Ответ пользователя: {answer}"
        else:
            return "⚠️ Контроллер задачи не установлен"
    
    async def _arun(self, tool_input: Union[str, dict]) -> str:
        return self._run(**(tool_input if isinstance(tool_input, dict) else {'question': tool_input}))

# ─────────────────────────────────────────────────────────────────────────────
# 8. ТИПЫ ДАННЫХ
# ─────────────────────────────────────────────────────────────────────────────
class ModelCaps(TypedDict, total=False): vision: bool; tool_use: bool; reasoning: bool; json_mode: bool
class ModelInfo(TypedDict): id: str; object: str; created: int; owned_by: str; capabilities: ModelCaps; context_window: int; max_tokens: int
class AgentConfig(TypedDict, total=False):
    api_base: str; api_key: str; model: str; system_prompt: str; temperature: float; max_tokens: int; top_p: float
    frequency_penalty: float; presence_penalty: float; max_iterations: int; timeout: int; use_tools: bool
    window_geometry: str; sandbox_dir: str; sb_enable_internet: bool; sb_enable_system: bool; sb_enable_pip: bool
    sb_enable_git: bool; sb_enable_venv: bool; sb_enable_all_modules: bool; sb_enable_math: bool
    sb_enable_bool: bool; sb_enable_network: bool; sb_enable_gui: bool; sb_enable_science: bool; sb_enable_testing: bool
    sb_allowed_modules: str; sb_forbidden_patterns: str; sb_pip_index: str; sb_venv_dir: str
class TaskData(TypedDict): id: str; description: str; priority: int; status: str; result: str; error: str; created: str; progress: str

# ─────────────────────────────────────────────────────────────────────────────
# 9. МЕНЕДЖЕР ЗАДАЧ
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(order=True)
class Task:
    priority: int
    id: str = field(compare=False, default_factory=lambda: uuid.uuid4().hex[:8])
    description: str = field(compare=False, default="")
    status: str = field(compare=False, default="queued")
    result: str = field(compare=False, default="")
    error: str = field(compare=False, default="")
    progress: str = field(compare=False, default="Ожидание...")
    created_at: datetime = field(compare=False, default_factory=datetime.now)
    control: Any = field(compare=False, default=None, repr=False)
    def to_dict(self) -> TaskData:
        return {'id': self.id, 'description': self.description, 'priority': self.priority, 'status': self.status, 'result': self.result, 'error': self.error, 'created': self.created_at.isoformat(), 'progress': self.progress}

class TaskQueueManager:
    def __init__(self, max_workers: int = 1):
        self._q: queue.PriorityQueue[Task] = queue.PriorityQueue()
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._running = False; self._stop = threading.Event()
        self._workers: list[threading.Thread] = []; self._max_w = max_workers
        self._version = 0; self._active_controls: Dict[str, TaskControl] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def add(self, desc: str, pri: int = 2) -> str:
        t = Task(priority=pri, description=desc)
        with self._lock: self._tasks[t.id] = t; self._q.put(t); self._version += 1
        return t.id

    def _update_task(self, task_id: str, **updates):
        with self._lock:
            t = self._tasks.get(task_id)
            if t:
                for k, v in updates.items():
                    if hasattr(t, k): setattr(t, k, v)
                self._version += 1

    def start(self, factory: Callable[[], Any], log_cb: Callable[[str], None], progress_cb: Optional[Callable[[str,str,str,int,dict],None]] = None) -> None:
        if self._running: return
        self._running = True; self._stop.clear()
        for i in range(self._max_w):
            w = threading.Thread(target=self._loop, args=(factory, log_cb, progress_cb), daemon=True, name=f"W-{i}")
            w.start(); self._workers.append(w)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set(); self.cancel_all_running(); self._running = False
        for w in self._workers: w.join(timeout=timeout)
        self._workers.clear(); self._executor.shutdown(wait=False)

    def cancel_all_running(self) -> None:
        with self._lock:
            for ctrl in self._active_controls.values(): ctrl.cancel()
            self._active_controls.clear()

    def clear(self) -> None:
        self.stop()
        with self._lock: self._tasks.clear(); self._q = queue.PriorityQueue(); self._version += 1

    def get_snapshot(self) -> tuple[list[TaskData], int]:
        with self._lock: return ([t.to_dict() for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)], self._version)

    def get_control(self, task_id: str) -> Optional[TaskControl]:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.control if task else None

    def _loop(self, factory: Callable[[], Any], log_cb: Callable[[str], None], progress_cb: Optional[Callable[[str,str,str,int,dict],None]]) -> None:
        while not self._stop.is_set():
            try: task = self._q.get(timeout=1.0)
            except queue.Empty: continue
            with self._lock: ref = self._tasks.get(task.id)
            if not ref or ref.status != "queued": self._q.task_done(); continue
            ctrl = TaskControl(); ref.control = ctrl
            with self._lock: self._active_controls[task.id] = ctrl
            self._update_task(task.id, status="running", progress="Инициализация...")
            log_cb(f"🚀 [{task.id}] {task.description[:50]}...")
            if progress_cb: progress_cb("info", f"🚀 Задача [{task.id}] запущена", None, 0, None)
            try:
                agent = factory()
                if hasattr(agent, 'invoke'):
                    res = agent.invoke({"input": task.description, "progress_cb": progress_cb, "control": ctrl})
                    result = res.get("output", str(res)) if isinstance(res, dict) else str(res)
                else: result = str(agent(task.description))
                if ctrl.is_cancelled():
                    self._update_task(task.id, status="failed", progress="🛑 Отменено", error="Отменено пользователем")
                    log_cb(f"🛑 [{task.id}] Отменено")
                    if progress_cb: progress_cb("warning", f"🛑 Задача [{task.id}] отменена", None, None, None)
                else:
                    self._update_task(task.id, status="completed", progress="✓ Готово", result=result)
                    log_cb(f"✅ [{task.id}] Успех")
                    if progress_cb: progress_cb("success", f"✅ Задача [{task.id}] завершена", result, None, None)
            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}"
                self._update_task(task.id, status="failed", progress="✗ Ошибка", error=err_msg)
                log_cb(f"❌ [{task.id}] {err_msg}")
                if progress_cb: progress_cb("error", f"❌ Ошибка задачи [{task.id}]", err_msg, None, None)
            finally:
                with self._lock: self._active_controls.pop(task.id, None)
                self._q.task_done()

# ─────────────────────────────────────────────────────────────────────────────
# 10. МЕНЕДЖЕР МОДЕЛЕЙ
# ─────────────────────────────────────────────────────────────────────────────
class ModelManager:
    def __init__(self, api_base: str, api_key: str = "lm-studio"):
        self.api_base = validate_url(api_base); self.api_key = api_key
        self._cache: list[ModelInfo] = []; self._current: Optional[ModelInfo] = None
        self._known = {"qwen3.5": {"ctx": 131072, "tools": True, "vision": False, "reasoning": True}, "qwen3": {"ctx": 131072, "tools": True, "vision": False, "reasoning": False}, "qwen2.5": {"ctx": 131072, "tools": True, "vision": False, "reasoning": False}}
    
    def fetch_models(self) -> list[ModelInfo]:
        try:
            resp = requests.get(f"{self.api_base}/models", timeout=10, headers={"Authorization": f"Bearer {self.api_key}"})
            resp.raise_for_status(); data = resp.json(); models = []
            for m in data.get("data", []): models.append(self._detect_caps(m.get("id", "unknown")))
            self._cache = models; return models
        except Exception as e: logger.error(f"Ошибка загрузки моделей: {e}", exc_info=True); return []
    
    def _detect_caps(self, mid: str) -> ModelInfo:
        ml = mid.lower(); caps: ModelCaps = {'vision': False, 'tool_use': False, 'reasoning': False, 'json_mode': True}; ctx = 32768
        for k, v in self._known.items():
            if k in ml: caps.update({'vision':v['vision'],'tool_use':v['tools'],'reasoning':v['reasoning']}); ctx = v['ctx']; break
        if any(x in ml for x in ['vision','llava','claude-3']): caps['vision'] = True
        if any(x in ml for x in ['tool','function','agent','coder','qwen3','qwen2.5']): caps['tool_use'] = True
        if any(x in ml for x in ['reasoning','o1','o3','deepseek-r1','qwen3.5']): caps['reasoning'] = True
        return {'id':mid,'object':'model','created':int(time.time()),'owned_by':'lm-studio','capabilities':caps,'context_window':ctx,'max_tokens':min(ctx//2, 8192)}
    
    def get_model_info(self, mid: str) -> Optional[ModelInfo]:
        for m in self._cache:
            if m['id'] == mid: self._current = m; return m
        self._current = self._detect_caps(mid); return self._current
    def get_current(self) -> Optional[ModelInfo]: return self._current

# ─────────────────────────────────────────────────────────────────────────────
# 11. 🔧 АГЕНТ (ИСПРАВЛЕНА ИНТЕГРАЦИЯ LANGCHAIN + ПРОГРЕСС МЕЖДУ ИТЕРАЦИЯМИ)
# ─────────────────────────────────────────────────────────────────────────────
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig

class QwenCompatibleAgent:
    SYSTEM_PROMPT = """Ты — экспертный Python-разработчик и QA-инженер в LangChain-агенте.
Твоя цель: написать, протестировать и отладить код до production-ready состояния.
📜 СТРОГИЕ ПРАВИЛА:
ЯЗЫК: Все комментарии, docstrings, логи и финальный отчёт — СТРОГО НА РУССКОМ. Идентификаторы кода — на английском (PEP 8).
ИНСТРУМЕНТЫ: НИКОГДА не пиши код в текстовом ответе. ВСЕГДА используй инструменты для выполнения.

📁 ДОСТУП К ФАЙЛОВОЙ СИСТЕМЕ:
- Ты работаешь в изолированной песочнице. Тебе РАЗРЕШЕНО читать и писать файлы в текущей рабочей директории.
- Все файлы проекта (например, «Задача.txt», «data.csv») лежат в корне sandbox. Используй ОТНОСИТЕЛЬНЫЕ ПУТИ.
- Чтение: `with open('Задача.txt', 'r', encoding='utf-8') as f: content = f.read()`
- Запись: `with open('output.py', 'w', encoding='utf-8') as f: f.write(code)`
- Если пользователь упоминает файл, СНАЧАЛА прочитай его через `python_repl_safe`, затем выполняй задачу.

❓ ОБЩЕНИЕ С ПОЛЬЗОВАТЕЛЕМ:
- Если задача неясна, есть несколько вариантов решения или нужны уточнения — ИСПОЛЬЗУЙ инструмент `ask_user`.
- Задавай конкретные вопросы с вариантами ответа, если это уместно.
- Пример: `{"name": "ask_user", "arguments": {"question": "Какой формат вывода предпочитаете: JSON или CSV?", "options": "JSON,CSV,Таблица"}}`
- После получения ответа продолжай выполнение задачи.

🔄 ЦИКЛ САМОПРОВЕРКИ: Напиши код → Выполни через инструмент → Проанализируй вывод → Исправь ошибки → Повтори.
⚠️ БЕЗОПАСНОСТЬ: Не используй сеть или системные команды (`os.system`, `subprocess`) без явного запроса.
📊 ФОРМАТ ФИНАЛЬНОГО ОТЧЁТА: ✅ Код готов и проверен. 📋 Протестировано: [...] 🛡️ Граничные случаи: [...] 📦 Зависимости: [...]
🔑 ПАМЯТАЙ: Код не считается выполненным, пока не прошёл инструментальную проверку без ошибок."""

    def __init__(self, llm: ChatOpenAI, tools: list[BaseTool], system_prompt: str, max_iterations: int = 50, timeout: int = 1800):
        self.system_prompt = (system_prompt or self.SYSTEM_PROMPT) + "\n\n[ИНСТРУКЦИЯ]\nИспользуй только предоставленные инструменты."
        self.max_iterations = max_iterations; self.timeout = timeout
        self.llm = llm.bind_tools(tools) if tools else llm
        self.tools = {t.name: t for t in tools} if tools else {}
        self._reasoning_fallback_count = 0

    def _build_messages(self, user_input: str, history: list | None = None) -> list:
        msgs = [SystemMessage(content=self.system_prompt), HumanMessage(content=user_input)]
        if history: msgs.extend(history)
        return msgs

    def _execute_tool(self, name: str, args: dict | str, progress_cb: Optional[Callable] = None, control: Optional[TaskControl] = None) -> str:
        tool = self.tools.get(name)
        if not tool: 
            msg = f"⚠️ Инструмент '{name}' не найден"
            if progress_cb: progress_cb("warning", f"🔧 Инструмент не найден: {name}", msg, None, {'name': name, 'args': args})
            return msg
        try:
            if name == "ask_user" and hasattr(tool, 'control'):
                tool.control = control
            if progress_cb: 
                args_short = {k: (str(v)[:30]+"..." if len(str(v)) >30 else str(v)) for k,v in (args if isinstance(args,dict) else {'code':str(args)}).items()}
                progress_cb("info", f"🔧 Вызов: {name}", f"Аргументы: {json.dumps(args_short, ensure_ascii=False)}", None, {'name': name, 'args': args_short})
            
            t0 = time.time()
            result = str(tool.invoke(args))
            elapsed = time.time() - t0
            
            if progress_cb:
                status = "success" if "❌" not in result and "⚠️" not in result else "warning" if "⚠️" in result else "error"
                icon = "✅" if status=="success" else "⚠️" if status=="warning" else "❌"
                progress_cb(status, f"{icon} {name} завершён за {elapsed:.1f}с", result[:150], None, {'name': name, 'result': result[:80], 'time': f"{elapsed:.1f}s"})
            return result
        except Exception as e:
            msg = f"❌ {type(e).__name__}: {e}"
            if progress_cb: progress_cb("error", f"❌ Ошибка инструмента {name}", msg, None, {'name': name, 'error': str(e)})
            return msg

    def invoke(self, input_: dict) -> dict:
        if not isinstance(input_, dict): return {"output": "❌ Ошибка формата"}
        user_input = input_.get("input", ""); progress_cb = input_.get("progress_cb"); control = input_.get("control")
        if not user_input: return {"output": "⚠️ Пустой запрос"}
        if progress_cb: progress_cb("info", "📋 Анализ задачи...", user_input[:100], 0, None)
        messages = self._build_messages(user_input)
        
        for iteration in range(1, self.max_iterations + 1):
            if control:
                if control.is_cancelled(): return {"output": "🛑 Отменено пользователем"}
                control.wait_if_paused()
                if control.is_cancelled(): return {"output": "🛑 Отменено пользователем"}
            try:
                # ✅ Точка 1: начало итерации
                if progress_cb:
                    progress_cb("debug", f"🔄 Итерация {iteration}/{self.max_iterations}", f"Запрос к модели: {self._cfg.get('model', 'unknown') if hasattr(self, '_cfg') else 'LLM'}", iteration, None)
                
                callback_handler = LangChainProgressHandler(progress_cb)
                
                # ✅ Точка 2: перед вызовом LLM (каждые 5 итераций, чтобы не спамить)
                if progress_cb and iteration % 5 == 0:
                    progress_cb("info", f"🤖 Запрос к модели...", f"Итерация {iteration}", iteration, None)
                
                # ✅ ИСПРАВЛЕНО: RunnableConfig для callbacks (LangChain 1.2.15)
                config: RunnableConfig = {"callbacks": [callback_handler]}
                response = self.llm.invoke(messages, config=config)
                
                # ✅ Точка 3: после получения ответа от LLM
                if progress_cb:
                    tool_calls = getattr(response, 'tool_calls', []) or []
                    if tool_calls:
                        progress_cb("info", f"🔧 Получено {len(tool_calls)} вызов(ов) инструмента(ов)", None, iteration, None)
                    else:
                        progress_cb("success", f"✅ LLM сгенерировал ответ", response.content[:100] if response.content else "Без текста", iteration, None)
                
                tool_calls = getattr(response, 'tool_calls', []) or []
                
                if not response.content and not tool_calls:
                    usage = getattr(response, 'usage_metadata', {}) or {}
                    out_det = usage.get('output_token_details', {}) or {}
                    if out_det.get('reasoning', 0) > 0 and self._reasoning_fallback_count < 3:
                        self._reasoning_fallback_count += 1
                        if progress_cb: progress_cb("warning", "🤔 Модель в режиме рассуждения, упрощаю запрос...", None, iteration, None)
                        messages.append(HumanMessage(content="КРАТКО: вызови инструмент. Только JSON."))
                        continue
                    elif out_det.get('reasoning', 0) > 0:
                        return {"output": "⚠️ Модель не сформировала ответ после reasoning-фазы."}
                
                self._reasoning_fallback_count = 0
                if tool_calls:
                    messages.append(response)
                    for i, tc in enumerate(tool_calls, 1):
                        t_name, t_args = tc.get('name'), tc.get('args', {})
                        # ✅ Точка 4: перед вызовом инструмента
                        if progress_cb:
                            progress_cb("info", f"🔧 [{i}/{len(tool_calls)}] Запуск: {t_name}", json.dumps(t_args, ensure_ascii=False)[:100], iteration, {'name': t_name, 'args': t_args})
                        res = self._execute_tool(t_name, t_args, progress_cb, control)
                        # ✅ Точка 5: после выполнения инструмента (уже в _execute_tool)
                        messages.append(ToolMessage(content=res, tool_call_id=tc.get('id', uuid.uuid4().hex), name=t_name))
                    continue
                    
                if progress_cb: progress_cb("success", "✅ Завершение...", response.content[:100] if response.content else "Без вывода", iteration, None)
                return {"output": response.content}
            except Exception as e:
                if progress_cb: progress_cb("error", f"❌ Ошибка итерации {iteration}", str(e)[:150], iteration, None)
                if iteration == self.max_iterations: return {"output": f"❌ Ошибка после {self.max_iterations} итераций: {e}"}
                messages.append(AIMessage(content=f"[Ошибка: {e}]"))
        return {"output": "⚠️ Лимит итераций"}

# ─────────────────────────────────────────────────────────────────────────────
# 12. ФАБРИКА & КОНФИГ
# ─────────────────────────────────────────────────────────────────────────────
class AgentFactory:
    def __init__(self):
        self._cfg: AgentConfig = {
            "api_base": "http://localhost:1234", "api_key": "lm-studio", "model": "qwen/qwen3.5-9b",
            "system_prompt": QwenCompatibleAgent.SYSTEM_PROMPT, "temperature": 0.1, "max_tokens": 4096,
            "top_p": 0.9, "frequency_penalty": 0.0, "presence_penalty": 0.0,
            "max_iterations": 50, "timeout": 1800, "use_tools": True,
            "window_geometry": "1400x900", "sandbox_dir": str(Path.home() / "lm_agent_sandbox"),
            "sb_enable_internet": False, "sb_enable_system": False, "sb_enable_pip": True,
            "sb_enable_git": False, "sb_enable_venv": False, "sb_enable_all_modules": False,
            "sb_enable_math": True, "sb_enable_bool": True, "sb_enable_network": False,
            "sb_enable_gui": False, "sb_enable_science": True, "sb_enable_testing": True,
            "sb_allowed_modules": "", "sb_forbidden_patterns": "", "sb_pip_index": "https://pypi.org/simple", "sb_venv_dir": ""
        }
        self._mgr: Optional[ModelManager] = None
    
    def set_model_manager(self, mgr: ModelManager): self._mgr = mgr
    def configure(self, **kw): self._cfg.update({k:v for k,v in kw.items() if k in self._cfg})
    
    def create_agent(self, sandbox_dir: str = None) -> Any:
        wd = sandbox_dir or self._cfg.get("sandbox_dir")
        sb_cfg = SandboxAdvancedConfig(
            enable_internet=self._cfg.get("sb_enable_internet", False), enable_system_cmds=self._cfg.get("sb_enable_system", False),
            enable_pip=self._cfg.get("sb_enable_pip", True), enable_git=self._cfg.get("sb_enable_git", False),
            enable_venv=self._cfg.get("sb_enable_venv", False), enable_all_modules=self._cfg.get("sb_enable_all_modules", False),
            enable_math=self._cfg.get("sb_enable_math", True), enable_bool=self._cfg.get("sb_enable_bool", True),
            enable_network=self._cfg.get("sb_enable_network", False), enable_gui=self._cfg.get("sb_enable_gui", False),
            enable_science=self._cfg.get("sb_enable_science", True), enable_testing=self._cfg.get("sb_enable_testing", True),
            custom_allowed_modules=self._cfg.get("sb_allowed_modules", ""), custom_forbidden_patterns=self._cfg.get("sb_forbidden_patterns", ""),
            pip_index_url=self._cfg.get("sb_pip_index", "https://pypi.org/simple"), venv_dir=self._cfg.get("sb_venv_dir", "")
        )
        tools = []
        if self._cfg.get("use_tools", True):
            tools.append(SafePythonREPL(timeout=self._cfg.get("timeout",1800), work_dir=wd, sandbox_config=sb_cfg))
            tools.append(PipInstallTool(sandbox_config=sb_cfg))
            tools.append(GitOperationTool(sandbox_config=sb_cfg))
            tools.append(VenvManagerTool(sandbox_config=sb_cfg))
            tools.append(AskUserTool())
        
        # ✅ ChatOpenAI: base_url вместо openai_api_base, timeout в инициализации
        llm = ChatOpenAI(
            model=self._cfg.get("model", "qwen/qwen3.5-9b"),
            base_url=validate_url(self._cfg["api_base"]),
            api_key=self._cfg["api_key"] or "lm-studio",
            temperature=float(self._cfg.get("temperature") or 0.1),
            max_tokens=int(self._cfg.get("max_tokens") or 4096),
            max_retries=3,
            timeout=1800,
            extra_body={"ttl": 300}
        )
        agent = QwenCompatibleAgent(llm=llm, tools=tools, system_prompt=self._cfg.get("system_prompt"), max_iterations=int(self._cfg.get("max_iterations") or 50), timeout=int(self._cfg.get("timeout") or 1800))
        agent._cfg = self._cfg  # ✅ Передаём конфиг для отображения в логах
        return agent

class ConfigManager:
    PATH = LOG_DIR / "config.json"; BACKUP = LOG_DIR / "config.backup.json"
    @classmethod
    def load(cls) -> AgentConfig:
        for p in (cls.PATH, cls.BACKUP):
            if p.exists():
                try:
                    with open(p,'r',encoding='utf-8') as f: cfg = json.load(f)
                    def_cfg = AgentFactory()._cfg
                    return {**def_cfg, **{k:v for k,v in cfg.items() if k in def_cfg}}
                except Exception: continue
        return AgentFactory()._cfg.copy()
    @classmethod
    def save(cls, cfg: AgentConfig) -> bool:
        try:
            if cls.PATH.exists(): cls.PATH.replace(cls.BACKUP)
            with open(cls.PATH,'w',encoding='utf-8') as f: json.dump(cfg,f,indent=2,ensure_ascii=False)
            return True
        except Exception: return False

# ─────────────────────────────────────────────────────────────────────────────
# 13. GUI: ДИАЛОГ НАСТРОЕК ПЕСОЧНИЦЫ
# ─────────────────────────────────────────────────────────────────────────────
class AdvancedSandboxDialog(tk.Toplevel):
    def __init__(self, parent, config: dict, apply_cb: Callable[[dict], None]):
        super().__init__(parent)
        self.title("⚙️ Расширенные настройки песочницы"); self.geometry("750x650")
        self.transient(parent); self.grab_set(); self.config = config.copy(); self.apply_cb = apply_cb
        self._build_ui()
    def _build_ui(self):
        nb = ttk.Notebook(self); nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        f0 = ttk.Frame(nb, padding=10); nb.add(f0, text="🔓 Главное")
        ttk.Label(f0, text="⚠️ ВНИМАНИЕ: Эти настройки влияют на безопасность!", foreground="red", font=("Arial",9,"bold")).pack(anchor=tk.W, pady=5)
        self.var_all = tk.BooleanVar(value=self.config.get("sb_enable_all_modules", False)); ttk.Checkbutton(f0, text="🔓 РАЗРЕШИТЬ ВСЕ МОДУЛИ", variable=self.var_all).pack(anchor=tk.W, pady=5)
        ttk.Separator(f0, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.var_net = tk.BooleanVar(value=self.config.get("sb_enable_internet", False)); ttk.Checkbutton(f0, text="🌐 Сетевые запросы", variable=self.var_net).pack(anchor=tk.W)
        self.var_sys = tk.BooleanVar(value=self.config.get("sb_enable_system", False)); ttk.Checkbutton(f0, text="💻 Системные команды", variable=self.var_sys).pack(anchor=tk.W)
        self.var_files = tk.BooleanVar(value=True); ttk.Checkbutton(f0, text="📁 Доступ к файлам", variable=self.var_files).pack(anchor=tk.W)
        f1 = ttk.Frame(nb, padding=10); nb.add(f1, text="📦 Группы модулей")
        self.var_math = tk.BooleanVar(value=self.config.get("sb_enable_math", True)); ttk.Checkbutton(f1, text="🧮 Математика", variable=self.var_math).pack(anchor=tk.W)
        self.var_data = tk.BooleanVar(value=self.config.get("sb_enable_bool", True)); ttk.Checkbutton(f1, text="📊 Данные (json, csv)", variable=self.var_data).pack(anchor=tk.W)
        self.var_network = tk.BooleanVar(value=self.config.get("sb_enable_network", False)); ttk.Checkbutton(f1, text="🌐 Сеть (requests, socket)", variable=self.var_network).pack(anchor=tk.W)
        self.var_gui = tk.BooleanVar(value=self.config.get("sb_enable_gui", False)); ttk.Checkbutton(f1, text="🎨 GUI (tkinter, PyQt)", variable=self.var_gui).pack(anchor=tk.W)
        self.var_science = tk.BooleanVar(value=self.config.get("sb_enable_science", True)); ttk.Checkbutton(f1, text="🔬 Наука (numpy, pandas)", variable=self.var_science).pack(anchor=tk.W)
        self.var_testing = tk.BooleanVar(value=self.config.get("sb_enable_testing", True)); ttk.Checkbutton(f1, text="🧪 Тесты (pytest, unittest)", variable=self.var_testing).pack(anchor=tk.W)
        f2 = ttk.Frame(nb, padding=10); nb.add(f2, text="🛠️ Инструменты")
        self.var_pip = tk.BooleanVar(value=self.config.get("sb_enable_pip", True)); ttk.Checkbutton(f2, text="✅ pip install", variable=self.var_pip).pack(anchor=tk.W)
        self.var_git = tk.BooleanVar(value=self.config.get("sb_enable_git", False)); ttk.Checkbutton(f2, text="✅ Git", variable=self.var_git).pack(anchor=tk.W)
        self.var_venv = tk.BooleanVar(value=self.config.get("sb_enable_venv", False)); ttk.Checkbutton(f2, text="✅ Venv", variable=self.var_venv).pack(anchor=tk.W)
        f3 = ttk.Frame(nb, padding=10); nb.add(f3, text="🛡️ Правила")
        ttk.Label(f3, text="Доп. разрешённые модули:").pack(anchor=tk.W)
        self.var_mods = tk.Text(f3, height=2, width=70, font=("Consolas",9)); self.var_mods.insert("1.0", self.config.get("sb_allowed_modules", "")); self.var_mods.pack(fill=tk.X, pady=2)
        ttk.Label(f3, text="Доп. запрещённые паттерны:").pack(anchor=tk.W, pady=(5,2))
        self.var_forb = tk.Text(f3, height=2, width=70, font=("Consolas",9)); self.var_forb.insert("1.0", self.config.get("sb_forbidden_patterns", "")); self.var_forb.pack(fill=tk.X, pady=2)
        btn_f = ttk.Frame(self, padding=10); btn_f.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(btn_f, text="💾 Применить", command=self._apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_f, text="❌ Отмена", command=self.destroy).pack(side=tk.RIGHT)
    def _apply(self):
        self.config.update({
            "sb_enable_all_modules": self.var_all.get(), "sb_enable_internet": self.var_net.get(), "sb_enable_system": self.var_sys.get(),
            "sb_enable_pip": self.var_pip.get(), "sb_enable_git": self.var_git.get(), "sb_enable_venv": self.var_venv.get(),
            "sb_enable_math": self.var_math.get(), "sb_enable_bool": self.var_data.get(), "sb_enable_network": self.var_network.get(),
            "sb_enable_gui": self.var_gui.get(), "sb_enable_science": self.var_science.get(), "sb_enable_testing": self.var_testing.get(),
            "sb_allowed_modules": self.var_mods.get("1.0", tk.END).strip(), "sb_forbidden_patterns": self.var_forb.get("1.0", tk.END).strip(),
            "allow_local_files": self.var_files.get()
        })
        if self.var_all.get() and not messagebox.askyesno("⚠️ Подтверждение", "Разрешить все модули? Это снижает безопасность."): return
        self.apply_cb(self.config); self.destroy()

# ─────────────────────────────────────────────────────────────────────────────
# 14. GUI: ОСНОВНОЕ ОКНО
# ─────────────────────────────────────────────────────────────────────────────
class AgentGUI(tk.Tk):
    _STATUS = {"queued": "⏸️", "running": "▶️", "completed": "✅", "failed": "❌"}
    def __init__(self):
        super().__init__()
        self._cfg = ConfigManager.load()
        self._setup_window(); self._init_components(); self._build_ui(); self._bind_events()
        self._context_menu: Optional[tk.Menu] = None; self._tree_version = -1
        self._progress_windows: Dict[str, ProgressWindow] = {}
        self.after(100, self._poll_logs); self.after(500, self._fetch_models); self.after(1000, self._refresh_tree)
    
    def _setup_window(self):
        self.title("🧠 LM Studio Agent v12.0.0")
        g = self._cfg.get("window_geometry", "1400x900")
        if g and "x" in g: self.geometry(g)
        self.minsize(1200, 800)
        s = ttk.Style()
        if "clam" in s.theme_names(): s.theme_use("clam")
        self.configure(bg="#f0f2f5")
        
    def _init_components(self):
        self._queue = TaskQueueManager(max_workers=1); self._factory = AgentFactory()
        self._factory.configure(**self._cfg)
        self._mgr = ModelManager(self._cfg.get("api_base", "http://localhost:1234"), self._cfg.get("api_key", "lm-studio"))
        self._factory.set_model_manager(self._mgr)
        self._log_q: queue.Queue[tuple[str,str]] = queue.Queue(); self._model_info: Optional[ModelInfo] = None
        
    def _build_ui(self):
        top = ttk.Frame(self, padding=8); top.pack(fill=tk.X)
        ttk.Label(top, text="🌐 API:").pack(side=tk.LEFT, padx=(0,4))
        self._api_v = tk.StringVar(value=self._cfg.get("api_base", "")); ttk.Entry(top, textvariable=self._api_v, width=24).pack(side=tk.LEFT, padx=(0,4))
        ttk.Label(top, text="🔑 Key:").pack(side=tk.LEFT, padx=(4,4))
        self._key_v = tk.StringVar(value=self._cfg.get("api_key", "")); ttk.Entry(top, textvariable=self._key_v, width=12, show="•").pack(side=tk.LEFT, padx=(0,4))
        ttk.Label(top, text="🤖 Модель:").pack(side=tk.LEFT, padx=(4,4))
        self._mod_v = tk.StringVar(value=self._cfg.get("model", "")); self._mod_c = ttk.Combobox(top, textvariable=self._mod_v, width=22, state="readonly")
        self._mod_c.pack(side=tk.LEFT, padx=(0,4)); self._mod_c.bind("<<ComboboxSelected>>", self._on_model_change)
        ttk.Button(top, text="🔄", command=self._fetch_models, width=3).pack(side=tk.LEFT)
        self._stat = ttk.Label(top, text="⏳ Загрузка...", foreground="gray"); self._stat.pack(side=tk.LEFT, padx=(10,0))
        act = ttk.Frame(top); act.pack(side=tk.RIGHT)
        ttk.Button(act, text="⚙️ Песочница", command=self._open_sandbox_settings).pack(side=tk.LEFT, padx=2)
        ttk.Button(act, text="💾 Применить", command=self._apply).pack(side=tk.LEFT, padx=2)
        self._info_f = ttk.LabelFrame(self, text="📊 Модель", padding=8); self._info_f.pack(fill=tk.X, padx=8, pady=(0,8))
        self._info_t = tk.Text(self._info_f, height=3, wrap=tk.WORD, bg="#e8f4f8", font=("Consolas",9)); self._info_t.pack(fill=tk.X)
        self._info_t.insert("1.0", "Нажмите 🔄"); self._info_t.config(state=tk.DISABLED)
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        left = ttk.LabelFrame(main, text="📋 Задачи", padding=8); main.add(left, weight=3)
        cols = [("id", "ID",60),("desc", "Задача",220),("pri", "Приор.",50),("status", "Статус",70),("progress", "Прогресс",200)]
        self._tree = ttk.Treeview(left, columns=[c[0] for c in cols], show="headings", height=12)
        for i,t,w in cols: self._tree.heading(i,text=t); self._tree.column(i,width=w,anchor=tk.CENTER if i!="desc" else tk.W)
        self._tree.pack(fill=tk.BOTH, expand=True); self._tree.bind("<Button-3>", self._show_context_menu); self._tree.bind("<<TreeviewSelect>>", self._on_select)
        ts = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview); ts.pack(side=tk.RIGHT, fill=tk.Y); self._tree.configure(yscrollcommand=ts.set)
        bf = ttk.Frame(left); bf.pack(fill=tk.X, pady=4)
        for txt,cmd in [("➕ Задача",self._add),("▶️ Старт",self._start),("⏹️ Стоп",self._stop),("🗑️ Очистить",self._clear)]:
            ttk.Button(bf, text=txt, command=cmd).pack(side=tk.LEFT, padx=2)
        sandbox_frame = ttk.Frame(left); sandbox_frame.pack(fill=tk.X, pady=(4,0))
        ttk.Label(sandbox_frame, text="📁 Песочница:").pack(side=tk.LEFT)
        self._sandbox_var = tk.StringVar(value=self._cfg.get("sandbox_dir", "")); ttk.Entry(sandbox_frame, textvariable=self._sandbox_var, width=25, state="readonly").pack(side=tk.LEFT, padx=4)
        ttk.Button(sandbox_frame, text="📂 Выбрать...", command=self._select_sandbox).pack(side=tk.LEFT)
        right = ttk.LabelFrame(main, text="⚙️ Настройки", padding=8); main.add(right, weight=2)
        ttk.Label(right, text="Промпт:").pack(anchor=tk.W)
        self._prompt = scrolledtext.ScrolledText(right, height=6, width=38, font=("Consolas",9)); self._prompt.insert("1.0", self._cfg.get("system_prompt", "")); self._prompt.pack(fill=tk.BOTH, expand=True, pady=4)
        sf = ttk.Frame(right); sf.pack(fill=tk.X); self._param_vars = {}
        for i,(lbl,frm,to,inc,w,key) in enumerate([("Temp:", 0, 2, 0.1, 8, "temperature"), ("Max tok:", 100, 8192, 100, 8, "max_tokens"), ("Top P:", 0, 1, 0.05, 8, "top_p"), ("Iter:", 1, 50, 1, 8, "max_iterations")]):
            ttk.Label(sf, text=lbl).grid(row=i, column=0, sticky=tk.W, pady=2)
            var_obj = tk.DoubleVar() if inc < 1 else tk.IntVar(); var_obj.set(self._cfg.get(key, frm if inc==1 else 0.1 if inc <1 else 50))
            spin = ttk.Spinbox(sf, from_=frm, to=to, increment=inc, width=w, textvariable=var_obj); spin.grid(row=i, column=1, padx=5, pady=2)
            self._param_vars[key] = var_obj
        self._tools_v = tk.BooleanVar(value=self._cfg.get("use_tools",True)); ttk.Checkbutton(right, text="✅ Инструменты", variable=self._tools_v).pack(anchor=tk.W, pady=4)
        lf = ttk.LabelFrame(self, text="📜 Лог", padding=8); lf.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0,8))
        self._log_txt = scrolledtext.ScrolledText(lf, height=7, font=("Consolas",9), state=tk.DISABLED, bg="#1e1e1e", fg="#00ff00"); self._log_txt.pack(fill=tk.BOTH, expand=True)
        self._log_txt.tag_config("err",foreground="#ff6b6b"); self._log_txt.tag_config("warn",foreground="#ffa500"); self._log_txt.bind("<Double-Button-1>", lambda e: self._clear_log())
        self._status_bar = ttk.Label(self, text="Готов", relief=tk.SUNKEN, anchor=tk.W); self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
    def _open_sandbox_settings(self):
        def on_apply(cfg):
            self._cfg.update(cfg); ConfigManager.save(self._cfg); self._factory.configure(**self._cfg)
            self._log("💾 Настройки песочницы обновлены", "info")
        AdvancedSandboxDialog(self, self._cfg, on_apply)
        
    def _show_context_menu(self, event):
        item = self._tree.identify_row(event.y)
        if not item: return
        self._tree.selection_set(item)
        if not self._context_menu:
            self._context_menu = tk.Menu(self, tearoff=0)
            self._context_menu.add_command(label="👁️ Просмотр", command=self._ctx_view_result)
            self._context_menu.add_command(label="🔄 Повторить", command=self._ctx_retry)
            self._context_menu.add_separator(); self._context_menu.add_command(label="🗑️ Удалить", command=self._ctx_delete)
        self._context_menu.tk_popup(event.x_root, event.y_root)
        
    def _ctx_view_result(self): self._on_select()
    def _ctx_retry(self):
        sel = self._tree.selection()
        if not sel: return
        tid = self._tree.item(sel[0])["values"][0]
        tasks, _ = self._queue.get_snapshot()
        task = next((t for t in tasks if t["id"] == tid), None)
        if task and task["description"]: self._queue.add(task["description"], task["priority"]); self._refresh_tree()
    def _ctx_delete(self):
        sel = self._tree.selection()
        if not sel: return
        tid = self._tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Удалить", f"Удалить задачу {tid}?"):
            with self._queue._lock:
                if tid in self._queue._tasks: del self._queue._tasks[tid]; self._queue._version += 1
            self._refresh_tree()
    def _select_sandbox(self):
        path = filedialog.askdirectory(initialdir=self._cfg.get("sandbox_dir"), title="Папка песочницы")
        if path: self._sandbox_var.set(path); self._cfg["sandbox_dir"] = path; ConfigManager.save(self._cfg)
    def _bind_events(self): self.protocol("WM_DELETE_WINDOW", self._close); self.bind("<Configure>", lambda e: self._save_geo() if e.widget==self else None)
    def _save_geo(self):
        g = self.geometry()
        if g and "x" in g: self._cfg["window_geometry"] = g
    def _close(self): self._queue.stop(); self._save_cfg(); self._save_geo(); ConfigManager.save(self._cfg); self.destroy()
    def _save_cfg(self):
        self._cfg.update({
            "api_base": self._api_v.get().strip().rstrip('/'), "api_key": self._key_v.get(), "model": self._mod_v.get(),
            "system_prompt": self._prompt.get("1.0",tk.END).strip(), "temperature": float(self._param_vars["temperature"].get() or 0.1),
            "max_tokens": int(self._param_vars["max_tokens"].get() or 4096), "top_p": float(self._param_vars["top_p"].get() or 0.9),
            "max_iterations": int(self._param_vars["max_iterations"].get() or 50), "use_tools": self._tools_v.get(),
            "sandbox_dir": self._sandbox_var.get(), "timeout": 1800
        })
    def _apply(self):
        self._save_cfg()
        if ConfigManager.save(self._cfg): self._factory.configure(**self._cfg); self._log("💾 Сохранено", "info")
        else: messagebox.showwarning("Ошибка", "Не удалось сохранить!")
    def _fetch_models(self):
        self._stat.config(text="📡...", foreground="blue"); self._mod_c.config(state="disabled")
        def bg():
            try:
                models = self._mgr.fetch_models()
                if not models: models = [{"id": "qwen/qwen3.5-9b", "capabilities":{}, "context_window":4096, "max_tokens":4096}]
                def ui():
                    self._mod_c["values"] = [m["id"] for m in models]
                    cur = self._mod_v.get()
                    self._mod_c.set(cur if cur in [m["id"] for m in models] else models[0]["id"])
                    self._mod_c.config(state="readonly"); self._stat.config(text=f"✅ {len(models)}", foreground="green"); self._update_info()
                self.after(0, ui)
            except Exception: self.after(0, lambda: self._stat.config(text="⚠️", foreground="orange"))
        threading.Thread(target=bg, daemon=True).start()
    def _on_model_change(self, event=None): self._model_info = self._mgr.get_model_info(self._mod_v.get()); self._update_info()
    def _update_info(self):
        if not self._model_info: return
        m = self._model_info; c = m.get("capabilities",{})
        info = f"Модель: {m['id']}\nContext: {m.get('context_window','N/A')} | Max: {m.get('max_tokens','N/A')}\n👁️{c.get('vision',False)} 🔧{c.get('tool_use',False)} 🧠{c.get('reasoning',False)}"
        self._info_t.config(state=tk.NORMAL); self._info_t.delete("1.0",tk.END); self._info_t.insert("1.0",info); self._info_t.config(state=tk.DISABLED)
    def _add(self):
        w=tk.Toplevel(self); w.title("➕ Задача"); w.geometry("600x350"); w.transient(self); w.grab_set()
        ttk.Label(w, text="Описание:").pack(pady=(12,4), anchor=tk.W, padx=16)
        d=scrolledtext.ScrolledText(w, height=8, width=70, font=("Consolas",9)); d.pack(pady=4, padx=16, fill=tk.BOTH, expand=True); d.focus()
        p=tk.IntVar(value=2); pf=ttk.Frame(w); pf.pack(pady=8)
        for t,v in [("🔴 Высокий",1),("🟡 Нормальный",2),("🟢 Низкий",3)]: ttk.Radiobutton(pf, text=t, variable=p, value=v).pack(side=tk.LEFT, padx=6)
        def ok():
            txt=d.get("1.0",tk.END).strip()
            if not (5 <= len(txt) <=1000): messagebox.showwarning("Внимание", "5-1000 символов"); return
            tid=self._queue.add(txt,p.get()); self._refresh_tree(); self._log(f"📥 [{tid}] {txt[:40]}...", "info"); w.destroy()
        bf=ttk.Frame(w); bf.pack(pady=12)
        ttk.Button(bf, text="❌", command=w.destroy).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="✅", command=ok).pack(side=tk.LEFT, padx=8)
        w.bind("<Return>", lambda e: ok()); w.bind("<Escape>", lambda e: w.destroy())
    def _start(self):
        self._save_cfg(); self._factory.configure(**self._cfg)
        def progress_cb(level: str, message: str, details: str, iteration: int, tool_call: dict):
            sel = self._tree.selection(); tid = sel[0] if sel else None
            if tid and tid in self._progress_windows:
                self._progress_windows[tid].add(level, message, details, iteration, tool_call)
        def answer_cb(answer: str):
            sel = self._tree.selection(); tid = sel[0] if sel else None
            if tid:
                ctrl = self._queue.get_control(tid)
                if ctrl: ctrl.answer_queue.put(answer)
        self._queue.start(lambda: self._factory.create_agent(sandbox_dir=self._cfg.get("sandbox_dir")), self._log, progress_cb)
        self._log("▶️ Запуск", "info")
    def _stop(self): self._queue.stop(); self._log("⏹️ Стоп", "warn")
    def _clear(self):
        if messagebox.askyesno("Подтверждение", "Очистить ВСЕ задачи?"):
            for pw in self._progress_windows.values(): pw.destroy()
            self._progress_windows.clear(); self._queue.clear(); self._refresh_tree(); self._log("🗑️ Очищено", "warn")
    def _refresh_tree(self):
        snapshot, version = self._queue.get_snapshot()
        if version == self._tree_version: self.after(1000, self._refresh_tree); return
        self._tree_version = version; self._tree.delete(*self._tree.get_children())
        for t in snapshot:
            desc = t["description"][:30] + ("..." if len(t["description"]) >30 else "")
            status_icon = self._STATUS.get(t["status"], t["status"])
            progress_text = t.get("progress", "")
            if t["status"] == "running" and progress_text:
                progress_display = progress_text[:40] + ("..." if len(progress_text)>40 else "")
                self._tree.insert("", tk.END, values=(t["id"], desc, t["priority"], f"{status_icon}", progress_display))
            else:
                self._tree.insert("", tk.END, values=(t["id"], desc, t["priority"], status_icon, progress_text))
            if t["status"] == "running":
                if t["id"] not in self._progress_windows:
                    ctrl = self._queue.get_control(t["id"])
                    if ctrl:
                        pw = ProgressWindow(self, t["id"], t["description"], ctrl, lambda ans, tid=t["id"]: self._queue.get_control(tid).answer_queue.put(ans) if self._queue.get_control(tid) else None)
                        self._progress_windows[t["id"]] = pw; pw.add("info", f"🚀 Задача запущена", t["description"][:100], 0, None)
            elif t["status"] in ("completed", "failed") and t["id"] in self._progress_windows:
                pw = self._progress_windows[t["id"]]
                pw.add("success" if t["status"]=="completed" else "error", f"{'✅' if t['status']=='completed' else '❌'} Завершено", t.get("result") or t.get("error"), None, None)
                self.after(3000, lambda tid=t["id"]: self._cleanup_window(tid))
        self.after(1000, self._refresh_tree)
    def _cleanup_window(self, tid: str):
        if tid in self._progress_windows:
            try: self._progress_windows[tid].destroy()
            except Exception: pass
            del self._progress_windows[tid]
    def _on_select(self, e=None):
        s=self._tree.selection()
        if not s: return
        tid=self._tree.item(s[0])["values"][0]
        tasks, _ = self._queue.get_snapshot()
        t=next((x for x in tasks if x["id"]==tid), None)
        if t and (t.get("result") or t.get("error")): self._show_res(t["description"], t.get("result") or f"❌ {t['error']}")
        if t and t["status"] == "running" and tid in self._progress_windows: self._progress_windows[tid].lift()
    def _show_res(self, title, content):
        w=tk.Toplevel(self); w.title(f"📄 {title[:30]}..."); w.geometry("700x500"); w.transient(self); w.grab_set()
        txt=scrolledtext.ScrolledText(w, font=("Consolas",10), wrap=tk.WORD); txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10); txt.insert(tk.END, content); txt.config(state=tk.DISABLED)
        ttk.Button(w, text="✓", command=w.destroy).pack(pady=5)
    def _clear_log(self): self._log_txt.config(state=tk.NORMAL); self._log_txt.delete("1.0",tk.END); self._log_txt.config(state=tk.DISABLED); self._log("🧹 Лог очищен", "info")
    def _log(self, msg, level="info"): self._log_q.put((msg,level))
    def _poll_logs(self):
        msgs=[]
        while True:
            try: msgs.append(self._log_q.get_nowait())
            except queue.Empty: break
        if msgs:
            self._log_txt.config(state=tk.NORMAL)
            for msg,lv in msgs: tag="err" if lv=="err" else "warn" if lv=="warn" else ""; self._log_txt.insert(tk.END, f"[{datetime.now():%H:%M:%S}] {msg}\n", tag)
            self._log_txt.see(tk.END); self._log_txt.config(state=tk.DISABLED)
        self.after(100, self._poll_logs)

def main():
    if sys.platform == "win32": os.environ["PYTHONIOENCODING"] = "utf-8"
    logger.info("="*60); logger.info("🚀 Agent GUI v12.0.0"); logger.info("="*60)
    try: import langchain; logger.info(f"✅ LangChain {langchain.__version__}")
    except ImportError: print("⚠️ pip install langchain langchain-openai pydantic requests"); return
    AgentGUI().mainloop()

if __name__ == "__main__":
    main()