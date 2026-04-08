"""
Code Quality Tools for LM Agent.

Provides tools for linting, formatting, and testing code.
"""

import subprocess
import tempfile
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import BaseTool, ToolResult, ToolDefinition


class CodeLintingTool(BaseTool):
    """
    Инструмент для линтинга кода Python.
    
    Использует ruff если доступен, иначе pylint или flake8.
    """
    
    def __init__(self):
        super().__init__(
            name="code_lint",
            description="Проверка кода на ошибки и стиль (ruff/pylint/flake8)"
        )
        self._linter = self._detect_linter()
    
    def _detect_linter(self) -> Optional[str]:
        """Определить доступный линтер."""
        linters = ['ruff', 'pylint', 'flake8']
        for linter in linters:
            try:
                result = subprocess.run(
                    [linter, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return linter
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description + f" (using {self._linter or 'none'})",
            parameters={
                "code": {"type": "string", "description": "Код для проверки"},
                "file_path": {"type": "string", "description": "Путь к файлу (опционально)"},
                "fix": {"type": "boolean", "description": "Исправить автоматически (только ruff)"}
            },
            returns="str"
        )
    
    def execute(self, code: str, file_path: Optional[str] = None,
                fix: bool = False) -> ToolResult:
        """Выполнить линтинг кода."""
        
        if not self._linter:
            return ToolResult(
                success=False,
                output="",
                error="No linter available. Install with: pip install ruff"
            )
        
        # Создание временного файла
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            if self._linter == 'ruff':
                return self._run_ruff(temp_path, fix)
            elif self._linter == 'pylint':
                return self._run_pylint(temp_path)
            elif self._linter == 'flake8':
                return self._run_flake8(temp_path)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Unknown linter"
                )
        finally:
            # Очистка временного файла
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _run_ruff(self, file_path: str, fix: bool) -> ToolResult:
        """Запустить ruff."""
        cmd = ['ruff', 'check', file_path]
        
        if fix:
            cmd = ['ruff', 'check', '--fix', file_path]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            # Если fix режим и были исправления
            if fix and result.returncode == 0:
                with open(file_path, 'r', encoding='utf-8') as f:
                    fixed_code = f.read()
                return ToolResult(
                    success=True,
                    output=f"Fixed:\n{fixed_code}",
                    metadata={"fixed_code": fixed_code}
                )
            
            return ToolResult(
                success=result.returncode == 0,
                output=output if output else "No issues found",
                error=output if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Linting timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _run_pylint(self, file_path: str) -> ToolResult:
        """Запустить pylint."""
        cmd = ['pylint', file_path, '--output-format=text']
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                error=result.stdout if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Linting timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _run_flake8(self, file_path: str) -> ToolResult:
        """Запустить flake8."""
        cmd = ['flake8', file_path, '--count', '--show-source', '--statistics']
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            return ToolResult(
                success=result.returncode == 0,
                output=output if output else "No issues found",
                error=output if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Linting timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class CodeFormattingTool(BaseTool):
    """
    Инструмент для форматирования кода Python.
    
    Использует black если доступен, иначе autopep8.
    """
    
    def __init__(self):
        super().__init__(
            name="code_format",
            description="Форматирование кода Python (black/autopep8)"
        )
        self._formatter = self._detect_formatter()
    
    def _detect_formatter(self) -> Optional[str]:
        """Определить доступный форматтер."""
        formatters = ['black', 'autopep8']
        for formatter in formatters:
            try:
                result = subprocess.run(
                    [formatter, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return formatter
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description + f" (using {self._formatter or 'none'})",
            parameters={
                "code": {"type": "string", "description": "Код для форматирования"},
                "line_length": {"type": "integer", "description": "Длина строки (по умолчанию 88)"}
            },
            returns="str"
        )
    
    def execute(self, code: str, line_length: int = 88) -> ToolResult:
        """Отформатировать код."""
        
        if not self._formatter:
            return ToolResult(
                success=False,
                output="",
                error="No formatter available. Install with: pip install black"
            )
        
        # Создание временного файла
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            if self._formatter == 'black':
                return self._run_black(temp_path, line_length)
            elif self._formatter == 'autopep8':
                return self._run_autopep8(temp_path, line_length)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Unknown formatter"
                )
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _run_black(self, file_path: str, line_length: int) -> ToolResult:
        """Запустить black."""
        cmd = [
            'black', 
            file_path,
            '--line-length', str(line_length),
            '--quiet'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Чтение отформатированного кода
            with open(file_path, 'r', encoding='utf-8') as f:
                formatted_code = f.read()
            
            return ToolResult(
                success=True,
                output=formatted_code,
                metadata={"formatted_code": formatted_code}
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Formatting timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _run_autopep8(self, file_path: str, line_length: int) -> ToolResult:
        """Запустить autopep8."""
        cmd = [
            'autopep8',
            file_path,
            '--max-line-length', str(line_length),
            '--in-place',
            '--aggressive',
            '--aggressive'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Чтение отформатированного кода
            with open(file_path, 'r', encoding='utf-8') as f:
                formatted_code = f.read()
            
            return ToolResult(
                success=True,
                output=formatted_code,
                metadata={"formatted_code": formatted_code}
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Formatting timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class UnitTestGeneratorTool(BaseTool):
    """
    Инструмент для генерации и запуска unit тестов.
    
    Создает тесты для предоставленного кода и запускает их в песочнице.
    """
    
    def __init__(self):
        super().__init__(
            name="unit_test",
            description="Генерация и запуск unit тестов для Python кода"
        )
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "code": {"type": "string", "description": "Код для тестирования"},
                "test_template": {"type": "string", "description": "Шаблон теста (pytest/unittest)"},
                "run_tests": {"type": "boolean", "description": "Запустить тесты после генерации"}
            },
            returns="str"
        )
    
    def execute(self, code: str, test_template: str = "pytest",
                run_tests: bool = True) -> ToolResult:
        """Сгенерировать и запустить тесты."""
        
        try:
            # Генерация базового шаблона теста
            test_code = self._generate_test_template(code, test_template)
            
            if not test_code:
                return ToolResult(
                    success=False,
                    output="",
                    error="Failed to generate test template"
                )
            
            result_info = {
                "test_code": test_code,
                "template": test_template
            }
            
            if run_tests:
                test_result = self._run_tests(test_code, code)
                result_info["test_result"] = test_result
            
            import json
            return ToolResult(
                success=True,
                output=json.dumps(result_info, ensure_ascii=False, indent=2),
                metadata=result_info
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _generate_test_template(self, code: str, template_type: str) -> str:
        """Сгенерировать шаблон теста."""
        
        # Простой анализ кода для извлечения имен функций/классов
        import ast
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ""
        
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
        
        if template_type == "pytest":
            return self._generate_pytest_template(functions, classes, code)
        else:
            return self._generate_unittest_template(functions, classes, code)
    
    def _generate_pytest_template(self, functions: List[str], 
                                  classes: List[str], 
                                  original_code: str) -> str:
        """Сгенерировать pytest шаблон."""
        test_lines = [
            "# Auto-generated tests",
            "import pytest",
            "",
            "# Import the code to test",
            "exec('''" + original_code.replace("'''", "\\'\\'\\'") + "''')",
            ""
        ]
        
        for func in functions:
            test_lines.extend([
                f"def test_{func}():",
                f"    # TODO: Add test cases for {func}",
                f"    # Example:",
                f"    # result = {func}(...)",
                f"    # assert result is not None",
                f"    pass",
                ""
            ])
        
        for cls in classes:
            test_lines.extend([
                f"class Test{cls}:",
                f"    def test_{cls.lower()}_initialization(self):",
                f"        # TODO: Test {cls} initialization",
                f"        # instance = {cls}(...)",
                f"        # assert instance is not None",
                f"        pass",
                ""
            ])
        
        return "\n".join(test_lines)
    
    def _generate_unittest_template(self, functions: List[str],
                                    classes: List[str],
                                    original_code: str) -> str:
        """Сгенерировать unittest шаблон."""
        test_lines = [
            "# Auto-generated tests",
            "import unittest",
            "",
            "# Import the code to test",
            "exec('''" + original_code.replace("'''", "\\'\\'\\'") + "''')",
            ""
        ]
        
        for func in functions:
            test_lines.extend([
                f"class Test{func.title()}(unittest.TestCase):",
                f"    def test_{func}(self):",
                f"        # TODO: Add test cases for {func}",
                f"        pass",
                ""
            ])
        
        for cls in classes:
            test_lines.extend([
                f"class Test{cls}(unittest.TestCase):",
                f"    def test_{cls.lower()}_initialization(self):",
                f"        # TODO: Test {cls} initialization",
                f"        pass",
                ""
            ])
        
        test_lines.append("if __name__ == '__main__':")
        test_lines.append("    unittest.main()")
        
        return "\n".join(test_lines)
    
    def _run_tests(self, test_code: str, original_code: str) -> Dict[str, Any]:
        """Запустить тесты."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_code.py")
            
            # Запись тестового файла
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_code)
            
            # Запуск pytest
            try:
                result = subprocess.run(
                    ['python', '-m', 'pytest', test_file, '-v'],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=tmpdir
                )
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                    "returncode": result.returncode
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "output": "Test execution timeout",
                    "returncode": -1
                }
            except Exception as e:
                return {
                    "success": False,
                    "output": str(e),
                    "returncode": -1
                }
