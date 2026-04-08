"""
Валидация кода и путей для безопасного выполнения.

Модуль содержит функции для статического анализа кода,
валидации путей к файлам и проверки безопасности операций.
"""
import ast
import re
from pathlib import Path
from typing import Optional, Tuple, List, Set
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Результат валидации кода."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    imported_modules: Set[str]
    function_calls: Set[str]


def safe_path(path: str, base: Path) -> Optional[Path]:
    """
    Безопасное разрешение пути относительно базовой директории.
    
    Предотвращает выход за пределы базовой директории через:
    - Абсолютные пути
    - Символические ссылки
    - Паттерны типа ../../etc/passwd
    
    Args:
        path: Путь для проверки (может быть относительным или абсолютным)
        base: Базовая директория (песочница)
    
    Returns:
        Разрешённый путь или None если путь небезопасен
    
    Examples:
        >>> base = Path("/sandbox")
        >>> safe_path("file.txt", base)
        PosixPath('/sandbox/file.txt')
        >>> safe_path("../etc/passwd", base)
        None
    """
    try:
        # Нормализуем базовый путь
        base_resolved = base.resolve(strict=False)
        
        # Если путь абсолютный, проверяем что он внутри base
        path_obj = Path(path)
        if path_obj.is_absolute():
            resolved = path_obj.resolve(strict=False)
            try:
                resolved.relative_to(base_resolved)
                # Возвращаем строку с прямыми слешами для кроссплатформенности
                return resolved.as_posix()
            except ValueError:
                return None
        
        # Для относительных путей - резолвим относительно base
        resolved = (base_resolved / path_obj).resolve(strict=False)
        
        # Проверяем что результат внутри base
        try:
            resolved.relative_to(base_resolved)
            # Возвращаем строку с прямыми слешами для кроссплатформенности
            return resolved.as_posix()
        except ValueError:
            return None
            
    except (OSError, ValueError, RuntimeError) as e:
        # Логгируем ошибку но не пробрасываем
        import logging
        logging.getLogger(__name__).debug(f"Ошибка валидации пути: {e}")
        return None


def validate_imports(tree: ast.AST, allowed_modules: Set[str]) -> List[str]:
    """
    Проверить импорты в AST дереве на соответствие разрешённым модулям.
    
    Args:
        tree: AST дерево разобранного кода
        allowed_modules: Множество разрешённых модулей
    
    Returns:
        Список запрещённых импортов
    """
    forbidden = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split('.')[0]
                if module not in allowed_modules:
                    forbidden.append(f"Запрещённый импорт: {alias.name}")
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split('.')[0]
                if module not in allowed_modules:
                    forbidden.append(f"Запрещённый импорт: from {node.module} import ...")
            elif node.level == 0:
                # from X import Y без модуля - это from X import Y
                pass
    
    return forbidden


def check_dangerous_calls(tree: ast.AST) -> List[str]:
    """
    Проверить AST дерево на опасные вызовы функций.
    
    Args:
        tree: AST дерево разобранного кода
    
    Returns:
        Список найденных опасных вызовов
    """
    dangerous = []
    dangerous_funcs = {'eval', 'exec', 'compile', '__import__', 'open'}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Проверяем прямые вызовы
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_funcs:
                    dangerous.append(f"Опасный вызов: {node.func.id}()")
            
            # Проверяем вызовы атрибутов (например, __builtins__.__import__)
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_funcs:
                    dangerous.append(f"Опасный вызов: {node.func.attr}()")
                # Проверяем на доступ к запрещённым атрибутам
                if node.func.attr.startswith('__') and node.func.attr.endswith('__'):
                    dangerous.append(f"Доступ к dunder атрибуту: {node.func.attr}")
    
    return dangerous


def analyze_code(code: str, allowed_modules: Set[str]) -> ValidationResult:
    """
    Провести полный статический анализ кода.
    
    Args:
        code: Исходный код для анализа
        allowed_modules: Множество разрешённых модулей
    
    Returns:
        ValidationResult с результатами анализа
    """
    errors = []
    warnings = []
    imported_modules = set()
    function_calls = set()
    
    # Парсим код в AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(
            is_valid=False,
            errors=[f"Синтаксическая ошибка: {e}"],
            warnings=[],
            imported_modules=set(),
            function_calls=set()
        )
    
    # Извлекаем импорты
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
    
    # Проверяем импорты на разрешённость
    import_errors = validate_imports(tree, allowed_modules)
    errors.extend(import_errors)
    
    # Проверяем опасные вызовы
    dangerous = check_dangerous_calls(tree)
    errors.extend(dangerous)
    
    # Извлекаем все вызовы функций для логирования
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                function_calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                function_calls.add(node.func.attr)
    
    # Дополнительные предупреждения
    for node in ast.walk(tree):
        # Предупреждение о больших циклах
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call):
                if isinstance(node.iter.func, ast.Name):
                    if node.iter.func.id == 'range':
                        if node.iter.args and isinstance(node.iter.args[0], ast.Constant):
                            if isinstance(node.iter.args[0].value, int) and node.iter.args[0].value > 10000:
                                warnings.append(f"Большой диапазон в range(): {node.iter.args[0].value}")
        
        # Предупреждение о рекурсии
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id == node.name:
                        warnings.append(f"Возможная рекурсия в функции: {node.name}")
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        imported_modules=imported_modules,
        function_calls=function_calls
    )


def validate_url(url: str) -> str:
    """
    Валидировать и нормализовать URL.
    
    Args:
        url: URL для валидации
    
    Returns:
        Нормализованный URL с /v1 на конце
    
    Raises:
        ValueError: Если URL некорректен
    """
    url = url.strip().rstrip('/')
    
    # Добавляем схему если нет
    if not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    
    # Добавляем /v1 если нет
    if not url.endswith('/v1'):
        url = f'{url}/v1'
    
    # Базовая валидация формата
    pattern = r'^https?://[\w\-\.]+(:\d+)?(/.*)?$'
    if not re.match(pattern, url):
        raise ValueError(f"Некорректный URL: {url}")
    
    return url


def parse_json_list(text: str) -> list:
    """
    Распарсить текст как JSON список или CSV.
    
    Args:
        text: Текст для парсинга
    
    Returns:
        Список строк
    """
    if not isinstance(text, str) or not text.strip():
        return []
    
    try:
        # Пробуем распарсить как JSON
        if text.strip().startswith('['):
            result = __import__('json').loads(text)
            return result if isinstance(result, list) else [str(result)]
    except Exception:
        pass
    
    # Фолбэк: разбиваем по запятым
    return [x.strip() for x in text.split(',') if x.strip()]


def estimate_complexity(code: str) -> dict:
    """
    Оценить сложность кода для установки лимитов.
    
    Args:
        code: Исходный код
    
    Returns:
        Словарь с метриками сложности
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {'error': 'Syntax error', 'complexity': 0}
    
    metrics = {
        'lines': len(code.splitlines()),
        'functions': 0,
        'classes': 0,
        'loops': 0,
        'conditionals': 0,
        'imports': 0,
        'complexity': 0
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            metrics['functions'] += 1
            metrics['complexity'] += 1
        elif isinstance(node, ast.ClassDef):
            metrics['classes'] += 1
            metrics['complexity'] += 2
        elif isinstance(node, (ast.For, ast.While)):
            metrics['loops'] += 1
            metrics['complexity'] += 1
        elif isinstance(node, ast.If):
            metrics['conditionals'] += 1
            metrics['complexity'] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            metrics['imports'] += 1
    
    # Общая оценка сложности
    metrics['complexity'] += metrics['lines'] // 50
    
    return metrics
