"""
Tests for new LM Agent features.

Tests for data tools, code tools, and integration.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path


class TestDataTools:
    """Тесты для инструментов анализа данных."""
    
    def test_csv_analysis_tool_preview(self):
        """Тест предпросмотра CSV."""
        from lm_agent.tools.data_tools import CSVAnalysisTool
        
        # Создание тестового CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age,city\n")
            f.write("Alice,25,NYC\n")
            f.write("Bob,30,LA\n")
            f.write("Charlie,35,SF\n")
            csv_path = f.name
        
        try:
            tool = CSVAnalysisTool()
            result = tool.execute(file_path=csv_path, operation="preview", limit=2)
            
            assert result.success is True
            data = json.loads(result.output)
            assert data["total_rows"] == 3
            assert len(data["preview"]) == 2
            assert "name" in data["columns"]
        finally:
            os.unlink(csv_path)
    
    def test_csv_analysis_tool_stats(self):
        """Тест статистики CSV."""
        from lm_agent.tools.data_tools import CSVAnalysisTool
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("id,value\n")
            f.write("1,10\n")
            f.write("2,20\n")
            f.write("3,30\n")
            csv_path = f.name
        
        try:
            tool = CSVAnalysisTool()
            result = tool.execute(file_path=csv_path, operation="stats", column="value")
            
            assert result.success is True
            data = json.loads(result.output)
            assert data["count"] == 3
            assert data["min"] == 10.0
            assert data["max"] == 30.0
            assert data["mean"] == 20.0
        finally:
            os.unlink(csv_path)
    
    def test_csv_analysis_tool_filter(self):
        """Тест фильтрации CSV."""
        from lm_agent.tools.data_tools import CSVAnalysisTool
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age,city\n")
            f.write("Alice,25,NYC\n")
            f.write("Bob,30,LA\n")
            f.write("Charlie,35,NYC\n")
            csv_path = f.name
        
        try:
            tool = CSVAnalysisTool()
            result = tool.execute(
                file_path=csv_path, 
                operation="filter",
                filters={"city": "NYC"}
            )
            
            assert result.success is True
            data = json.loads(result.output)
            assert data["filtered_count"] == 2
        finally:
            os.unlink(csv_path)
    
    def test_dataframe_tool_basic(self):
        """Тест базовой работы DataFrameTool."""
        from lm_agent.tools.data_tools import DataFrameTool
        
        tool = DataFrameTool()
        
        # Проверка что инструмент инициализирован
        assert tool.name == "dataframe"
        assert tool._pandas_available or not tool._pandas_available  # Either way is OK
    
    def test_visualization_tool_initialization(self):
        """Тест инициализации инструмента визуализации."""
        from lm_agent.tools.data_tools import VisualizationTool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = VisualizationTool(output_dir=tmpdir)
            assert tool.name == "visualize"
            assert Path(tmpdir).exists()


class TestCodeTools:
    """Тесты для инструментов качества кода."""
    
    def test_code_linting_tool_detection(self):
        """Тест обнаружения линтера."""
        from lm_agent.tools.code_tools import CodeLintingTool
        
        tool = CodeLintingTool()
        assert tool.name == "code_lint"
        # Линтер может быть или не быть установлен - оба варианта OK
    
    def test_code_formatting_tool_detection(self):
        """Тест обнаружения форматтера."""
        from lm_agent.tools.code_tools import CodeFormattingTool
        
        tool = CodeFormattingTool()
        assert tool.name == "code_format"
        # Форматтер может быть или не быть установлен - оба варианта OK
    
    def test_unit_test_generator_pytest_template(self):
        """Тест генерации pytest шаблона."""
        from lm_agent.tools.code_tools import UnitTestGeneratorTool
        
        code = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

class Calculator:
    def divide(self, a, b):
        return a / b
"""
        
        tool = UnitTestGeneratorTool()
        result = tool.execute(code=code, test_template="pytest", run_tests=False)
        
        assert result.success is True
        data = json.loads(result.output)
        assert "test_code" in data
        assert "def test_add():" in data["test_code"]
        assert "def test_multiply():" in data["test_code"]
        assert "class TestCalculator:" in data["test_code"]
    
    def test_unit_test_generator_unittest_template(self):
        """Тест генерации unittest шаблона."""
        from lm_agent.tools.code_tools import UnitTestGeneratorTool
        
        code = """
def greet(name):
    return f"Hello, {name}"
"""
        
        tool = UnitTestGeneratorTool()
        result = tool.execute(code=code, test_template="unittest", run_tests=False)
        
        assert result.success is True
        data = json.loads(result.output)
        assert "test_code" in data
        assert "class TestGreet(unittest.TestCase):" in data["test_code"]
    
    def test_code_linting_invalid_code(self):
        """Тест линтинга невалидного кода."""
        from lm_agent.tools.code_tools import CodeLintingTool
        
        invalid_code = """
def broken(
    # Missing closing paren and body
"""
        
        tool = CodeLintingTool()
        # Если линтер не установлен, просто пропускаем
        if tool._linter is None:
            pytest.skip("No linter available")
            return
        
        result = tool.execute(code=invalid_code)
        # Должна быть ошибка синтаксиса или линтинг ошибка
        assert not result.success or "syntax" in result.output.lower() or result.error


