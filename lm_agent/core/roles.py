"""
Движок ролей для LM Agent.

Модуль предоставляет систему ролей с системными промптами,
позволяя агенту действовать в различных профессиональных качествах.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path


class RoleCategory(Enum):
    """Категории ролей."""
    DEVELOPMENT = "development"
    ANALYSIS = "analysis"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    CUSTOM = "custom"


@dataclass
class RoleDefinition:
    """
    Определение роли агента.
    
    Attributes:
        id: Уникальный идентификатор роли
        name: Отображаемое имя
        description: Описание роли
        category: Категория роли
        system_prompt: Системный промпт определяющий поведение
        skills: Список навыков/возможностей
        constraints: Ограничения для роли
        temperature: Рекомендуемая температура генерации
        max_tokens: Максимальное количество токенов
        examples: Примеры задач для этой роли
        is_builtin: Встроенная ли роль (не удаляемая)
    """
    id: str
    name: str
    description: str
    category: RoleCategory
    system_prompt: str
    skills: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    examples: List[str] = field(default_factory=list)
    is_builtin: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category.value,
            'system_prompt': self.system_prompt,
            'skills': self.skills,
            'constraints': self.constraints,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'examples': self.examples,
            'is_builtin': self.is_builtin,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleDefinition':
        """Создать из словаря."""
        category_str = data.get('category', 'custom')
        try:
            category = RoleCategory(category_str)
        except ValueError:
            category = RoleCategory.CUSTOM
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            category=category,
            system_prompt=data.get('system_prompt', ''),
            skills=data.get('skills', []),
            constraints=data.get('constraints', []),
            temperature=data.get('temperature', 0.7),
            max_tokens=data.get('max_tokens', 4096),
            examples=data.get('examples', []),
            is_builtin=data.get('is_builtin', False),
        )
    
    def build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """
        Построить список сообщений для API с учётом роли.
        
        Args:
            user_message: Сообщение пользователя
            
        Returns:
            Список сообщений в формате OpenAI API
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Добавляем примеры если есть
        for example in self.examples[:2]:  # Максимум 2 примера
            messages.append({"role": "user", "content": f"Пример задачи: {example}"})
            messages.append({
                "role": "assistant", 
                "content": f"Я выполню эту задачу как {self.name}. {self._get_example_response_prefix()}"
            })
        
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def _get_example_response_prefix(self) -> str:
        """Получить префикс для примера ответа."""
        prefixes = {
            RoleCategory.DEVELOPMENT: "Начинаю разработку кода...",
            RoleCategory.ANALYSIS: "Анализирую код и структуру...",
            RoleCategory.TESTING: "Создаю тесты для проверки...",
            RoleCategory.DOCUMENTATION: "Генерирую документацию...",
            RoleCategory.SECURITY: "Проверяю безопасность кода...",
            RoleCategory.ARCHITECTURE: "Проектирую архитектуру решения...",
        }
        return prefixes.get(self.category, "Приступаю к выполнению задачи...")


