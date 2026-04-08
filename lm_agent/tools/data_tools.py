"""
Data Analysis Tools for LM Agent.

Provides tools for working with CSV, Excel, and generating visualizations.
"""

import io
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import BaseTool, ToolResult, ToolDefinition


class CSVAnalysisTool(BaseTool):
    """
    Инструмент для анализа CSV файлов.
    
    Поддерживает:
    - Чтение и предпросмотр данных
    - Статистический анализ (mean, median, std)
    - Фильтрация и группировка
    """
    
    def __init__(self):
        super().__init__(
            name="csv_analysis",
            description="Анализ CSV файлов: статистика, фильтрация, группировка"
        )
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "file_path": {"type": "string", "description": "Путь к CSV файлу"},
                "operation": {
                    "type": "string", 
                    "enum": ["preview", "stats", "filter", "group"],
                    "description": "Тип операции"
                },
                "column": {"type": "string", "description": "Целевая колонка (опционально)"},
                "filters": {"type": "object", "description": "Фильтры (опционально)"},
                "limit": {"type": "integer", "description": "Лимит строк для preview"}
            },
            returns="str"
        )
    
    def execute(self, file_path: str, operation: str, 
                column: Optional[str] = None, filters: Optional[Dict] = None,
                limit: int = 10) -> ToolResult:
        """Выполнить анализ CSV."""
        try:
            # Проверка существования файла
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {file_path}"
                )
            
            if not path.suffix.lower() == '.csv':
                return ToolResult(
                    success=False,
                    output="",
                    error="Only CSV files are supported"
                )
            
            # Чтение файла
            import csv
            
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if not rows:
                return ToolResult(
                    success=False,
                    output="",
                    error="Empty CSV file"
                )
            
            if operation == "preview":
                return self._preview(rows, limit)
            elif operation == "stats":
                return self._stats(rows, column)
            elif operation == "filter":
                return self._filter(rows, filters or {})
            elif operation == "group":
                return self._group(rows, column)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def _preview(self, rows: List[Dict], limit: int) -> ToolResult:
        """Предпросмотр данных."""
        preview_rows = rows[:limit]
        result = {
            "total_rows": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "preview": preview_rows
        }
        return ToolResult(
            success=True,
            output=json.dumps(result, ensure_ascii=False, indent=2)
        )
    
    def _stats(self, rows: List[Dict], column: Optional[str]) -> ToolResult:
        """Статистический анализ."""
        if not column:
            # Общая статистика по всем колонкам
            stats = {}
            for col in rows[0].keys():
                values = [row[col] for row in rows if row.get(col)]
                stats[col] = {
                    "count": len(values),
                    "unique": len(set(values))
                }
        else:
            values = [row[column] for row in rows if row.get(column)]
            # Попытка числового анализа
            try:
                numeric_values = [float(v) for v in values]
                stats = {
                    "count": len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "sum": sum(numeric_values),
                    "mean": sum(numeric_values) / len(numeric_values)
                }
            except (ValueError, TypeError):
                stats = {
                    "count": len(values),
                    "unique": len(set(values)),
                    "sample": list(set(values))[:10]
                }
        
        return ToolResult(
            success=True,
            output=json.dumps(stats, ensure_ascii=False, indent=2)
        )
    
    def _filter(self, rows: List[Dict], filters: Dict) -> ToolResult:
        """Фильтрация данных."""
        filtered = rows
        
        for key, value in filters.items():
            filtered = [r for r in filtered if r.get(key) == str(value)]
        
        result = {
            "original_count": len(rows),
            "filtered_count": len(filtered),
            "data": filtered[:100]  # Лимит вывода
        }
        
        return ToolResult(
            success=True,
            output=json.dumps(result, ensure_ascii=False, indent=2)
        )
    
    def _group(self, rows: List[Dict], column: Optional[str]) -> ToolResult:
        """Группировка данных."""
        if not column:
            return ToolResult(
                success=False,
                output="",
                error="Column parameter is required for grouping"
            )
        
        groups = {}
        for row in rows:
            key = row.get(column, "unknown")
            if key not in groups:
                groups[key] = 0
            groups[key] += 1
        
        sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)
        
        return ToolResult(
            success=True,
            output=json.dumps(dict(sorted_groups[:20]), ensure_ascii=False, indent=2)
        )