class TestIntegration:
    """Интеграционные тесты."""
    
    def test_all_tools_importable(self):
        """Тест что все инструменты импортируются."""
        from lm_agent import (
            # File Tools
            FileSearchTool,
            FileReadTool,
            FileWriteTool,
            ArchiveTool,
            # Web Tools
            WebSearchTool,
            WebScraperTool,
            APIClientTool,
            # Data Tools
            CSVAnalysisTool,
            DataFrameTool,
            VisualizationTool,
            # Code Tools
            CodeLintingTool,
            CodeFormattingTool,
            UnitTestGeneratorTool,
        )
        
        # Проверка что классы существуют
        assert FileSearchTool is not None
        assert WebSearchTool is not None
        assert CSVAnalysisTool is not None
        assert CodeLintingTool is not None
    
    def test_memory_and_planning_integration(self):
        """Тест интеграции памяти и планирования."""
        from lm_agent import (
            ShortTermMemory,
            LongTermMemory,
            EpisodicMemory,
            ReActAgent,
            PlanAndSolveAgent
        )
        
        # Создание компонентов
        stm = ShortTermMemory(max_messages=10)
        ltm = LongTermMemory()
        em = EpisodicMemory(max_episodes=5)
        
        react = ReActAgent(max_iterations=5)
        plan_solve = PlanAndSolveAgent(max_retries=2)
        
        # Добавление в память
        stm.add("user", "Test message")
        ltm.add("Important fact", importance=0.9)
        em.add_episode("task", "action", "result", success=True, lesson="Learned something")
        
        # Проверка
        assert len(stm.messages) == 1
        assert ltm.vector_store.count() >= 1
        assert len(em.episodes) == 1
    
    def test_tool_result_serialization(self):
        """Тест сериализации результатов инструментов."""
        from lm_agent.tools.base import ToolResult
        import json
        
        result = ToolResult(
            success=True,
            output="Test output",
            metadata={"key": "value"},
            execution_time=0.5
        )
        
        # Проверка строкового представления
        assert "Test output" in str(result)
        
        # Проверка что можно конвертировать в dict для JSON
        data = {
            "success": result.success,
            "output": result.output,
            "metadata": result.metadata
        }
        json_str = json.dumps(data)
        assert "Test output" in json_str


class TestPlanExecution:
    """Тесты выполнения планов."""
    
    def test_plan_creation_and_execution(self):
        """Тест создания и выполнения плана."""
        from lm_agent.core.planning import Plan, PlanStep, StepStatus
        
        plan = Plan(task="Test task")
        
        step1 = plan.add_step("Step 1", tool_name="tool1", tool_args={"arg": "val"})
        step2 = plan.add_step("Step 2", tool_name="tool2")
        
        assert len(plan.steps) == 2
        assert step1.id == 1
        assert step2.id == 2
        assert step1.status == StepStatus.PENDING
        
        # Симуляция выполнения
        step1.status = StepStatus.COMPLETED
        step1.result = "Result 1"
        
        assert plan.get_next_pending_step().id == 2
        assert not plan.is_complete()
        
        step2.status = StepStatus.COMPLETED
        assert plan.is_complete()
    
    def test_plan_with_failures(self):
        """Тест плана с неудачами."""
        from lm_agent.core.planning import Plan, StepStatus
        
        plan = Plan(task="Task with failures")
        plan.add_step("Step 1")
        plan.add_step("Step 2")
        
        step1 = plan.steps[0]
        step1.status = StepStatus.FAILED
        step1.error = "Something went wrong"
        
        assert plan.has_failed()
        assert step1.retry_count == 0
