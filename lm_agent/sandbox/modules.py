"""
Группы модулей и правила безопасности для песочницы.

Модуль содержит определения разрешённых групп модулей Python,
запрещённых паттернов и правил для безопасного выполнения кода.
"""
import re
from typing import Set, FrozenSet, Pattern


# ─────────────────────────────────────────────────────────────────────────────
# Группы модулей (расширенный список)
# ─────────────────────────────────────────────────────────────────────────────
MODULE_GROUPS = {
    'core': frozenset({
        'builtins', '__future__', 'typing', 'typing_extensions', 'abc',
        'collections', 'itertools', 'functools', 'operator', 'copy',
        'weakref', 'types', 'contextlib', 'contextvars', 'dataclasses', 'enum'
    }),
    'math': frozenset({
        'math', 'cmath', 'decimal', 'fractions', 'random', 'statistics', 'numbers'
    }),
    'datetime': frozenset({'datetime', 'time', 'calendar', 'zoneinfo'}),
    'text': frozenset({
        're', 'string', 'textwrap', 'unicodedata', 'difflib',
        'struct', 'codecs'
    }),
    'data': frozenset({'json', 'csv', 'pickle', 'shelve', 'pprint'}),
    'files': frozenset({
        'os', 'sys', 'io', 'pathlib', 'tempfile', 'shutil',
        'glob', 'fnmatch', 'linecache', 'stat'
    }),
    'debug': frozenset({
        'traceback', 'warnings', 'logging', 'inspect', 'dis',
        'ast', 'tokenize', 'token', 'keyword', 'pdb'
    }),
    'concurrency': frozenset({
        'threading', 'queue', 'concurrent', 'concurrent.futures',
        'asyncio', 'selectors'
    }),
    'utils': frozenset({
        'uuid', 'hashlib', 'hmac', 'secrets', 'base64', 'binascii',
        'quopri', 'uu', 'argparse', 'configparser'
    }),
    'network': frozenset({
        'socket', 'urllib', 'urllib.parse', 'urllib.request',
        'http', 'http.client', 'ssl', 'email', 'requests', 'aiohttp'
    }),
    'gui': frozenset({
        'tkinter', 'tkinter.ttk', 'PyQt5', 'PyQt5.QtCore',
        'PyQt5.QtWidgets', 'PySide6', 'pygame', 'kivy'
    }),
    'science': frozenset({
        'numpy', 'pandas', 'matplotlib', 'matplotlib.pyplot',
        'scipy', 'plotly', 'seaborn', 'sympy', 'sklearn'
    }),
    'testing': frozenset({'unittest', 'doctest', 'pytest', 'mock'}),
}

# ─────────────────────────────────────────────────────────────────────────────
# Запрещённые паттерны (всегда)
# ─────────────────────────────────────────────────────────────────────────────
ALWAYS_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r'__import__',
    r'importlib',
    r'exec\s*\(',
    r'eval\s*\(',
    r'compile\s*\(',
    r'__class__',
    r'__mro__',
    r'__getattribute__',
    r'__setattr__',
    r'__builtins__',
    r'__globals__',
    r'__code__',
    r'__subclasses__',
    r'__base__',
    r'__dir__',
    r'__format__',
    r'__reduce__',
    r'__reduce_ex__',
)

# Системные модули (опасные)
SYSTEM_MODULE_PATTERNS: tuple[str, ...] = (
    r'os\.system',
    r'subprocess',
    r'popen',
    r'spawn',
    r'pty',
    r'ctypes',
    r'curses',
    r'msvcrt',
    r'winreg',
)

# Запрещённые атрибуты
FORBIDDEN_ATTRS: FrozenSet[str] = frozenset({
    '__class__', '__mro__', '__subclasses__', '__globals__',
    '__builtins__', '__import__', 'eval', 'exec', 'compile',
    '__code__', '__closure__', '__func__', '__self__'
})


# ─────────────────────────────────────────────────────────────────────────────
# Компилированные regex паттерны для производительности
# ─────────────────────────────────────────────────────────────────────────────
def compile_patterns(patterns: tuple[str, ...]) -> Pattern:
    """Компилировать список паттернов в один regex."""
    return re.compile('|'.join(patterns), re.IGNORECASE)


