"""
Базовые тесты для модулей LM Agent.

Модуль содержит юнит-тесты для проверки корректности
работы основных компонентов системы.
"""
import pytest
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Тесты валидации путей
# ─────────────────────────────────────────────────────────────────────────────
class TestSafePath:
    """Тесты функции safe_path."""
    
    def test_safe_relative_path(self):
        """Проверка безопасного относительного пути."""
        from lm_agent.sandbox.validator import safe_path
        
        base = Path("/sandbox")
        result = safe_path("file.txt", base)
        
        assert result is not None
        assert str(result) == "/sandbox/file.txt"
    
    def test_unsafe_parent_path(self):
        """Проверка блокировки выхода за пределы базовой директории."""
        from lm_agent.sandbox.validator import safe_path
        
        base = Path("/sandbox")
        result = safe_path("../etc/passwd", base)
        
        assert result is None
    
    def test_absolute_path_inside_base(self):
        """Проверка абсолютного пути внутри базы."""
        from lm_agent.sandbox.validator import safe_path
        
        base = Path("/sandbox")
        result = safe_path("/sandbox/subdir/file.txt", base)
        
        assert result is not None
        assert str(result) == "/sandbox/subdir/file.txt"
    
    def test_absolute_path_outside_base(self):
        """Проверка блокировки абсолютного пути вне базы."""
        from lm_agent.sandbox.validator import safe_path
        
        base = Path("/sandbox")
        result = safe_path("/etc/passwd", base)
        
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Тесты анализа кода
# ─────────────────────────────────────────────────────────────────────────────
class TestCodeAnalysis:
    """Тесты статического анализа кода."""
    
    def test_valid_code(self):
        """Проверка валидного кода."""
        from lm_agent.sandbox.validator import analyze_code
        
        code = """
def hello():
    return "Hello, World!"

result = hello()
print(result)
"""
        allowed = {'builtins', 'typing'}
        result = analyze_code(code, allowed)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_forbidden_import(self):
        """Проверка блокировки запрещённого импорта."""
        from lm_agent.sandbox.validator import analyze_code
        
        code = "import os\nprint(os.system('ls'))"
        allowed = {'builtins'}  # os не разрешён
        result = analyze_code(code, allowed)
        
        assert result.is_valid is False
        assert any("Запрещённый импорт" in err for err in result.errors)
    
    def test_dangerous_call(self):
        """Проверка блокировки опасных вызовов."""
        from lm_agent.sandbox.validator import analyze_code
        
        code = "eval('1+1')"
        allowed = {'builtins'}
        result = analyze_code(code, allowed)
        
        assert result.is_valid is False
        assert any("Опасный вызов" in err for err in result.errors)
    
    def test_extract_imports(self):
        """Проверка извлечения импортов."""
        from lm_agent.sandbox.validator import analyze_code
        
        code = """
import math
from collections import defaultdict
import json as j
"""
        allowed = {'math', 'collections', 'json'}
        result = analyze_code(code, allowed)
        
        assert 'math' in result.imported_modules
        assert 'collections' in result.imported_modules
        assert 'json' in result.imported_modules


# ─────────────────────────────────────────────────────────────────────────────
# Тесты конфигурации песочницы
# ─────────────────────────────────────────────────────────────────────────────
class TestSandboxConfig:
    """Тесты конфигурации песочницы."""
    
    def test_default_config(self):
        """Проверка конфигурации по умолчанию."""
        from lm_agent.core.config import SandboxAdvancedConfig
        
        config = SandboxAdvancedConfig()
        
        assert config.enable_internet is False
        assert config.enable_pip is True
        assert config.max_pip_timeout == 120
    
    def test_config_validation(self):
        """Проверка валидации конфигурации."""
        from lm_agent.core.config import SandboxAdvancedConfig
        
        config = SandboxAdvancedConfig(max_pip_timeout=5)  # Слишком мало
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("max_pip_timeout" in err for err in errors)
    
    def test_config_to_dict(self):
        """Проверка преобразования в словарь."""
        from lm_agent.core.config import SandboxAdvancedConfig
        
        config = SandboxAdvancedConfig(enable_math=False)
        d = config.to_dict()
        
        assert isinstance(d, dict)
        assert d['enable_math'] is False
    
    def test_config_from_dict(self):
        """Проверка создания из словаря."""
        from lm_agent.core.config import SandboxAdvancedConfig
        
        d = {'enable_internet': True, 'enable_pip': False}
        config = SandboxAdvancedConfig.from_dict(d)
        
        assert config.enable_internet is True
        assert config.enable_pip is False


