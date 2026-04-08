"""
Planning and Reasoning Module for LM Agent.

Implements ReAct, Plan-and-Solve, and Self-Reflection patterns.
"""

import json
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StepStatus(Enum):
    """Статус шага плана."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Шаг плана."""
    
    id: int
    description: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count
        }


@dataclass
class Plan:
    """План выполнения задачи."""
    
    task: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    reflection: Optional[str] = None
    
    def add_step(self, description: str, tool_name: Optional[str] = None,
                 tool_args: Optional[Dict] = None) -> PlanStep:
        """Добавить шаг в план."""
        step = PlanStep(
            id=len(self.steps) + 1,
            description=description,
            tool_name=tool_name,
            tool_args=tool_args
        )
        self.steps.append(step)
        return step
    
    def get_next_pending_step(self) -> Optional[PlanStep]:
        """Получить следующий ожидающий шаг."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None
    
    def get_current_step(self) -> Optional[PlanStep]:
        """Получить текущий выполняемый шаг."""
        for step in self.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        return None
    
    def is_complete(self) -> bool:
        """Проверить завершен ли план."""
        return all(
            step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] 
            for step in self.steps
        ) and len(self.steps) > 0
    
    def has_failed(self) -> bool:
        """Проверить есть ли неудачные шаги."""
        return any(step.status == StepStatus.FAILED for step in self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "reflection": self.reflection
        }


class ReActAgent:
    """
    Реализация паттерна ReAct (Reason -> Act -> Observe).
    
    Цикл:
    1. Thought (Размышление): Анализ текущей ситуации
    2. Action (Действие): Выбор и выполнение инструмента
    3. Observation (Наблюдение): Анализ результата
    4. Repeat until solved
    """
    
    def __init__(self, max_iterations: int = 10):
        """
        Инициализация ReAct агента.
        
        Args:
            max_iterations: Максимальное количество итераций
        """
        self.max_iterations = max_iterations
        self.history: List[Dict[str, str]] = []
    
    def think(self, task: str, context: List[Dict]) -> str:
        """
        Сгенерировать размышление о следующем шаге.
        
        Args:
            task: Исходная задача
            context: Контекст диалога
            
        Returns:
            Текст размышления
        """
        # Это должно вызываться через LLM
        # Здесь только структура
        thought = {
            "task": task,
            "current_state": "Analyzing...",
            "next_action": " TBD",
            "reasoning": ""
        }
        return json.dumps(thought, ensure_ascii=False)
    
    def act(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнить действие через инструмент.
        
        Args:
            tool_name: Имя инструмента
            tool_args: Аргументы инструмента
            
        Returns:
            Результат действия
        """
        return {
            "tool": tool_name,
            "args": tool_args,
            "status": "executed"
        }
    
    def observe(self, result: Any) -> str:
        """
        Проанализировать результат действия.
        
        Args:
            result: Результат выполнения инструмента
            
        Returns:
            Наблюдение о результате
        """
        observation = {
            "outcome": "success" if result else "failure",
            "learnings": [],
            "next_steps": []
        }
        return json.dumps(observation, ensure_ascii=False)
    
    def run_cycle(self, task: str, tools: Dict[str, Any], 
                  llm_callback: callable) -> Dict[str, Any]:
        """
        Запустить полный цикл ReAct.
        
        Args:
            task: Задача для решения
            tools: Доступные инструменты
            llm_callback: Функция для вызова LLM
            
        Returns:
            Результат выполнения
        """
        self.history = []
        
        for iteration in range(self.max_iterations):
            # Thought
            thought = self.think(task, self.history)
            self.history.append({"role": "thought", "content": thought})
            
            # Parse LLM response for action
            # This would be done by LLM in real implementation
            action = llm_callback(thought, tools)
            
            if action.get("type") == "final_answer":
                return {
                    "success": True,
                    "answer": action.get("answer"),
                    "iterations": iteration + 1
                }
            
            # Act
            tool_name = action.get("tool")
            tool_args = action.get("args", {})
            
            if tool_name not in tools:
                self.history.append({
                    "role": "error", 
                    "content": f"Unknown tool: {tool_name}"
                })
                continue
            
            action_result = self.act(tool_name, tool_args)
            actual_result = tools[tool_name].run(**tool_args)
            
            # Observe
            observation = self.observe(actual_result)
            self.history.append({
                "role": "observation",
                "content": observation
            })
            
            # Check if solved
            if actual_result.success and self._is_task_solved(task, actual_result.output):
                return {
                    "success": True,
                    "answer": actual_result.output,
                    "iterations": iteration + 1
                }
        
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": self.max_iterations
        }
    
    def _is_task_solved(self, task: str, result: str) -> bool:
        """Проверить решает ли результат задачу."""
        # Упрощенная проверка - должна быть реализована через LLM
        return len(result) > 0


