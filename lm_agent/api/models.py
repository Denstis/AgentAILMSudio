"""
Модели данных для API.

Модуль содержит типы данных для работы с моделями LLM.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ModelCapabilities:
    """Возможности модели."""
    vision: bool = False
    tool_use: bool = False
    reasoning: bool = False
    json_mode: bool = False
    function_calling: bool = False
    embedding: bool = False
    
    def to_dict(self) -> Dict[str, bool]:
        """Преобразовать в словарь."""
        return {
            'vision': self.vision,
            'tool_use': self.tool_use,
            'reasoning': self.reasoning,
            'json_mode': self.json_mode,
            'function_calling': self.function_calling,
            'embedding': self.embedding,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelCapabilities:
        """Создать из словаря."""
        return cls(
            vision=data.get('vision', False),
            tool_use=data.get('tool_use', False),
            reasoning=data.get('reasoning', False),
            json_mode=data.get('json_mode', False),
            function_calling=data.get('function_calling', False),
            embedding=data.get('embedding', False),
        )


@dataclass
class ModelInfo:
    """
    Информация о модели LLM.
    
    Attributes:
        id: Уникальный идентификатор модели
        name: Отображаемое имя модели
        owned_by: Владелец модели (организация)
        created: Дата создания (timestamp)
        context_window: Размер контекстного окна в токенах
        max_tokens: Максимальное количество выходных токенов
        capabilities: Возможности модели
        description: Описание модели
        tags: Теги для категоризации
        is_default: Флаг модели по умолчанию
        status: Статус модели (active, inactive, loading)
    """
    id: str
    name: str = ""
    owned_by: str = "unknown"
    created: int = 0
    context_window: int = 4096
    max_tokens: int = 2048
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    is_default: bool = False
    status: str = "active"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            'id': self.id,
            'name': self.name,
            'owned_by': self.owned_by,
            'created': self.created,
            'context_window': self.context_window,
            'max_tokens': self.max_tokens,
            'capabilities': self.capabilities.to_dict(),
            'description': self.description,
            'tags': self.tags,
            'is_default': self.is_default,
            'status': self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelInfo:
        """Создать из словаря."""
        caps_data = data.get('capabilities', {})
        if isinstance(caps_data, ModelCapabilities):
            capabilities = caps_data
        else:
            capabilities = ModelCapabilities.from_dict(caps_data)
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', data.get('id', '')),
            owned_by=data.get('owned_by', 'unknown'),
            created=data.get('created', 0),
            context_window=data.get('context_window', 4096),
            max_tokens=data.get('max_tokens', 2048),
            capabilities=capabilities,
            description=data.get('description', ''),
            tags=data.get('tags', []),
            is_default=data.get('is_default', False),
            status=data.get('status', 'active'),
        )
    
    @property
    def created_datetime(self) -> Optional[datetime]:
        """Дата создания в формате datetime."""
        if self.created:
            return datetime.fromtimestamp(self.created)
        return None
    
    def __str__(self) -> str:
        """Строковое представление."""
        return f"{self.name} ({self.id})"


@dataclass
class ModelList:
    """
    Список доступных моделей.
    
    Attributes:
        models: Список объектов ModelInfo
        object: Тип объекта (обычно 'list')
        has_more: Есть ли ещё модели для загрузки
    """
    models: List[ModelInfo] = field(default_factory=list)
    object: str = "list"
    has_more: bool = False
    
    def __len__(self) -> int:
        """Количество моделей."""
        return len(self.models)
    
    def __iter__(self):
        """Итератор по моделям."""
        return iter(self.models)
    
    def __getitem__(self, index: int) -> ModelInfo:
        """Получить модель по индексу."""
        return self.models[index]
    
    def add(self, model: ModelInfo):
        """Добавить модель в список."""
        self.models.append(model)
    
    def get_by_id(self, model_id: str) -> Optional[ModelInfo]:
        """Найти модель по ID."""
        for model in self.models:
            if model.id == model_id:
                return model
        return None
    
    def get_by_name(self, name: str) -> Optional[ModelInfo]:
        """Найти модель по имени."""
        for model in self.models:
            if model.name == name or model.id == name:
                return model
        return None
    
    def filter_by_capability(self, capability: str) -> List[ModelInfo]:
        """Фильтровать модели по возможности."""
        result = []
        for model in self.models:
            caps = model.capabilities
            if getattr(caps, capability, False):
                result.append(model)
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            'object': self.object,
            'has_more': self.has_more,
            'models': [m.to_dict() for m in self.models],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelList:
        """Создать из словаря."""
        models = [ModelInfo.from_dict(m) for m in data.get('models', [])]
        return cls(
            models=models,
            object=data.get('object', 'list'),
            has_more=data.get('has_more', False),
        )