# ─────────────────────────────────────────────────────────────────────────────
# Тесты модульных групп
# ─────────────────────────────────────────────────────────────────────────────
class TestModuleGroups:
    """Тесты групп модулей."""
    
    def test_get_allowed_modules_basic(self):
        """Проверка получения базовых модулей."""
        from lm_agent.sandbox.modules import get_allowed_modules
        
        config = {}
        allowed = get_allowed_modules(config)
        
        assert 'builtins' in allowed
        assert 'typing' in allowed
    
    def test_get_allowed_modules_with_flags(self):
        """Проверка получения модулей с флагами."""
        from lm_agent.sandbox.modules import get_allowed_modules
        
        config = {'enable_math': True, 'enable_science': True}
        allowed = get_allowed_modules(config)
        
        assert 'math' in allowed
        assert 'numpy' in allowed
    
    def test_is_module_allowed(self):
        """Проверка проверки разрешённости модуля."""
        from lm_agent.sandbox.modules import is_module_allowed
        
        allowed = frozenset({'math', 'json', 'tkinter'})
        
        assert is_module_allowed('math', allowed) is True
        assert is_module_allowed('os', allowed) is False
        assert is_module_allowed('tkinter.ttk', allowed) is True


# ─────────────────────────────────────────────────────────────────────────────
# Тесты кэширования
# ─────────────────────────────────────────────────────────────────────────────
class TestCache:
    """Тесты систем кэширования."""
    
    def test_lru_cache_basic(self):
        """Проверка базовой работы LRU кэша."""
        from lm_agent.utils.cache import LRUCache
        
        cache = LRUCache(maxsize=3)
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)
        
        assert cache.get('a') == 1
        assert cache.get('b') == 2
    
    def test_lru_cache_eviction(self):
        """Проверка вытеснения старых элементов."""
        from lm_agent.utils.cache import LRUCache
        
        cache = LRUCache(maxsize=2)
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)  # Должно вытеснить 'a'
        
        assert cache.get('a') is None
        assert cache.get('b') == 2
        assert cache.get('c') == 3
    
    def test_cached_import(self):
        """Проверка кэширования импортов."""
        from lm_agent.utils.cache import cached_import, clear_import_cache
        
        clear_import_cache()
        module = cached_import('json')
        
        assert module is not None
        assert module.__name__ == 'json'
        
        # Второй раз должно вернуть из кэша
        module2 = cached_import('json')
        assert module2 is module


# ─────────────────────────────────────────────────────────────────────────────
# Тесты URL валидации
# ─────────────────────────────────────────────────────────────────────────────
class TestURLValidation:
    """Тесты валидации URL."""
    
    def test_url_normalization(self):
        """Проверка нормализации URL."""
        from lm_agent.sandbox.validator import validate_url
        
        result = validate_url("http://localhost:1234")
        assert result == "http://localhost:1234/v1"
    
    def test_url_with_scheme(self):
        """Проверка URL со схемой."""
        from lm_agent.sandbox.validator import validate_url
        
        result = validate_url("https://api.example.com/v1")
        assert result == "https://api.example.com/v1"
    
    def test_url_without_scheme(self):
        """Проверка URL без схемы."""
        from lm_agent.sandbox.validator import validate_url
        
        result = validate_url("localhost:1234")
        assert result.startswith("http://")


# ─────────────────────────────────────────────────────────────────────────────
# Запуск тестов
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
