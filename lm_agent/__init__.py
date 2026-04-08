"""
LM Agent - Модульная архитектура с расширенными возможностями

Структура проекта:

lm_agent/
├── core/                 # Ядро системы (config, memory, planning)
├── tools/                # Инструменты (file, web, base)
├── sandbox/              # Песочница и безопасность
├── gui/                  # Графический интерфейс
├── config/               # Файлы конфигурации
├── utils/                # Утилиты
└── tests/                # Тесты

Версия 0.2.0 добавляет:
- Базовые классы инструментов (BaseTool)
- Файловые инструменты (поиск, чтение, запись, архивы)
- Веб инструменты (поиск, scraping, API)
- Система памяти (краткосрочная, долгосрочная, эпизодическая)
- Планирование (ReAct, Plan-and-Solve, саморефлексия)
"""

__version__ = "0.2.0"
__author__ = "LM Agent Team"

# Core imports
from lm_agent.core.config import (
    ProgressEntry,
    ModelCaps,
    ModelInfo,
    AgentConfig,
    TaskData,
    SandboxAdvancedConfig,
)

# Memory imports
from lm_agent.core.memory import (
    ShortTermMemory,
    LongTermMemory,
    EpisodicMemory,
    MemoryEntry
)

# Planning imports
from lm_agent.core.planning import (
    ReActAgent,
    PlanAndSolveAgent,
    SelfReflection,
    Plan,
    PlanStep,
    StepStatus
)

# Tool imports
from lm_agent.tools.base import (
    BaseTool,
    ToolResult,
    ToolDefinition
)

from lm_agent.tools.file_tools import (
    FileSearchTool,
    FileReadTool,
    FileWriteTool,
    ArchiveTool
)

from lm_agent.tools.web_tools import (
    WebSearchTool,
    WebScraperTool,
    APIClientTool
)

from lm_agent.tools.data_tools import (
    CSVAnalysisTool,
    DataFrameTool,
    VisualizationTool
)

from lm_agent.tools.code_tools import (
    CodeLintingTool,
    CodeFormattingTool,
    UnitTestGeneratorTool
)

# Sandbox imports
from lm_agent.sandbox.validator import (
    ValidationResult,
    safe_path
)

from lm_agent.sandbox.modules import (
    get_allowed_modules,
    is_module_allowed,
    contains_forbidden_pattern
)

__all__ = [
    # Core Config
    "ProgressEntry",
    "ModelCaps",
    "ModelInfo",
    "AgentConfig",
    "TaskData",
    "SandboxAdvancedConfig",
    
    # Memory
    "ShortTermMemory",
    "LongTermMemory",
    "EpisodicMemory",
    "MemoryEntry",
    
    # Planning
    "ReActAgent",
    "PlanAndSolveAgent",
    "SelfReflection",
    "Plan",
    "PlanStep",
    "StepStatus",
    
    # Tools Base
    "BaseTool",
    "ToolResult",
    "ToolDefinition",
    
    # File Tools
    "FileSearchTool",
    "FileReadTool",
    "FileWriteTool",
    "ArchiveTool",
    
    # Web Tools
    "WebSearchTool",
    "WebScraperTool",
    "APIClientTool",
    
    # Data Tools
    "CSVAnalysisTool",
    "DataFrameTool",
    "VisualizationTool",
    
    # Code Tools
    "CodeLintingTool",
    "CodeFormattingTool",
    "UnitTestGeneratorTool",
    
    # Sandbox
    "ValidationResult",
    "safe_path",
    "get_allowed_modules",
    "is_module_allowed",
    "contains_forbidden_pattern",
]
