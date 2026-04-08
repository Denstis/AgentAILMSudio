"""
Утилиты логирования для LM Agent.

Модуль содержит настроенные обработчики логов,
форматтеры и функции для централизованного логирования.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Цветной форматтер для консоли
# ─────────────────────────────────────────────────────────────────────────────
class ColoredFormatter(logging.Formatter):
    """
    Форматтер для цветного вывода логов в консоль.
    
    Использует ANSI escape-коды для раскраски уровней логирования.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Purple
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматировать запись лога с цветом."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


# ─────────────────────────────────────────────────────────────────────────────
# JSON форматтер для структурированного логирования
# ─────────────────────────────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """
    Форматтер для вывода логов в формате JSON.
    
    Полезно для интеграции с системами мониторинга и анализа.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматировать запись как JSON."""
        import json
        
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Добавляем exception если есть
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Добавляем extra поля
        for key in ['threadName', 'process', 'filename']:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        
        return json.dumps(log_data, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Глобальный обработчик исключений
# ─────────────────────────────────────────────────────────────────────────────
def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Глобальный обработчик необработанных исключений.
    
    Логгирует критические ошибки перед завершением программы.
    
    Args:
        exc_type: Тип исключения
        exc_value: Значение исключения
        exc_traceback: Трассировка стека
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Игнорируем Ctrl+C
        return
    
    logger = logging.getLogger(__name__)
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def setup_logging(
    log_dir: Optional[Path] = None,
    log_level: str = 'DEBUG',
    console_level: str = 'INFO',
    enable_json: bool = False,
    enable_colors: bool = True
) -> logging.Logger:
    """
    Настроить систему логирования.
    
    Args:
        log_dir: Директория для файлов логов (по умолчанию ~/.lm_agent)
        log_level: Уровень логирования для файла
        console_level: Уровень логирования для консоли
        enable_json: Включить JSON форматирование
        enable_colors: Включить цвета в консоли
    
    Returns:
        Настроенный логгер
    """
    # Создаём директорию для логов
    if log_dir is None:
        log_dir = Path.home() / ".lm_agent"
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # Имя файла с датой
    log_file = log_dir / f"agent_{datetime.now():%Y%m%d}.log"
    
    # Получаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем старые обработчики
    root_logger.handlers.clear()
    
    # Файловый обработчик (всегда DEBUG)
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    
    if enable_colors:
        console_formatter = ColoredFormatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Опционально: JSON обработчик для отдельного файла
    if enable_json:
        json_file = log_dir / f"agent_{datetime.now():%Y%m%d}.json.log"
        json_handler = logging.FileHandler(json_file, encoding='utf-8', mode='a')
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    # Устанавливаем глобальный обработчик исключений
    sys.excepthook = handle_exception
    
    # Для потоков
    import threading
    threading.excepthook = lambda args: handle_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    )
    
    # Возвращаем логгер для этого модуля
    return logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Декоратор для логирования вызовов функций
# ─────────────────────────────────────────────────────────────────────────────
def log_calls(logger: Optional[logging.Logger] = None):
    """
    Декоратор для логирования вызовов функций.
    
    Args:
        logger: Логгер для использования (по умолчанию root logger)
    
    Returns:
        Декоратор
    """
    if logger is None:
        logger = logging.getLogger()
    
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"Вызов {func.__name__} с аргументами: args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Возврат {func.__name__}: {result}")
                return result
            except Exception as e:
                logger.error(f"Ошибка в {func.__name__}: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Контекстный менеджер для измерения времени
# ─────────────────────────────────────────────────────────────────────────────
class TimerContext:
    """
    Контекстный менеджер для измерения времени выполнения блока кода.
    
    Examples:
        >>> with TimerContext("Загрузка данных", logger):
        ...     data = load_data()
    """
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None, level: str = 'debug'):
        """
        Инициализировать таймер.
        
        Args:
            operation: Название операции для логирования
            logger: Логгер для использования
            level: Уровень логирования ('debug', 'info', etc.)
        """
        self.operation = operation
        self.logger = logger or logging.getLogger()
        self.level = getattr(logging, level.upper())
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        msg = f"Начало: {self.operation}"
        self.logger.log(self.level, msg)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if exc_type is None:
            msg = f"Завершено: {self.operation} за {elapsed:.3f}с"
            self.logger.log(self.level, msg)
        else:
            msg = f"Ошибка: {self.operation} после {elapsed:.3f}с - {exc_val}"
            self.logger.error(msg)
        return False  # Не подавляем исключения
