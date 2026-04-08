"""
Кэширование импортов для повышения производительности.

Модуль содержит функции для кэширования часто используемых
модулей и результатов вычислений.
"""
import functools
from typing import Any, Dict, Optional, Callable, TypeVar
from collections import OrderedDict


# ─────────────────────────────────────────────────────────────────────────────
# Глобальный кэш импортов
# ─────────────────────────────────────────────────────────────────────────────
_import_cache: Dict[str, Any] = {}


def cached_import(module_name: str) -> Optional[Any]:
    """
    Получить модуль из кэша или импортировать и закэшировать.
    
    Args:
        module_name: Имя модуля для импорта
    
    Returns:
        Модуль или None если импорт не удался
    
    Examples:
        >>> np = cached_import('numpy')
        >>> np.array([1, 2, 3])
    """
    if module_name in _import_cache:
        return _import_cache[module_name]
    
    try:
        import importlib
        module = importlib.import_module(module_name)
        _import_cache[module_name] = module
        return module
    except ImportError as e:
        import logging
        logging.getLogger(__name__).debug(f"Не удалось импортировать {module_name}: {e}")
        return None


def clear_import_cache() -> None:
    """Очистить кэш импортов."""
    _import_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# LRU кэш с ограничением размера
# ─────────────────────────────────────────────────────────────────────────────
T = TypeVar('T')


class LRUCache:
    """
    LRU (Least Recently Used) кэш с ограничением размера.
    
    Автоматически удаляет наименее используемые элементы при переполнении.
    
    Attributes:
        maxsize: Максимальный размер кэша
    
    Examples:
        >>> cache = LRUCache(maxsize=100)
        >>> cache.get('key')
        >>> cache.put('key', 'value')
    """
    
    def __init__(self, maxsize: int = 128):
        """
        Инициализировать LRU кэш.
        
        Args:
            maxsize: Максимальное количество элементов в кэше
        """
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получить значение по ключу.
        
        Args:
            key: Ключ для поиска
        
        Returns:
            Значение или None если ключ не найден
        """
        if key not in self._cache:
            return None
        
        # Перемещаем в конец (самый новый)
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def put(self, key: str, value: Any) -> None:
        """
        Положить значение в кэш.
        
        Args:
            key: Ключ
            value: Значение
        """
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        
        # Удаляем самый старый элемент если переполнение
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        """
        Удалить ключ из кэша.
        
        Args:
            key: Ключ для удаления
        
        Returns:
            True если ключ был удалён
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        return key in self._cache


# ─────────────────────────────────────────────────────────────────────────────
# Декоратор для кэширования с LRU
# ─────────────────────────────────────────────────────────────────────────────
def lru_cache(maxsize: int = 128) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Декоратор для кэширования результатов функции с LRU стратегией.
    
    Альтернатива functools.lru_cache с возможностью управления размером.
    
    Args:
        maxsize: Максимальный размер кэша
    
    Returns:
        Декоратор
    
    Examples:
        @lru_cache(maxsize=100)
        def expensive_function(x, y):
            return x + y
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = LRUCache(maxsize=maxsize)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Создаём ключ из аргументов
            key = str((args, sorted(kwargs.items())))
            
            result = cache.get(key)
            if result is not None:
                return result
            
            result = func(*args, **kwargs)
            cache.put(key, result)
            return result
        
        # Добавляем методы для управления кэшем
        wrapper.cache_clear = cache.clear
        wrapper.cache_info = lambda: {'size': len(cache), 'maxsize': maxsize}
        
        return wrapper
    
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Кэш для результатов выполнения кода
# ─────────────────────────────────────────────────────────────────────────────
class ExecutionCache:
    """
    Кэш для результатов выполнения Python кода.
    
    Использует хэш кода как ключ для предотвращения повторного выполнения
    одинакового кода.
    
    Attributes:
        maxsize: Максимальный размер кэша
        ttl: Время жизни кэша в секундах (None = бесконечно)
    """
    
    def __init__(self, maxsize: int = 50, ttl: Optional[int] = None):
        """
        Инициализировать кэш выполнения.
        
        Args:
            maxsize: Максимальное количество записей
            ttl: Время жизни кэша в секундах
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
    
    def _compute_hash(self, code: str, context: Optional[dict] = None) -> str:
        """Вычислить хэш кода и контекста."""
        import hashlib
        
        data = code + str(context or {})
        return hashlib.md5(data.encode()).hexdigest()
    
    def _is_expired(self, key: str) -> bool:
        """Проверить истёк ли срок жизни кэша."""
        if self.ttl is None:
            return False
        
        import time
        timestamp = self._timestamps.get(key, 0)
        return (time.time() - timestamp) > self.ttl
    
    def get(self, code: str, context: Optional[dict] = None) -> Optional[Any]:
        """
        Получить результат из кэша.
        
        Args:
            code: Исходный код
            context: Контекст выполнения (переменные)
        
        Returns:
            Результат или None если не найдено
        """
        key = self._compute_hash(code, context)
        
        if key not in self._cache:
            return None
        
        if self._is_expired(key):
            self.delete(code, context)
            return None
        
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def put(self, code: str, result: Any, context: Optional[dict] = None) -> None:
        """
        Положить результат в кэш.
        
        Args:
            code: Исходный код
            result: Результат выполнения
            context: Контекст выполнения
        """
        import time
        
        key = self._compute_hash(code, context)
        
        if key in self._cache:
            self._cache.move_to_end(key)
        
        self._cache[key] = result
        self._timestamps[key] = time.time()
        
        # Удаляем старые записи
        while len(self._cache) > self.maxsize:
            old_key = next(iter(self._cache))
            del self._cache[old_key]
            if old_key in self._timestamps:
                del self._timestamps[old_key]
    
    def delete(self, code: str, context: Optional[dict] = None) -> bool:
        """Удалить запись из кэша."""
        key = self._compute_hash(code, context)
        if key in self._cache:
            del self._cache[key]
            if key in self._timestamps:
                del self._timestamps[key]
            return True
        return False
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
        self._timestamps.clear()
    
    def size(self) -> int:
        """Вернуть текущий размер кэша."""
        return len(self._cache)