class PlanAndSolveAgent:
    """
    Паттерн Plan-and-Solve.
    
    1. Создать детальный план
    2. Выполнять по одному шагу
    3. Корректировать план при ошибках
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Инициализация агента.
        
        Args:
            max_retries: Максимальное количество попыток на шаг
        """
        self.max_retries = max_retries
        self.current_plan: Optional[Plan] = None
    
    def create_plan(self, task: str, llm_callback: callable) -> Plan:
        """
        Создать план выполнения задачи.
        
        Args:
            task: Задача
            llm_callback: Функция для вызова LLM
            
        Returns:
            План выполнения
        """
        plan = Plan(task=task)
        
        # LLM должен создать шаги плана
        # Здесь пример структуры
        steps_data = llm_callback(f"Create a step-by-step plan for: {task}")
        
        # Парсинг шагов из ответа LLM
        # В реальности нужно парсить JSON или структурированный ответ
        for i, step_desc in enumerate(steps_data.get("steps", [])):
            plan.add_step(
                description=step_desc.get("description"),
                tool_name=step_desc.get("tool"),
                tool_args=step_desc.get("args")
            )
        
        self.current_plan = plan
        return plan
    
    def execute_step(self, step: PlanStep, tools: Dict[str, Any]) -> bool:
        """
        Выполнить один шаг плана.
        
        Args:
            step: Шаг для выполнения
            tools: Доступные инструменты
            
        Returns:
            Успех выполнения
        """
        step.status = StepStatus.IN_PROGRESS
        step.started_at = datetime.now()
        
        for attempt in range(self.max_retries):
            step.retry_count = attempt
            
            try:
                if step.tool_name and step.tool_name in tools:
                    result = tools[step.tool_name].run(**(step.tool_args or {}))
                    
                    if result.success:
                        step.status = StepStatus.COMPLETED
                        step.result = result.output
                        step.completed_at = datetime.now()
                        return True
                    else:
                        step.error = result.error
                else:
                    step.error = f"Tool not found: {step.tool_name}"
                    
            except Exception as e:
                step.error = str(e)
        
        step.status = StepStatus.FAILED
        step.completed_at = datetime.now()
        return False
    
    def adjust_plan(self, failed_step: PlanStep, llm_callback: callable) -> bool:
        """
        Скорректировать план после неудачи.
        
        Args:
            failed_step: Неудачный шаг
            llm_callback: Функция для вызова LLM
            
        Returns:
            Есть ли изменения в плане
        """
        if not self.current_plan:
            return False
        
        # Запрос к LLM для корректировки плана
        adjustment = llm_callback(
            f"Step failed: {failed_step.description}. Error: {failed_step.error}. "
            "How to adjust the plan?"
        )
        
        # Применение корректировок
        # В реальности LLM вернет новые шаги или изменения
        if adjustment.get("action") == "skip":
            failed_step.status = StepStatus.SKIPPED
        elif adjustment.get("action") == "modify":
            failed_step.description = adjustment.get("new_description", failed_step.description)
            failed_step.tool_args = adjustment.get("new_args", failed_step.tool_args)
            failed_step.status = StepStatus.PENDING  # Попробовать снова
        elif adjustment.get("action") == "add_steps":
            # Добавить новые шаги после текущего
            for new_step_data in adjustment.get("steps", []):
                self.current_plan.add_step(
                    description=new_step_data.get("description"),
                    tool_name=new_step_data.get("tool"),
                    tool_args=new_step_data.get("args")
                )
            failed_step.status = StepStatus.PENDING
        
        return True
    
    def run(self, task: str, tools: Dict[str, Any], 
            llm_callback: callable) -> Dict[str, Any]:
        """
        Выполнить задачу по плану.
        
        Args:
            task: Задача
            tools: Инструменты
            llm_callback: Вызов LLM
            
        Returns:
            Результат выполнения
        """
        # Создание плана
        plan = self.create_plan(task, llm_callback)
        
        results = []
        
        while not plan.is_complete():
            step = plan.get_next_pending_step()
            
            if not step:
                break
            
            success = self.execute_step(step, tools)
            
            if not success:
                # Попытка корректировки плана
                adjusted = self.adjust_plan(step, llm_callback)
                
                if not adjusted:
                    plan.status = "failed"
                    return {
                        "success": False,
                        "error": f"Failed at step {step.id}: {step.error}",
                        "plan": plan.to_dict(),
                        "results": results
                    }
            
            results.append(step.to_dict())
        
        plan.completed_at = datetime.now()
        plan.status = "completed"
        
        return {
            "success": True,
            "plan": plan.to_dict(),
            "results": results
        }


class SelfReflection:
    """
    Модуль саморефлексии для оценки качества действий.
    """
    
    def __init__(self):
        self.evaluation_history: List[Dict] = []
    
    def evaluate_action(self, task: str, action: str, 
                       result: str, llm_callback: callable) -> Dict[str, Any]:
        """
        Оценить качество выполненного действия.
        
        Args:
            task: Исходная задача
            action: Предпринятое действие
            result: Результат
            llm_callback: Вызов LLM
            
        Returns:
            Оценка и рекомендации
        """
        evaluation = llm_callback(
            f"Task: {task}\nAction: {action}\nResult: {result}\n"
            "Evaluate the quality of this action (1-10) and provide feedback."
        )
        
        eval_record = {
            "task": task,
            "action": action,
            "result": result,
            "score": evaluation.get("score", 5),
            "feedback": evaluation.get("feedback", ""),
            "timestamp": datetime.now().isoformat()
        }
        
        self.evaluation_history.append(eval_record)
        
        return eval_record
    
    def get_improvement_suggestions(self, llm_callback: callable) -> List[str]:
        """
        Получить рекомендации по улучшению на основе истории.
        
        Args:
            llm_callback: Вызов LLM
            
        Returns:
            Список рекомендаций
        """
        if not self.evaluation_history:
            return []
        
        suggestions = llm_callback(
            "Based on these past evaluations, suggest improvements:\n"
            f"{json.dumps(self.evaluation_history[-10:], indent=2)}"
        )
        
        return suggestions.get("suggestions", [])
    
    def should_retry(self, task: str, failures: int, 
                    llm_callback: callable) -> bool:
        """
        Решить стоит ли повторять попытку.
        
        Args:
            task: Задача
            failures: Количество неудач
            llm_callback: Вызов LLM
            
        Returns:
            Стоит ли повторять
        """
        if failures >= 3:
            return False
        
        decision = llm_callback(
            f"Task '{task}' has failed {failures} times. Should we try again?"
        )
        
        return decision.get("retry", False)