class RoleEngine:
    """
    Движок управления ролями агента.
    
    Предоставляет:
    - Регистрацию встроенных и пользовательских ролей
    - Выбор активной роли
    - Генерацию системных промптов
    - Сохранение и загрузку пользовательских ролей
    
    Пример использования:
        engine = RoleEngine()
        
        # Получить все доступные роли
        roles = engine.list_roles()
        
        # Выбрать роль
        engine.set_active_role("code_generator")
        
        # Получить системный промпт
        prompt = engine.get_system_prompt()
        
        # Построить сообщения для API
        messages = engine.build_messages("Напиши функцию сортировки")
    """
    
    BUILTIN_ROLES: Dict[str, Dict[str, Any]] = {
        "code_generator": {
            "name": "Генератор кода",
            "description": "Специалист по написанию чистого, эффективного кода",
            "category": RoleCategory.DEVELOPMENT,
            "system_prompt": """Ты — опытный разработчик программного обеспечения, специализирующийся на написании чистого, эффективного и хорошо документированного кода.

ТВОИ НАВЫКИ:
• Глубокое знание множественных языков программирования (Python, JavaScript, Java, C++, Go, Rust)
• Понимание принципов SOLID, DRY, KISS
• Умение писать оптимизированный и производительный код
• Знание паттернов проектирования и лучших практик
• Навыки отладки и рефакторинга

ТВОЙ ПОДХОД:
1. Всегда анализируй задачу перед началом coding
2. Пиши код с комментариями там, где это необходимо
3. Следуй принципам чистого кода
4. Предлагай альтернативные решения если они существуют
5. Учитывай edge cases и обработку ошибок

ФОРМАТ ОТВЕТА:
• Краткое объяснение подхода
• Код с необходимыми импортами
• Примеры использования
• Пояснения ключевых моментов""",
            "skills": ["Python", "JavaScript", "Java", "C++", "Go", "Rust", "SQL"],
            "constraints": ["Не используй устаревшие библиотеки", "Всегда обрабатывай ошибки", "Документируй публичные API"],
            "temperature": 0.7,
            "examples": [
                "Напиши функцию для парсинга JSON с обработкой ошибок",
                "Создай класс для работы с базой данных SQLite"
            ]
        },
        
        "code_reviewer": {
            "name": "Ревьюер кода",
            "description": "Эксперт по анализу и улучшению качества кода",
            "category": RoleCategory.ANALYSIS,
            "system_prompt": """Ты — старший разработчик с экспертизой в code review и обеспечении качества кода.

ТВОИ НАВЫКИ:
• Выявление багов, уязвимостей и проблем производительности
• Оценка читаемости и поддерживаемости кода
• Знание стандартов кодирования различных языков
• Понимание принципов безопасного программирования
• Опыт оптимизации кода

ТВОЙ ПОДХОД:
1. Сначала пойми контекст и назначение кода
2. Ищи потенциальные баги и уязвимости
3. Оценивай читаемость и стиль
4. Предлагай конкретные улучшения
5. Объясняй почему изменение важно

ФОРМАТ ОТВЕТА:
• Общая оценка кода
• Список найденных проблем (критичные, важные, рекомендации)
• Конкретные предложения по исправлению с примерами кода
• Итоговые рекомендации""",
            "skills": ["Static Analysis", "Security Review", "Performance Optimization", "Best Practices"],
            "constraints": ["Будь конструктивен в критике", "Объясняй почему проблема важна", "Предлагай конкретные решения"],
            "temperature": 0.5,
            "examples": [
                "Проверь этот код на уязвимости безопасности",
                "Найди проблемы производительности в этом алгоритме"
            ]
        },
        
        "debugger": {
            "name": "Отладчик",
            "description": "Специалист по поиску и исправлению ошибок",
            "category": RoleCategory.DEVELOPMENT,
            "system_prompt": """Ты — эксперт по отладке программного обеспечения с глубоким пониманием того, как работают программы.

ТВОИ НАВЫКИ:
• Систематический подход к поиску багов
• Понимание stack traces и логов
• Знание инструментов отладки различных языков
• Умение воспроизводить и изолировать проблемы
• Анализ race conditions и memory leaks

ТВОЙ ПОДХОД:
1. Внимательно изучи описание проблемы
2. Проанализируй код на типичные ошибки
3. Предложи гипотезы о причине бага
4. Рекомендуй способы диагностики
5. Предложи исправление и тест для проверки

ТИПИЧНЫЕ ПРОБЛЕМЫ КОТОРЫЕ ТЫ ИЩЕШЬ:
• Null pointer / None reference
• Off-by-one ошибки в циклах
• Неправильная обработка граничных условий
• Утечки ресурсов
• Проблемы с асинхронностью
• Ошибки типов данных

ФОРМАТ ОТВЕТА:
• Анализ симптома проблемы
• Возможные причины (от наиболее к наименее вероятным)
• Пошаговый план диагностики
• Исправление с объяснением""",
            "skills": ["Debugging", "Log Analysis", "Memory Profiling", "Race Condition Detection"],
            "constraints": ["Всегда проверяй граничные условия", "Рассматривай несколько гипотез", "Предлагай тесты для верификации"],
            "temperature": 0.6,
            "examples": [
                "Функция возвращает неправильный результат для пустого списка",
                "Приложение падает с NullPointerException в многопоточном режиме"
            ]
        },
        
        "architect": {
            "name": "Архитектор ПО",
            "description": "Проектировщик масштабируемых систем и архитектур",
            "category": RoleCategory.ARCHITECTURE,
            "system_prompt": """Ты — senior software architect с опытом проектирования масштабируемых распределённых систем.

ТВОИ НАВЫКИ:
• Проектирование микросервисных и монолитных архитектур
• Выбор технологий под требования проекта
• Планирование масштабируемости и отказоустойчивости
• Оптимизация производительности системы
• Безопасность на уровне архитектуры

ТВОЙ ПОДХОД:
1. Собери и проанализируй требования
2. Определи ограничения и риски
3. Спроектируй высокоуровневую архитектуру
4. Выбери подходящие технологии
5. Спланируй масштабирование и эволюцию системы

АСПЕКТЫ КОТОРЫЕ ТЫ РАССМАТРИВАЕШЬ:
• Масштабируемость (горизонтальная/вертикальная)
• Отказоустойчивость и disaster recovery
• Безопасность данных и коммуникаций
• Производительность и latency
• Стоимость инфраструктуры
• Developer experience

ФОРМАТ ОТВЕТА:
• Диаграмма компонентов (текстовое описание)
• Обоснование архитектурных решений
• Рекомендации по технологиям
• План реализации по этапам
• Риски и mitigation strategies""",
            "skills": ["System Design", "Microservices", "Database Design", "Cloud Architecture", "API Design"],
            "constraints": ["Учитывай требования бизнеса", "Оценивай trade-offs", "Планируй на будущее"],
            "temperature": 0.8,
            "examples": [
                "Спроектируй архитектуру для сервиса с 1M пользователей",
                "Выбери стек технологий для стартапа e-commerce"
            ]
        },
        
        "tester": {
            "name": "Инженер по тестированию",
            "description": "Специалист по созданию тестов и обеспечению качества",
            "category": RoleCategory.TESTING,
            "system_prompt": """Ты — QA инженер с экспертизой в автоматизированном и ручном тестировании.

ТВОИ НАВЫКИ:
• Написание unit, integration и e2e тестов
• Test-driven development (TDD)
• Параметризированные и property-based тесты
• Mocking и stubbing зависимостей
• Coverage analysis

ТВОЙ ПОДХОД:
1. Пойми функциональность которую нужно протестировать
2. Определи нормальные и граничные случаи
3. Спроектируй тесты для покрытия всех сценариев
4. Напиши читаемые и поддерживаемые тесты
5. Включи негативные сценарии

ТИПЫ ТЕСТОВ КОТОРЫЕ ТЫ СОЗДАЁШЬ:
• Unit тесты для отдельных функций/методов
• Integration тесты для взаимодействия компонентов
• Edge case тесты для граничных условий
• Negative тесты для обработки ошибок
• Property-based тесты для инвариантов

ФОРМАТ ОТВЕТА:
• Стратегия тестирования
• Код тестов с пояснениями
• Описание тестируемых сценариев
• Рекомендации по запуску и CI/CD интеграции""",
            "skills": ["Unit Testing", "Integration Testing", "TDD", "Pytest", "Mocking"],
            "constraints": ["Тесты должны быть независимыми", "Используй понятные имена", "Включай edge cases"],
            "temperature": 0.6,
            "examples": [
                "Напиши unit тесты для функции сортировки",
                "Создай integration тесты для REST API"
            ]
        },
        
        "documenter": {
            "name": "Технический писатель",
            "description": "Специалист по созданию документации и руководств",
            "category": RoleCategory.DOCUMENTATION,
            "system_prompt": """Ты — технический писатель с опытом создания документации для разработчиков.

ТВОИ НАВЫКИ:
• Написание API документации
• Создание руководств пользователя
• Генерация README и getting started guides
• Документирование архитектурных решений (ADR)
• Создание туториалов и examples

ТВОЙ ПОДХОД:
1. Изучи код и пойми его назначение
2. Определи целевую аудиторию документации
3. Структурируй информацию логично
4. Пиши ясно и кратко
5. Включай примеры использования

ТИПЫ ДОКУМЕНТАЦИИ:
• API Reference с описанием параметров
• User Guides и tutorials
• Installation guides
• Troubleshooting guides
• Architecture Decision Records

ФОРМАТ ОТВЕТА:
• Структура документации
• Полный текст с markdown форматированием
• Примеры кода где уместно
• Diagrams (текстовое описание)""",
            "skills": ["Technical Writing", "API Documentation", "Markdown", "Diagram Creation"],
            "constraints": ["Пиши для своей аудитории", "Используй примеры", "Поддерживай актуальность"],
            "temperature": 0.7,
            "examples": [
                "Напиши README для Python библиотеки",
                "Создай документацию для REST API endpoint"
            ]
        },
        
        "security_expert": {
            "name": "Эксперт по безопасности",
            "description": "Специалист по безопасности кода и систем",
            "category": RoleCategory.SECURITY,
            "system_prompt": """Ты — эксперт по кибербезопасности с фокусом на security code review.

ТВОИ НАВЫКИ:
• Выявление OWASP Top 10 уязвимостей
• Анализ криптографической реализации
• Проверка аутентификации и авторизации
• Security hardening рекомендаций
• Secure coding best practices

ТВОЙ ПОДХОД:
1. Анализируй код с позиции атакующего
2. Ищи уязвимости в обработке ввода
3. Проверяй управление сессиями и доступом
4. Оценивай криптографические примитивы
5. Рекомендуй security controls

УЯЗВИМОСТИ КОТОРЫЕ ТЫ ИЩЕШЬ:
• SQL Injection, XSS, CSRF
• Buffer overflows
• Insecure deserialization
• Hardcoded credentials
• Weak cryptography
• Privilege escalation

ФОРМАТ ОТВЕТА:
• Список найденных уязвимостей с CVSS оценкой
• Детальное описание каждой проблемы
• PoC exploitation (если применимо)
• Конкретные remediation steps
• Security recommendations""",
            "skills": ["Security Audit", "Penetration Testing", "Cryptography", "OWASP"],
            "constraints": ["Не раскрывай чувствительную информацию", "Давай actionable рекомендации", "Приоритизируй по риску"],
            "temperature": 0.5,
            "examples": [
                "Проверь этот код на SQL injection уязвимости",
                "Оцени безопасность реализации аутентификации"
            ]
        }
    }
    
    def __init__(self, custom_roles_path: Optional[Path] = None):
        """
        Инициализация движка ролей.
        
        Args:
            custom_roles_path: Путь к файлу пользовательских ролей (JSON)
        """
        self._roles: Dict[str, RoleDefinition] = {}
        self._active_role_id: Optional[str] = None
        self._custom_roles_path = custom_roles_path or Path("custom_roles.json")
        
        # Загрузка встроенных ролей
        self._load_builtin_roles()
        
        # Загрузка пользовательских ролей
        self._load_custom_roles()
    
    def _load_builtin_roles(self):
        """Загрузить встроенные роли."""
        for role_id, role_data in self.BUILTIN_ROLES.items():
            self._roles[role_id] = RoleDefinition(
                id=role_id,
                name=role_data['name'],
                description=role_data['description'],
                category=role_data['category'],
                system_prompt=role_data['system_prompt'],
                skills=role_data.get('skills', []),
                constraints=role_data.get('constraints', []),
                temperature=role_data.get('temperature', 0.7),
                max_tokens=role_data.get('max_tokens', 4096),
                examples=role_data.get('examples', []),
                is_builtin=True,
            )
    
    def _load_custom_roles(self):
        """Загрузить пользовательские роли из файла."""
        if not self._custom_roles_path.exists():
            return
        
        try:
            with open(self._custom_roles_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for role_data in data.get('roles', []):
                role = RoleDefinition.from_dict(role_data)
                role.is_builtin = False
                self._roles[role.id] = role
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Не удалось загрузить пользовательские роли: {e}")
    
    def save_custom_roles(self):
        """Сохранить пользовательские роли в файл."""
        custom_roles = [
            role.to_dict() for role in self._roles.values()
            if not role.is_builtin
        ]
        
        with open(self._custom_roles_path, 'w', encoding='utf-8') as f:
            json.dump({'roles': custom_roles}, f, indent=2, ensure_ascii=False)
    
    def list_roles(
        self,
        category: Optional[RoleCategory] = None,
        include_builtin: bool = True
    ) -> List[RoleDefinition]:
        """
        Получить список ролей.
        
        Args:
            category: Фильтр по категории
            include_builtin: Включать ли встроенные роли
            
        Returns:
            Список RoleDefinition
        """
        roles = list(self._roles.values())
        
        if category is not None:
            roles = [r for r in roles if r.category == category]
        
        if not include_builtin:
            roles = [r for r in roles if not r.is_builtin]
        
        return sorted(roles, key=lambda r: r.name)
    
    def get_role(self, role_id: str) -> Optional[RoleDefinition]:
        """
        Получить роль по ID.
        
        Args:
            role_id: Идентификатор роли
            
        Returns:
            RoleDefinition или None
        """
        return self._roles.get(role_id)
    
    def set_active_role(self, role_id: str) -> bool:
        """
        Установить активную роль.
        
        Args:
            role_id: ID роли для активации
            
        Returns:
            True если роль найдена и установлена
        """
        if role_id not in self._roles:
            return False
        
        self._active_role_id = role_id
        return True
    
    def get_active_role(self) -> Optional[RoleDefinition]:
        """Получить активную роль."""
        if self._active_role_id is None:
            return None
        return self._roles.get(self._active_role_id)
    
    def get_system_prompt(self, role_id: Optional[str] = None) -> str:
        """
        Получить системный промпт для роли.
        
        Args:
            role_id: ID роли (или активная если None)
            
        Returns:
            Системный промпт
        """
        if role_id is None:
            role_id = self._active_role_id
        
        if role_id is None:
            return "Ты — полезный ассистент."
        
        role = self._roles.get(role_id)
        if role is None:
            return "Ты — полезный ассистент."
        
        return role.system_prompt
    
    def build_messages(
        self,
        user_message: str,
        role_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Построить сообщения для API с учётом роли.
        
        Args:
            user_message: Сообщение пользователя
            role_id: ID роли (или активная если None)
            
        Returns:
            Список сообщений для OpenAI API
        """
        if role_id is None:
            role_id = self._active_role_id
        
        if role_id is None:
            return [{"role": "user", "content": user_message}]
        
        role = self._roles.get(role_id)
        if role is None:
            return [{"role": "user", "content": user_message}]
        
        return role.build_messages(user_message)
    
    def create_custom_role(
        self,
        id: str,
        name: str,
        description: str,
        system_prompt: str,
        category: RoleCategory = RoleCategory.CUSTOM,
        **kwargs
    ) -> RoleDefinition:
        """
        Создать пользовательскую роль.
        
        Args:
            id: Уникальный идентификатор
            name: Отображаемое имя
            description: Описание
            system_prompt: Системный промпт
            category: Категория
            **kwargs: Дополнительные параметры
            
        Returns:
            Созданная роль
            
        Raises:
            ValueError: Если роль с таким ID уже существует
        """
        if id in self._roles:
            raise ValueError(f"Роль с ID '{id}' уже существует")
        
        role = RoleDefinition(
            id=id,
            name=name,
            description=description,
            category=category,
            system_prompt=system_prompt,
            is_builtin=False,
            **kwargs
        )
        
        self._roles[id] = role
        self.save_custom_roles()
        
        return role
    
    def delete_custom_role(self, role_id: str) -> bool:
        """
        Удалить пользовательскую роль.
        
        Args:
            role_id: ID роли для удаления
            
        Returns:
            True если роль удалена, False если не найдена или встроенная
        """
        role = self._roles.get(role_id)
        if role is None or role.is_builtin:
            return False
        
        del self._roles[role_id]
        
        if self._active_role_id == role_id:
            self._active_role_id = None
        
        self.save_custom_roles()
        return True
    
    def update_custom_role(self, role_id: str, **updates) -> Optional[RoleDefinition]:
        """
        Обновить пользовательскую роль.
        
        Args:
            role_id: ID роли для обновления
            **updates: Поля для обновления
            
        Returns:
            Обновлённая роль или None
        """
        role = self._roles.get(role_id)
        if role is None or role.is_builtin:
            return None
        
        # Обновление полей
        for key, value in updates.items():
            if hasattr(role, key):
                setattr(role, value)
        
        self.save_custom_roles()
        return role
    
    def get_recommendations(self, task_description: str) -> List[RoleDefinition]:
        """
        Рекомендовать роли基于任务描述.
        
        Args:
            task_description: Описание задачи
            
        Returns:
            Список рекомендованных ролей
        """
        keywords_map = {
            RoleCategory.DEVELOPMENT: ['код', 'функция', 'класс', 'напиши', 'создай', 'реализуй'],
            RoleCategory.ANALYSIS: ['анализ', 'проверь', 'найди', 'оцени', 'ревью'],
            RoleCategory.TESTING: ['тест', 'проверка', 'unit', 'integration', 'pytest'],
            RoleCategory.DOCUMENTATION: ['документация', 'readme', 'описание', 'manual'],
            RoleCategory.SECURITY: ['безопасность', 'уязвимость', 'security', 'audit'],
            RoleCategory.ARCHITECTURE: ['архитектура', 'дизайн', 'система', 'масштаб'],
        }
        
        task_lower = task_description.lower()
        scores = {}
        
        for category, keywords in keywords_map.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[category] = score
        
        if not scores:
            return self.list_roles()[:3]
        
        recommended = []
        for category, score in sorted(scores.items(), key=lambda x: -x[1]):
            roles = [r for r in self.list_roles() if r.category == category]
            recommended.extend(roles[:2])
        
        return recommended[:5]
