"""
Типы данных и конфигурация для LM Agent.

Модуль содержит определения типов данных, конфигурационных классов
и констант, используемых во всём приложении.
"""
from __future__ import annotations
from typing import Any, Optional, TypedDict, List, Dict
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Типы данных для прогресса
# ─────────────────────────────────────────────────────────────────────────────
class ProgressEntry(TypedDict, total=False):
    """Запись лога прогресса выполнения задачи."""
    timestamp: str
    level: str
    message: str
    details: Optional[str]
    iteration: Optional[int]
    tool_call: Optional[dict]
    ask_user: Optional[dict]


# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация модели
# ─────────────────────────────────────────────────────────────────────────────
class ModelCaps(TypedDict, total=False):
    """Возможности модели."""
    vision: bool
    tool_use: bool
    reasoning: bool
    json_mode: bool


class ModelInfo(TypedDict):
    """Информация о модели."""
    id: str
    object: str
    created: int
    owned_by: str
    capabilities: ModelCaps
    context_window: int
    max_tokens: int


# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация агента
# ─────────────────────────────────────────────────────────────────────────────
class AgentConfig(TypedDict, total=False):
    """Конфигурация агента."""
    model_name: str
    base_url: str
    temperature: float
    max_tokens: int
    top_p: float
    frequency_penalty: float
    max_iterations: int
    timeout: int
    sandbox_enabled: bool
    log_level: str


# ─────────────────────────────────────────────────────────────────────────────
# Данные задачи
# ─────────────────────────────────────────────────────────────────────────────
class TaskData(TypedDict):
    """Данные задачи для выполнения."""
    id: str
    description: str
    priority: int
    status: str
    result: str
    error: str
    created: str
    progress: str


# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация песочницы (dataclass для удобства)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SandboxAdvancedConfig:
    """
    Расширенная конфигурация песочницы для безопасного выполнения кода.
    
    Attributes:
        enable_internet: Разрешить доступ к интернету
        enable_system_cmds: Разрешить системные команды
        enable_pip: Разрешить установку пакетов через pip
        enable_git: Разрешить Git операции
        enable_venv: Разрешить управление виртуальными окружениями
        enable_all_modules: Разрешить все модули (опасно!)
        enable_math: Разрешить математические модули
        enable_bool: Разрешить встроенные функции
        enable_network: Разрешить сетевые операции
        enable_gui: Разрешить GUI библиотеки
        enable_science: Разрешить научные библиотеки
        enable_testing: Разрешить тестовые фреймворки
        custom_allowed_modules: Пользовательский список разрешённых модулей
        custom_forbidden_patterns: Пользовательские запрещённые паттерны
        pip_index_url: URL индекс для pip
        venv_dir: Директория для виртуальных окружений
        max_pip_timeout: Максимальное время установки пакета (сек)
        max_git_timeout: Максимальное время Git операции (сек)
        allow_local_files: Разрешить доступ к локальным файлам
    """
    enable_internet: bool = False
    enable_system_cmds: bool = False
    enable_pip: bool = True
    enable_git: bool = False
    enable_venv: bool = False
    enable_all_modules: bool = False
    enable_math: bool = True
    enable_bool: bool = True
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

    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {k: v for k, v in self.__dict__.items()}
    
    @classmethod
    def from_dict(cls, d: dict) -> "SandboxAdvancedConfig":
        """Создать из словаря."""
        return cls(**{k: d.get(k, getattr(cls, k, None)) for k in cls.__dataclass_fields__.keys()})
    
    def validate(self) -> List[str]:
        """
        Валидировать конфигурацию.
        
        Returns:
            Список ошибок валидации (пустой если всё корректно)
        """
        errors = []
        if self.enable_all_modules and not self.enable_internet:
            errors.append("⚠️ enable_all_modules включает опасные модули")
        if self.max_pip_timeout < 10 or self.max_pip_timeout > 600:
            errors.append("max_pip_timeout должен быть между 10 и 600 секундами")
        if self.max_git_timeout < 10 or self.max_git_timeout > 1800:
            errors.append("max_git_timeout должен быть между 10 и 1800 секундами")
        return errors
