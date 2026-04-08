"""
File System Tools for LM Agent.

Provides advanced file system operations including search, read, write, and archive support.
"""

import os
import glob
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .base import BaseTool, ToolResult, ToolDefinition


@dataclass
class FileSearchConfig:
    """Конфигурация для поиска файлов."""
    pattern: str
    recursive: bool = True
    max_results: int = 100
    content_search: Optional[str] = None
    file_types: Optional[List[str]] = None


class FileSearchTool(BaseTool):
    """Инструмент для поиска файлов по маске и содержимому."""
    
    def __init__(self, base_path: str = "."):
        super().__init__(
            name="file_search",
            description="Поиск файлов по маске имени и/или содержимому. "
                       "Поддерживает glob-паттерны и поиск текста внутри файлов."
        )
        self.base_path = Path(base_path).resolve()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "pattern": {
                    "type": "string",
                    "description": "Glob-паттерн для поиска (например, '*.py', '**/*.txt')"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Искать рекурсивно в поддиректориях",
                    "default": True
                },
                "content_search": {
                    "type": "string",
                    "description": "Текст для поиска внутри файлов (опционально)",
                    "default": None
                },
                "max_results": {
                    "type": "integer",
                    "description": "Максимальное количество результатов",
                    "default": 100
                }
            },
            returns="List[Dict[str, Any]]"
        )
    
    def execute(
        self,
        pattern: str,
        recursive: bool = True,
        content_search: Optional[str] = None,
        max_results: int = 100
    ) -> ToolResult:
        """
        Выполнить поиск файлов.
        
        Args:
            pattern: Glob-паттерн для поиска
            recursive: Искать рекурсивно
            content_search: Текст для поиска внутри файлов
            max_results: Максимум результатов
            
        Returns:
            ToolResult со списком найденных файлов
        """
        try:
            # Безопасная проверка пути
            if ".." in pattern:
                raise ValueError("Path traversal not allowed")
            
            # Формирование полного паттерна
            if recursive:
                full_pattern = str(self.base_path / "**" / pattern)
            else:
                full_pattern = str(self.base_path / pattern)
            
            # Поиск файлов
            files = glob.glob(full_pattern, recursive=recursive)
            
            # Фильтрация по содержимому если указано
            if content_search:
                filtered_files = []
                for file_path in files:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if content_search in content:
                                filtered_files.append(file_path)
                                if len(filtered_files) >= max_results:
                                    break
                    except Exception:
                        continue
                files = filtered_files
            else:
                files = files[:max_results]
            
            # Формирование результатов
            results = []
            for file_path in files:
                try:
                    stat = os.stat(file_path)
                    rel_path = os.path.relpath(file_path, self.base_path)
                    results.append({
                        "path": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                except Exception:
                    continue
            
            output = f"Found {len(results)} files:\n"
            for r in results:
                output += f"  - {r['path']} ({r['size']} bytes)\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"files": results, "count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class FileReadTool(BaseTool):
    """Инструмент для умного чтения файлов с поддержкой чанков."""
    
    def __init__(self, base_path: str = "."):
        super().__init__(
            name="file_read",
            description="Чтение файлов с поддержкой построчного чтения и чанков. "
                       "Автоматически определяет кодировку и обрабатывает большие файлы."
        )
        self.base_path = Path(base_path).resolve()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Путь к файлу относительно базовой директории"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Начальная строка (0-based)",
                    "default": 0
                },
                "end_line": {
                    "type": "integer",
                    "description": "Конечная строка (exclusive), None для чтения до конца",
                    "default": None
                },
                "encoding": {
                    "type": "string",
                    "description": "Кодировка файла",
                    "default": "utf-8"
                }
            },
            returns="str"
        )
    
    def execute(
        self,
        path: str,
        start_line: int = 0,
        end_line: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> ToolResult:
        """
        Прочитать файл полностью или частично.
        
        Args:
            path: Путь к файлу
            start_line: Начальная строка
            end_line: Конечная строка
            encoding: Кодировка
            
        Returns:
            ToolResult с содержимым файла
        """
        try:
            # Безопасная проверка пути
            if ".." in path:
                raise ValueError("Path traversal not allowed")
            
            full_path = (self.base_path / path).resolve()
            
            # Проверка что файл внутри base_path
            if not str(full_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: path outside base directory")
            
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            if not full_path.is_file():
                raise ValueError(f"Not a file: {path}")
            
            # Чтение файла
            lines = []
            with open(full_path, 'r', encoding=encoding, errors='replace') as f:
                for i, line in enumerate(f):
                    if i < start_line:
                        continue
                    if end_line is not None and i >= end_line:
                        break
                    lines.append(line)
            
            content = ''.join(lines)
            total_lines = len(lines)
            
            output = f"File: {path}\n"
            output += f"Lines {start_line}-{end_line or 'end'} ({total_lines} lines):\n"
            output += "=" * 50 + "\n"
            output += content
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(full_path),
                    "lines_read": total_lines,
                    "start_line": start_line,
                    "end_line": end_line
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class FileWriteTool(BaseTool):
    """Инструмент для записи файлов."""
    
    def __init__(self, base_path: str = "."):
        super().__init__(
            name="file_write",
            description="Запись содержимого в файл. Создает директорию если нужно."
        )
        self.base_path = Path(base_path).resolve()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Путь к файлу"
                },
                "content": {
                    "type": "string",
                    "description": "Содержимое для записи"
                },
                "mode": {
                    "type": "string",
                    "description": "Режим записи: 'w' (overwrite) или 'a' (append)",
                    "default": "w"
                },
                "encoding": {
                    "type": "string",
                    "description": "Кодировка",
                    "default": "utf-8"
                }
            },
            returns="str"
        )
    
    def execute(
        self,
        path: str,
        content: str,
        mode: str = "w",
        encoding: str = "utf-8"
    ) -> ToolResult:
        """
        Записать содержимое в файл.
        
        Args:
            path: Путь к файлу
            content: Содержимое
            mode: Режим записи
            encoding: Кодировка
            
        Returns:
            ToolResult с результатом операции
        """
        try:
            # Безопасная проверка пути
            if ".." in path:
                raise ValueError("Path traversal not allowed")
            
            full_path = (self.base_path / path).resolve()
            
            # Проверка что файл внутри base_path
            if not str(full_path).startswith(str(self.base_path)):
                raise ValueError("Access denied: path outside base directory")
            
            # Создание директории если нужно
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Запись файла
            with open(full_path, mode, encoding=encoding) as f:
                f.write(content)
            
            file_size = len(content.encode(encoding))
            
            return ToolResult(
                success=True,
                output=f"Successfully wrote {file_size} bytes to {path}",
                metadata={
                    "path": str(full_path),
                    "size": file_size,
                    "mode": mode
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class ArchiveTool(BaseTool):
    """Инструмент для работы с архивами (zip/tar)."""
    
    def __init__(self, base_path: str = "."):
        super().__init__(
            name="archive",
            description="Создание и извлечение ZIP/TAR архивов."
        )
        self.base_path = Path(base_path).resolve()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "operation": {
                    "type": "string",
                    "description": "Операция: 'create' или 'extract'",
                    "enum": ["create", "extract"]
                },
                "archive_path": {
                    "type": "string",
                    "description": "Путь к архиву"
                },
                "files": {
                    "type": "array",
                    "description": "Список файлов для архивации (для create)",
                    "items": {"type": "string"}
                },
                "extract_dir": {
                    "type": "string",
                    "description": "Директория для извлечения (для extract)",
                    "default": "."
                },
                "format": {
                    "type": "string",
                    "description": "Формат архива: 'zip' или 'tar'",
                    "default": "zip"
                }
            },
            returns="str"
        )
    
    def execute(
        self,
        operation: str,
        archive_path: str,
        files: Optional[List[str]] = None,
        extract_dir: str = ".",
        format: str = "zip"
    ) -> ToolResult:
        """
        Создать или извлечь архив.
        
        Args:
            operation: 'create' или 'extract'
            archive_path: Путь к архиву
            files: Список файлов (для create)
            extract_dir: Директория для извлечения (для extract)
            format: Формат архива
            
        Returns:
            ToolResult с результатом операции
        """
        try:
            # Безопасная проверка путей
            if ".." in archive_path or (extract_dir and ".." in extract_dir):
                raise ValueError("Path traversal not allowed")
            
            if operation == "create":
                return self._create_archive(archive_path, files or [], format)
            elif operation == "extract":
                return self._extract_archive(archive_path, extract_dir, format)
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _create_archive(
        self,
        archive_path: str,
        files: List[str],
        format: str
    ) -> ToolResult:
        """Создать архив."""
        full_archive_path = (self.base_path / archive_path).resolve()
        
        if format == "zip":
            with zipfile.ZipFile(full_archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in files:
                    full_file_path = (self.base_path / file).resolve()
                    if full_file_path.exists():
                        arcname = os.path.relpath(full_file_path, self.base_path)
                        zf.write(full_file_path, arcname)
        elif format == "tar":
            with tarfile.open(full_archive_path, 'w:gz') as tf:
                for file in files:
                    full_file_path = (self.base_path / file).resolve()
                    if full_file_path.exists():
                        arcname = os.path.relpath(full_file_path, self.base_path)
                        tf.add(full_file_path, arcname)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return ToolResult(
            success=True,
            output=f"Created {format} archive: {archive_path} with {len(files)} files",
            metadata={
                "archive_path": str(full_archive_path),
                "files_count": len(files),
                "format": format
            }
        )
    
    def _extract_archive(
        self,
        archive_path: str,
        extract_dir: str,
        format: str
    ) -> ToolResult:
        """Извлечь архив."""
        full_archive_path = (self.base_path / archive_path).resolve()
        full_extract_dir = (self.base_path / extract_dir).resolve()
        
        # Проверка что extract_dir внутри base_path
        if not str(full_extract_dir).startswith(str(self.base_path)):
            raise ValueError("Access denied: extract path outside base directory")
        
        full_extract_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_count = 0
        
        if format == "zip":
            with zipfile.ZipFile(full_archive_path, 'r') as zf:
                zf.extractall(full_extract_dir)
                extracted_count = len(zf.namelist())
        elif format == "tar":
            with tarfile.open(full_archive_path, 'r:gz') as tf:
                tf.extractall(full_extract_dir)
                extracted_count = len(tf.getnames())
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return ToolResult(
            success=True,
            output=f"Extracted {extracted_count} files from {archive_path} to {extract_dir}",
            metadata={
                "archive_path": str(full_archive_path),
                "extract_dir": str(full_extract_dir),
                "files_count": extracted_count,
                "format": format
            }
        )