class DataFrameTool(BaseTool):
    """
    Универсальный инструмент для работы с табличными данными.
    
    Использует pandas если доступен, иначе fallback на csv модуль.
    """
    
    def __init__(self):
        super().__init__(
            name="dataframe",
            description="Работа с табличными данными (CSV, Excel) через pandas"
        )
        self._pandas_available = False
        try:
            import pandas as pd
            self._pandas_available = True
        except ImportError:
            pass
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description + (" (pandas available)" if self._pandas_available else " (basic mode)"),
            parameters={
                "file_path": {"type": "string", "description": "Путь к файлу"},
                "operation": {
                    "type": "string",
                    "enum": ["load", "info", "describe", "query", "to_csv"],
                    "description": "Операция"
                },
                "query": {"type": "string", "description": "SQL-like запрос или выражение"},
                "output_path": {"type": "string", "description": "Путь для сохранения"}
            },
            returns="str"
        )
    
    def execute(self, file_path: str, operation: str,
                query: Optional[str] = None, 
                output_path: Optional[str] = None) -> ToolResult:
        """Выполнить операцию с данными."""
        
        if self._pandas_available:
            return self._execute_pandas(file_path, operation, query, output_path)
        else:
            # Fallback режим
            if operation == "load":
                return CSVAnalysisTool().execute(file_path, "preview", limit=20)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Pandas not available. Install with: pip install pandas"
                )
    
    def _execute_pandas(self, file_path: str, operation: str,
                       query: Optional[str], 
                       output_path: Optional[str]) -> ToolResult:
        """Выполнить через pandas."""
        try:
            import pandas as pd
            
            # Определение формата файла
            path = Path(file_path)
            suffix = path.suffix.lower()
            
            # Загрузка данных
            if suffix == '.csv':
                df = pd.read_csv(file_path)
            elif suffix in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unsupported file format: {suffix}"
                )
            
            if operation == "load":
                result = {
                    "shape": list(df.shape),
                    "columns": list(df.columns),
                    "preview": df.head(10).to_dict('records')
                }
                return ToolResult(
                    success=True,
                    output=json.dumps(result, ensure_ascii=False, default=str, indent=2)
                )
            
            elif operation == "info":
                buffer = io.StringIO()
                df.info(buf=buffer)
                return ToolResult(
                    success=True,
                    output=buffer.getvalue()
                )
            
            elif operation == "describe":
                desc = df.describe(include='all')
                return ToolResult(
                    success=True,
                    output=desc.to_string()
                )
            
            elif operation == "query":
                if not query:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Query parameter is required"
                    )
                try:
                    result_df = df.query(query)
                    return ToolResult(
                        success=True,
                        output=result_df.head(50).to_string()
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Query error: {str(e)}"
                    )
            
            elif operation == "to_csv":
                if not output_path:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Output path is required"
                    )
                df.to_csv(output_path, index=False)
                return ToolResult(
                    success=True,
                    output=f"Saved to {output_path} ({len(df)} rows)"
                )
            
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class VisualizationTool(BaseTool):
    """
    Инструмент для создания визуализаций.
    
    Создает графики на основе данных и сохраняет их как изображения.
    """
    
    def __init__(self, output_dir: str = "plots"):
        super().__init__(
            name="visualize",
            description="Создание графиков и визуализаций данных"
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._matplotlib_available = False
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            self._matplotlib_available = True
        except ImportError:
            pass
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description + (" (matplotlib available)" if self._matplotlib_available else ""),
            parameters={
                "data_file": {"type": "string", "description": "Путь к файлу с данными"},
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "scatter", "histogram", "pie"],
                    "description": "Тип графика"
                },
                "x_column": {"type": "string", "description": "Колонка для X оси"},
                "y_column": {"type": "string", "description": "Колонка для Y оси"},
                "title": {"type": "string", "description": "Заголовок графика"},
                "output_filename": {"type": "string", "description": "Имя выходного файла"}
            },
            returns="str"
        )
    
    def execute(self, data_file: str, chart_type: str,
                x_column: str, y_column: Optional[str] = None,
                title: str = "Chart", 
                output_filename: Optional[str] = None) -> ToolResult:
        """Создать визуализацию."""
        
        if not self._matplotlib_available:
            return ToolResult(
                success=False,
                output="",
                error="Matplotlib not available. Install with: pip install matplotlib"
            )
        
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
            
            # Загрузка данных
            path = Path(data_file)
            if path.suffix.lower() == '.csv':
                df = pd.read_csv(data_file)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Only CSV files supported for visualization"
                )
            
            # Создание фигуры
            fig, ax = plt.subplots(figsize=(10, 6))
            
            if chart_type == "line":
                ax.plot(df[x_column], df[y_column], marker='o')
            elif chart_type == "bar":
                ax.bar(df[x_column], df[y_column])
                plt.xticks(rotation=45)
            elif chart_type == "scatter":
                ax.scatter(df[x_column], df[y_column])
            elif chart_type == "histogram":
                ax.hist(df[x_column], bins=20, edgecolor='black')
            elif chart_type == "pie":
                sizes = df.groupby(x_column)[y_column].sum()
                ax.pie(sizes, labels=sizes.index, autopct='%1.1f%%')
            
            ax.set_title(title)
            ax.set_xlabel(x_column)
            if y_column and chart_type != "pie":
                ax.set_ylabel(y_column)
            
            plt.tight_layout()
            
            # Сохранение
            if not output_filename:
                output_filename = f"{chart_type}_{title.replace(' ', '_')}.png"
            
            output_path = self.output_dir / output_filename
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            return ToolResult(
                success=True,
                output=f"Chart saved to: {output_path.absolute()}",
                metadata={"path": str(output_path.absolute())}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