FORBIDDEN_PATTERN: Pattern = compile_patterns(ALWAYS_FORBIDDEN_PATTERNS)
SYSTEM_PATTERN: Pattern = compile_patterns(SYSTEM_MODULE_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# Функции для работы с модулями
# ─────────────────────────────────────────────────────────────────────────────
def get_allowed_modules(config_flags: dict) -> FrozenSet[str]:
    """
    Получить набор разрешённых модулей на основе конфигурации.
    
    Args:
        config_flags: Словарь флагов конфигурации (enable_math, enable_science, etc.)
    
    Returns:
        Замороженное множество имён разрешённых модулей
    """
    if config_flags.get('enable_all_modules', False):
        # Возвращаем все модули из всех групп
        all_modules = set()
        for group in MODULE_GROUPS.values():
            all_modules.update(group)
        return frozenset(all_modules)
    
    # Базовый набор - всегда разрешён
    allowed = set(MODULE_GROUPS['core'])
    
    # Добавляем группы по флагам
    if config_flags.get('enable_math', True):
        allowed.update(MODULE_GROUPS['math'])
    
    allowed.update(MODULE_GROUPS['datetime'])
    allowed.update(MODULE_GROUPS['text'])
    
    if config_flags.get('enable_bool', True):  # data modules
        allowed.update(MODULE_GROUPS['data'])
    
    if config_flags.get('allow_local_files', True):
        allowed.update(MODULE_GROUPS['files'])
    
    allowed.update(MODULE_GROUPS['debug'])
    allowed.update(MODULE_GROUPS['concurrency'])
    allowed.update(MODULE_GROUPS['utils'])
    
    if config_flags.get('enable_network', False) or config_flags.get('enable_internet', False):
        allowed.update(MODULE_GROUPS['network'])
    
    if config_flags.get('enable_gui', False):
        allowed.update(MODULE_GROUPS['gui'])
    
    if config_flags.get('enable_science', True):
        allowed.update(MODULE_GROUPS['science'])
    
    if config_flags.get('enable_testing', True):
        allowed.update(MODULE_GROUPS['testing'])
    
    # Добавляем пользовательские модули
    custom = config_flags.get('custom_allowed_modules', '')
    if custom:
        custom_list = [m.strip() for m in custom.split(',') if m.strip()]
        allowed.update(custom_list)
    
    return frozenset(allowed)


def is_module_allowed(module_name: str, allowed_modules: FrozenSet[str]) -> bool:
    """
    Проверить, разрешён ли модуль.
    
    Args:
        module_name: Имя модуля для проверки
        allowed_modules: Множество разрешённых модулей
    
    Returns:
        True если модуль разрешён
    """
    # Проверяем точное совпадение
    if module_name in allowed_modules:
        return True
    
    # Проверяем родительский модуль (например, tkinter.ttk -> tkinter)
    base_module = module_name.split('.')[0]
    return base_module in allowed_modules


def contains_forbidden_pattern(code: str) -> tuple[bool, list[str]]:
    """
    Проверить код на наличие запрещённых паттернов.
    
    Args:
        code: Исходный код для проверки
    
    Returns:
        Кортеж (есть_запрещённое, список_найденных_паттернов)
    """
    found = []
    
    # Проверяем основные запрещённые паттерны
    match = FORBIDDEN_PATTERN.search(code)
    if match:
        found.append(f"Запрещённый паттерн: {match.group()}")
    
    # Проверяем системные паттерны
    match = SYSTEM_PATTERN.search(code)
    if match:
        found.append(f"Системный вызов: {match.group()}")
    
    return len(found) > 0, found


def get_safe_builtins(allowed_modules: FrozenSet[str]) -> dict:
    """
    Получить безопасный набор builtins.
    
    Args:
        allowed_modules: Множество разрешённых модулей
    
    Returns:
        Словарь безопасных builtins
    """
    import builtins
    
    # Базовые безопасные builtins
    safe_builtins = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytes',
        'chr', 'complex', 'dict', 'dir', 'divmod', 'enumerate',
        'filter', 'float', 'format', 'frozenset', 'getattr',
        'hasattr', 'hash', 'hex', 'id', 'int', 'isinstance',
        'issubclass', 'iter', 'len', 'list', 'map', 'max',
        'min', 'next', 'object', 'oct', 'ord', 'pow', 'print',
        'range', 'repr', 'reversed', 'round', 'set', 'slice',
        'sorted', 'str', 'sum', 'super', 'tuple', 'type',
        'zip', '__build_class__', '__name__', 'True', 'False', 'None'
    }
    
    source = vars(builtins)
    return {k: v for k, v in source.items() if k in safe_builtins}
