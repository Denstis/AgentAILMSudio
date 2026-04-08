"""
Base Tool Module for LM Agent.

This module provides the base class for all tools that the agent can use.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import time


@dataclass
class ToolResult:
    """Результат выполнения инструмента."""
    
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    
    def __str__(self) -> str:
        if self.success:
            return self.output
        else:
            return f"Error: {self.error}"


@dataclass
class ToolDefinition:
    """Определение инструмента для LLM."""
    
    name: str
    description: str
    parameters: Dict[str, Any]
    returns: str = "str"
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для промпта."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns
        }


class BaseTool(ABC):
    """
    Базовый класс для всех инструментов агента.
    
    Все инструменты должны наследовать этот класс и реализовать метод execute().
    """
    
    def __init__(self, name: str, description: str):
        """
        Инициализация инструмента.
        
        Args:
            name: Уникальное имя инструмента
            description: Описание того, что делает инструмент
        """
        self.name = name
        self.description = description
        self._execution_count = 0
        self._total_execution_time = 0.0
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Возвращает определение инструмента для LLM."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Выполнить инструмент с заданными параметрами.
        
        Args:
            **kwargs: Параметры для выполнения инструмента
            
        Returns:
            ToolResult: Результат выполнения
        """
        pass
    
    def run(self, **kwargs) -> ToolResult:
        """
        Обертка для execute с измерением времени и подсчетом вызовов.
        
        Args:
            **kwargs: Параметры для выполнения инструмента
            
        Returns:
            ToolResult: Результат выполнения
        """
        start_time = time.time()
        try:
            result = self.execute(**kwargs)
            result.execution_time = time.time() - start_time
            self._execution_count += 1
            self._total_execution_time += result.execution_time
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self._execution_count += 1
            self._total_execution_time += execution_time
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования инструмента."""
        return {
            "name": self.name,
            "execution_count": self._execution_count,
            "total_execution_time": self._total_execution_time,
            "avg_execution_time": (
                self._total_execution_time / self._execution_count 
                if self._execution_count > 0 else 0.0
            )
        }
    
    def reset_stats(self) -> None:
        """Сбросить статистику инструмента."""
        self._execution_count = 0
        self._total_execution_time = 0.0
